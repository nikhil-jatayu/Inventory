from datetime import date
from uuid import uuid4
from app.services.balances import rejected_for_dispatch

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.fiscal import (
    fiscal_bounds,
    fiscal_label,
    fiscal_months,
    fiscal_start_year,
    month_label,
    parse_fiscal_year,
)
from app.models import Dispatch, SalesRecord, Item, Rejection, RejectionIssue, Unit, User
from app.schemas.common import Page
from app.schemas.rejections import (
    RejectionBatchCreate,
    RejectionCreate,
    RejectionIssueCreate,
    RejectionIssueList,
    RejectionIssueOut,
    RejectionIssueStat,
    RejectionIssueUpdate,
    RejectionMonth,
    RejectionOut,
    RejectionReport,
)
from app.services.purchase_orders import ZERO, as_decimal

REJECTION_SORT_COLUMNS = {
    "rejection_date": Rejection.rejection_date,
    "quantity": Rejection.quantity,
    "item": Item.name,
    "issue": RejectionIssue.name,
}


def _normalise_name(value: str) -> str:
    return " ".join(value.split())


def _issue_out(issue: RejectionIssue, rejection_count: int = 0) -> RejectionIssueOut:
    return RejectionIssueOut(
        id=issue.id,
        name=issue.name,
        is_active=issue.is_active,
        rejection_count=rejection_count,
    )


def _find_issue_by_name(db: Session, name: str) -> RejectionIssue | None:
    return db.scalar(
        select(RejectionIssue).where(
            func.lower(RejectionIssue.name) == name.lower()
        )
    )


def _fiscal_year_expression(column):
    month = func.extract("month", column)
    year = func.extract("year", column)
    return case((month >= settings.fy_start_month, year), else_=year - 1)


def list_issues(db: Session, *, include_inactive: bool = False) -> RejectionIssueList:
    counts = (
        select(
            Rejection.issue_id.label("issue_id"),
            func.count(Rejection.id).label("rejection_count"),
        )
        .group_by(Rejection.issue_id)
        .subquery()
    )

    filters = [] if include_inactive else [RejectionIssue.is_active.is_(True)]
    rows = db.execute(
        select(RejectionIssue, func.coalesce(counts.c.rejection_count, literal(0)))
        .outerjoin(counts, counts.c.issue_id == RejectionIssue.id)
        .where(*filters)
        .order_by(RejectionIssue.is_active.desc(), RejectionIssue.name)
    ).all()

    return RejectionIssueList(
        issues=[_issue_out(issue, int(count)) for issue, count in rows]
    )


def create_issue(db: Session, payload: RejectionIssueCreate) -> RejectionIssueOut:
    name = _normalise_name(payload.name)
    existing = _find_issue_by_name(db, name)
    if existing is not None:
        if existing.is_active:
            raise AppError(409, f'Rejection issue "{existing.name}" already exists')
        existing.is_active = True
        db.commit()
        db.refresh(existing)
        return _issue_out(existing)

    issue = RejectionIssue(name=name)
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return _issue_out(issue)


def update_issue(
    db: Session, issue_id: int, payload: RejectionIssueUpdate
) -> RejectionIssueOut:
    issue = db.get(RejectionIssue, issue_id)
    if issue is None:
        raise AppError(404, "Rejection issue not found")

    changes = payload.model_dump(exclude_unset=True)
    new_name = changes.get("name")
    if new_name is not None and new_name.lower() != issue.name.lower():
        existing = _find_issue_by_name(db, new_name)
        if existing is not None and existing.id != issue.id:
            raise AppError(409, f'Rejection issue "{existing.name}" already exists')
        issue.name = new_name

    if "is_active" in changes and changes["is_active"] is not None:
        issue.is_active = changes["is_active"]

    db.commit()
    db.refresh(issue)
    return _issue_out(issue)


def deactivate_issue(db: Session, issue_id: int) -> RejectionIssueOut:
    issue = db.get(RejectionIssue, issue_id)
    if issue is None:
        raise AppError(404, "Rejection issue not found")
    issue.is_active = False
    db.commit()
    db.refresh(issue)
    return _issue_out(issue)




def apply_rejection_stock_effect(db: Session, rejection: Rejection) -> None:
    """Keep the rejection-to-stock rule in one place.

    Quality rejections are customer rejections of material that was already
    dispatched, so recording one does not change the stock ledger. If rejected
    material should ever be returned to stock, implement that here only.
    """
    return None


