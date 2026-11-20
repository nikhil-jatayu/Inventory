from datetime import date

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
from app.models import Item, Rejection, RejectionIssue, User
from app.schemas.common import Page
from app.schemas.rejections import (
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


def _resolve_issue(db: Session, payload: RejectionCreate) -> RejectionIssue:
    if payload.issue_id is not None:
        issue = db.get(RejectionIssue, payload.issue_id)
        if issue is None:
            raise AppError(404, "Rejection issue not found")
        return issue

    name = _normalise_name(payload.issue_name or "")
    existing = _find_issue_by_name(db, name)
    if existing is not None:
        if not existing.is_active:
            existing.is_active = True
        return existing

    issue = RejectionIssue(name=name)
    db.add(issue)
    db.flush()
    return issue


def apply_rejection_stock_effect(db: Session, rejection: Rejection) -> None:
    """Keep the rejection-to-stock rule in one place.

    Quality rejections are customer rejections of material that was already
    dispatched, so recording one does not change the stock ledger. If rejected
    material should ever be returned to stock, implement that here only.
    """
    return None


def _rejection_out(db: Session, rejection_id: int) -> RejectionOut:
    row = db.execute(
        select(Rejection, Item, RejectionIssue, User)
        .join(Item, Item.id == Rejection.item_id)
        .join(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
        .join(User, User.id == Rejection.recorded_by)
        .where(Rejection.id == rejection_id)
    ).first()
    if row is None:
        raise AppError(404, "Rejection not found")

    rejection, item, issue, user = row
    return RejectionOut(
        id=rejection.id,
        item_id=item.id,
        item_name=item.name,
        item_family=item.family,
        rejection_date=rejection.rejection_date,
        quantity=rejection.quantity,
        issue_id=issue.id,
        issue_name=issue.name,
        remarks=rejection.remarks,
        recorded_by=user.id,
        recorded_by_name=user.full_name,
    )


def record_rejection(
    db: Session, payload: RejectionCreate, *, recorded_by: User
) -> RejectionOut:
    item = db.get(Item, payload.item_id)
    if item is None:
        raise AppError(404, "Item not found")

    issue = _resolve_issue(db, payload)
    rejection = Rejection(
        item_id=item.id,
        rejection_date=payload.rejection_date,
        quantity=payload.quantity,
        issue_id=issue.id,
        remarks=payload.remarks,
        recorded_by=recorded_by.id,
    )
    db.add(rejection)
    apply_rejection_stock_effect(db, rejection)
    db.commit()
    db.refresh(rejection)

    return _rejection_out(db, rejection.id)


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
) -> Page[RejectionOut]:
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "The start date must be on or before the end date")

    filters = []
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
                RejectionIssue.name.ilike(needle),
                Rejection.remarks.ilike(needle),
            )
        )

    total = (
        db.scalar(
            select(func.count(Rejection.id))
            .select_from(Rejection)
            .join(Item, Item.id == Rejection.item_id)
            .join(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
            .where(*filters)
        )
        or 0
    )

    sort_column = REJECTION_SORT_COLUMNS.get(sort, Rejection.rejection_date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    rows = db.execute(
        select(Rejection, Item, RejectionIssue, User)
        .join(Item, Item.id == Rejection.item_id)
        .join(RejectionIssue, RejectionIssue.id == Rejection.issue_id)
        .join(User, User.id == Rejection.recorded_by)
        .where(*filters)
        .order_by(ordering, Rejection.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        RejectionOut(
            id=rejection.id,
            item_id=item.id,
            item_name=item.name,
            item_family=item.family,
            rejection_date=rejection.rejection_date,
            quantity=rejection.quantity,
            issue_id=issue.id,
            issue_name=issue.name,
            remarks=rejection.remarks,
            recorded_by=user.id,
            recorded_by_name=user.full_name,
        )
        for rejection, item, issue, user in rows
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