def _rejection_out(db: Session, rejection_id: int) -> RejectionOut:
    row = db.execute(
        select(Rejection, Item, RejectionIssue, User, Unit)
        .join(Item, Item.id == Rejection.item_id)
        .outerjoin(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
        .join(User, User.id == Rejection.recorded_by)
        .outerjoin(Unit, Unit.id == Rejection.unit_id)
        .where(Rejection.id == rejection_id)
    ).first()
    if row is None:
        raise AppError(404, "Rejection not found")

    rejection, item, issue, user, unit = row
    return RejectionOut(
        id=rejection.id, dispatch_id=rejection.dispatch_id, batch_id=rejection.batch_id,
        invoice_number=db.scalar(select(SalesRecord.invoice_number).where(SalesRecord.dispatch_id == rejection.dispatch_id)) if rejection.dispatch_id else None,
        rgp_number=rejection.rgp_number,
        unit_id=unit.id if unit else None,
        unit_name=unit.name if unit else None,
        item_id=item.id,
        item_name=item.name,
        item_family=item.family, project=item.project,
        rejection_date=rejection.rejection_date,
        quantity=rejection.quantity,
        issue_id=issue.id if issue else None,
        issue_name=issue.name if issue else None,
        remarks=rejection.remarks,
        recorded_by=user.id,
        recorded_by_name=user.full_name,
    )


def record_rejection(db: Session, payload: RejectionCreate, *, recorded_by: User) -> RejectionOut:
    return record_rejection_batch(db, RejectionBatchCreate(rgp_number=payload.rgp_number, unit_id=payload.unit_id,
        rejection_date=payload.rejection_date, lines=[payload.model_dump()]), recorded_by=recorded_by, remarks=payload.remarks)[0]


def record_rejection_batch(db: Session, payload: RejectionBatchCreate, *, recorded_by: User, remarks=None) -> list[RejectionOut]:
    try:
        unit = db.get(Unit, payload.unit_id)
        if unit is None or not unit.is_active:
            raise AppError(422, "Select an active unit")
        if payload.rejection_date > date.today():
            raise AppError(422, "Rejection date cannot be in the future")
        ids = [line.dispatch_id for line in payload.lines]
        if None in ids or len(set(ids)) != len(ids):
            raise AppError(422, "Select a different actual dispatch for each row")
        dispatches = {d.id:d for d in db.scalars(select(Dispatch).where(Dispatch.id.in_(ids)).order_by(Dispatch.id).with_for_update().execution_options(populate_existing=True)).all()}
        batch_id = str(uuid4())
        records = []
        for line in payload.lines:
            d = dispatches.get(line.dispatch_id)
            if d is None or d.unit_id != unit.id or d.item_id != line.item_id:
                raise AppError(422, "Dispatch does not match the selected unit and item")
            if d.dispatch_date > payload.rejection_date:
                raise AppError(422, "Rejection cannot precede actual dispatch")
            if db.scalar(select(SalesRecord.id).where(SalesRecord.dispatch_id == d.id)) is None:
                raise AppError(422, "Dispatch has no recorded sale; historical reconciliation is required")
            remaining = d.quantity - db.scalar(select(rejected_for_dispatch(d.id)))
            if line.quantity > remaining:
                raise AppError(422, f"Quantity exceeds unrejected quantity for dispatch #{d.id}")
            record = Rejection(dispatch_id=d.id, batch_id=batch_id, rgp_number=payload.rgp_number, unit_id=unit.id,
                item_id=d.item_id, rejection_date=payload.rejection_date, quantity=line.quantity, issue_id=None,
                recorded_by=recorded_by.id, remarks=remarks)
            db.add(record)
            records.append(record)
        db.flush()
        result = [_rejection_out(db, record.id) for record in records]
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def list_rejections(
    db: Session,
    *,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
    family: str | None,
    issue_id: int | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
    unit_id: int | None = None,
) -> Page[RejectionOut]:
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "The start date must be on or before the end date")

    filters = []
    if unit_id:
        filters.append(Rejection.unit_id == unit_id)
    if date_from:
        filters.append(Rejection.rejection_date >= date_from)
    if date_to:
        filters.append(Rejection.rejection_date <= date_to)
    if family:
        filters.append(Item.family == family)
    if issue_id:
        filters.append(Rejection.issue_id == issue_id)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            or_(
                Item.name.ilike(needle),
                Item.family.ilike(needle),
                Item.project.ilike(needle),
                RejectionIssue.name.ilike(needle),
                Rejection.rgp_number.ilike(needle),
                Unit.name.ilike(needle),
                Rejection.remarks.ilike(needle),
            )
        )

    total = (
        db.scalar(
            select(func.count(Rejection.id))
            .select_from(Rejection)
            .join(Item, Item.id == Rejection.item_id)
            .outerjoin(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
            .outerjoin(Unit, Unit.id == Rejection.unit_id)
            .where(*filters)
        )
        or 0
    )

    sort_column = REJECTION_SORT_COLUMNS.get(sort, Rejection.rejection_date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    rows = db.execute(
        select(Rejection, Item, RejectionIssue, User, Unit)
        .join(Item, Item.id == Rejection.item_id)
        .outerjoin(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
        .join(User, User.id == Rejection.recorded_by)
        .outerjoin(Unit, Unit.id == Rejection.unit_id)
        .where(*filters)
        .order_by(ordering, Rejection.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        RejectionOut(
            id=rejection.id, dispatch_id=rejection.dispatch_id, batch_id=rejection.batch_id,
        invoice_number=db.scalar(select(SalesRecord.invoice_number).where(SalesRecord.dispatch_id == rejection.dispatch_id)) if rejection.dispatch_id else None,
            rgp_number=rejection.rgp_number,
            unit_id=unit.id if unit else None,
            unit_name=unit.name if unit else None,
            item_id=item.id,
            item_name=item.name,
            item_family=item.family, project=item.project,
            rejection_date=rejection.rejection_date,
            quantity=rejection.quantity,
            issue_id=issue.id if issue else None,
            issue_name=issue.name if issue else None,
            remarks=rejection.remarks,
            recorded_by=user.id,
            recorded_by_name=user.full_name,
        )
        for rejection, item, issue, user, unit in rows
    ]

    return Page[RejectionOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def get_rejection_report(
    db: Session,
    *,
    fy: str | None,
    family: str | None,
) -> RejectionReport:
    if fy:
        try:
            start_year = parse_fiscal_year(fy)
        except ValueError as exc:
            raise AppError(422, str(exc)) from exc
    else:
        start_year = fiscal_start_year()

    start, end = fiscal_bounds(start_year)
    months = fiscal_months(start_year)

    filters = [Rejection.rejection_date >= start, Rejection.rejection_date <= end]
    if family:
        filters.append(Item.family == family)

    rejection_year = func.extract("year", Rejection.rejection_date)
    rejection_month = func.extract("month", Rejection.rejection_date)

    month_rows = db.execute(
        select(rejection_year, rejection_month, func.sum(Rejection.quantity))
        .join(Item, Item.id == Rejection.item_id)
        .where(*filters)
        .group_by(rejection_year, rejection_month)
    ).all()
    by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in month_rows
    }

    total_quantity = ZERO
    month_stats: list[RejectionMonth] = []
    for bucket in months:
        quantity = by_month.get((bucket.year, bucket.month), ZERO)
        total_quantity += quantity
        month_stats.append(
            RejectionMonth(
                month=bucket.strftime("%Y-%m"),
                label=month_label(bucket),
                quantity=quantity,
            )
        )

    issue_rows = db.execute(
        select(
            RejectionIssue.id,
            RejectionIssue.name,
            func.sum(Rejection.quantity),
            func.count(Rejection.id),
        )
        .join(Rejection, Rejection.issue_id == RejectionIssue.id)
        .join(Item, Item.id == Rejection.item_id)
        .where(*filters)
        .group_by(RejectionIssue.id, RejectionIssue.name)
        .order_by(func.sum(Rejection.quantity).desc(), RejectionIssue.name)
    ).all()

    issues: list[RejectionIssueStat] = []
    cumulative = ZERO
    for issue_id, name, quantity, count in issue_rows:
        issue_quantity = as_decimal(quantity)
        share = (
            float(issue_quantity / total_quantity * 100) if total_quantity > 0 else 0.0
        )
        cumulative += issue_quantity
        cumulative_share = (
            float(cumulative / total_quantity * 100) if total_quantity > 0 else 0.0
        )
        issues.append(
            RejectionIssueStat(
                issue_id=issue_id,
                name=name,
                quantity=issue_quantity,
                count=int(count),
                share=round(share, 1),
                cumulative_share=round(min(cumulative_share, 100.0), 1),
            )
        )

    rejection_count = (
        db.scalar(
            select(func.count(Rejection.id))
            .select_from(Rejection)
            .join(Item, Item.id == Rejection.item_id)
            .where(*filters)
        )
        or 0
    )

    year_expression = _fiscal_year_expression(Rejection.rejection_date)
    family_filters = [Item.family == family] if family else []
    year_rows = db.execute(
        select(year_expression, func.sum(Rejection.quantity))
        .select_from(Rejection)
        .join(Item, Item.id == Rejection.item_id)
        .where(*family_filters)
        .group_by(year_expression)
    ).all()

    years = {int(row[0]) for row in year_rows}
    years.update({fiscal_start_year(), start_year})
    fy_options = [
        fiscal_label(year) for year in sorted(years, reverse=True)
    ]

    return RejectionReport(
        fy=fiscal_label(start_year),
        fy_start=start,
        fy_end=end,
        fy_options=fy_options,
        months=month_stats,
        issues=issues,
        total_quantity=total_quantity,
        rejection_count=rejection_count,
        top_issue=issues[0].name if issues else None,
    )


__all__ = [
    "apply_rejection_stock_effect",
    "create_issue",
    "deactivate_issue",
    "get_rejection_report",
    "list_issues",
    "list_rejections",
    "record_rejection",
    "update_issue",
]
