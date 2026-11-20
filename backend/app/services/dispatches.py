from datetime import date
from decimal import Decimal

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
from app.models import (
    Dispatch,
    DispatchPlan,
    Item,
    PlanStatus,
    POLine,
    POStatus,
    PurchaseOrder,
    StockTransaction,
    StockTxnType,
)
from app.schemas.common import Page
from app.schemas.dispatches import (
    DispatchCreate,
    DispatchFYTotal,
    DispatchMonth,
    DispatchOut,
    DispatchReport,
)
from app.services.purchase_orders import (
    ZERO,
    as_decimal,
    format_quantity,
    refresh_po_status,
)

DISPATCH_SORT_COLUMNS = {
    "dispatch_date": Dispatch.dispatch_date,
    "quantity": Dispatch.quantity,
    "item": Item.name,
    "po_number": PurchaseOrder.po_number,
}


def _dispatch_out(
    dispatch: Dispatch, line: POLine, po: PurchaseOrder, item: Item
) -> DispatchOut:
    return DispatchOut(
        id=dispatch.id,
        po_line_id=line.id,
        po_id=po.id,
        po_number=po.po_number,
        customer_name=po.customer_name,
        unit_number=po.unit_number,
        item_id=item.id,
        item_name=item.name,
        item_family=item.family,
        dispatch_date=dispatch.dispatch_date,
        quantity=dispatch.quantity,
        remarks=dispatch.remarks,
    )


def _apply_to_plans(db: Session, line_id: int, quantity: Decimal) -> None:
    """Fulfil the line's open plans in planned-date order."""
    remaining = quantity
    plans = db.scalars(
        select(DispatchPlan)
        .where(
            DispatchPlan.po_line_id == line_id,
            DispatchPlan.status != PlanStatus.DONE,
        )
        .order_by(DispatchPlan.planned_date, DispatchPlan.id)
    ).all()

    for plan in plans:
        outstanding = plan.quantity - plan.fulfilled_quantity
        if outstanding <= 0:
            plan.status = PlanStatus.DONE
            continue

        taken = min(remaining, outstanding)
        plan.fulfilled_quantity += taken
        plan.status = (
            PlanStatus.DONE
            if plan.fulfilled_quantity >= plan.quantity
            else PlanStatus.PARTIAL
        )
        remaining -= taken
        if remaining <= 0:
            break


def record_dispatch(db: Session, payload: DispatchCreate) -> DispatchOut:
    line = db.scalar(
        select(POLine).where(POLine.id == payload.po_line_id).with_for_update()
    )
    if line is None:
        raise AppError(404, "Purchase order line not found")

    po = db.get(PurchaseOrder, line.po_id)
    item = db.scalar(select(Item).where(Item.id == line.item_id).with_for_update())
    if po is None or item is None:
        raise AppError(404, "Purchase order line not found")
    if po.status == POStatus.CANCELLED:
        raise AppError(422, "Cannot dispatch against a cancelled purchase order")
    if not item.is_active:
        raise AppError(422, f"{item.name} is inactive and cannot be dispatched")

    dispatched = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(Dispatch.quantity), literal(0))).where(
                Dispatch.po_line_id == line.id
            )
        )
    )
    balance = line.quantity - dispatched
    if balance <= 0:
        raise AppError(422, "This purchase order line has no remaining balance to dispatch")
    if payload.quantity > balance:
        raise AppError(
            422,
            f"Dispatch quantity exceeds the PO line balance. Balance: {format_quantity(balance)}",
        )

    available = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(StockTransaction.quantity), literal(0))).where(
                StockTransaction.item_id == item.id
            )
        )
    )
    if payload.quantity > available:
        raise AppError(
            422,
            f"Only {format_quantity(available)} units are available in stock",
        )

    dispatch = Dispatch(
        po_line_id=line.id,
        item_id=item.id,
        dispatch_date=payload.dispatch_date,
        quantity=payload.quantity,
        remarks=payload.remarks,
    )
    db.add(dispatch)
    db.add(
        StockTransaction(
            item_id=item.id,
            type=StockTxnType.DISPATCH,
            quantity=-payload.quantity,
            date=payload.dispatch_date,
            ref=po.po_number,
            remarks=payload.remarks,
        )
    )
    db.flush()

    _apply_to_plans(db, line.id, payload.quantity)
    refresh_po_status(db, po)
    db.commit()
    db.refresh(dispatch)

    return _dispatch_out(dispatch, line, po, item)


def list_dispatches(
    db: Session,
    *,
    search: str | None,
    date_from: date | None,
    date_to: date | None,
    family: str | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Page[DispatchOut]:
    filters = []
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "The start date must be on or before the end date")
    if date_from:
        filters.append(Dispatch.dispatch_date >= date_from)
    if date_to:
        filters.append(Dispatch.dispatch_date <= date_to)
    if family:
        filters.append(Item.family == family)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            Item.name.ilike(needle)
            | PurchaseOrder.po_number.ilike(needle)
            | PurchaseOrder.customer_name.ilike(needle)
            | PurchaseOrder.unit_number.ilike(needle)
            | Dispatch.remarks.ilike(needle)
        )

    joins = (
        select(Dispatch, POLine, PurchaseOrder, Item)
        .join(POLine, POLine.id == Dispatch.po_line_id)
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == Dispatch.item_id)
        .where(*filters)
    )

    total = (
        db.scalar(
            select(func.count(Dispatch.id))
            .select_from(Dispatch)
            .join(POLine, POLine.id == Dispatch.po_line_id)
            .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
            .join(Item, Item.id == Dispatch.item_id)
            .where(*filters)
        )
        or 0
    )

    sort_column = DISPATCH_SORT_COLUMNS.get(sort, Dispatch.dispatch_date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    rows = db.execute(
        joins.order_by(ordering, Dispatch.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        _dispatch_out(dispatch, line, po, item) for dispatch, line, po, item in rows
    ]

    return Page[DispatchOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def _fiscal_year_expression(column):
    month = func.extract("month", column)
    year = func.extract("year", column)
    return case(
        (month >= settings.fy_start_month, year),
        else_=year - 1,
    )


def get_dispatch_report(
    db: Session,
    *,
    fy: str | None,
    family: str | None,
) -> DispatchReport:
    if fy:
        try:
            start_year = parse_fiscal_year(fy)
        except ValueError as exc:
            raise AppError(422, str(exc)) from exc
    else:
        start_year = fiscal_start_year()

    start, end = fiscal_bounds(start_year)
    months = fiscal_months(start_year)

    dispatch_filters = [Dispatch.dispatch_date >= start, Dispatch.dispatch_date <= end]
    planned_filters = [
        DispatchPlan.planned_date >= start,
        DispatchPlan.planned_date <= end,
    ]
    if family:
        dispatch_filters.append(Item.family == family)
        planned_filters.append(Item.family == family)

    dispatch_year = func.extract("year", Dispatch.dispatch_date)
    dispatch_month = func.extract("month", Dispatch.dispatch_date)
    planned_year = func.extract("year", DispatchPlan.planned_date)
    planned_month = func.extract("month", DispatchPlan.planned_date)

    dispatched_rows = db.execute(
        select(dispatch_year, dispatch_month, func.sum(Dispatch.quantity))
        .join(Item, Item.id == Dispatch.item_id)
        .where(*dispatch_filters)
        .group_by(dispatch_year, dispatch_month)
    ).all()
    planned_rows = db.execute(
        select(planned_year, planned_month, func.sum(DispatchPlan.quantity))
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(*planned_filters)
        .group_by(planned_year, planned_month)
    ).all()

    dispatched_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in dispatched_rows
    }
    planned_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in planned_rows
    }

    cumulative = ZERO
    total_dispatched = ZERO
    total_planned = ZERO
    month_rows: list[DispatchMonth] = []
    for bucket in months:
        key = (bucket.year, bucket.month)
        planned = planned_by_month.get(key, ZERO)
        dispatched = dispatched_by_month.get(key, ZERO)
        total_planned += planned
        total_dispatched += dispatched
        cumulative += dispatched
        month_rows.append(
            DispatchMonth(
                month=bucket.strftime("%Y-%m"),
                label=month_label(bucket),
                planned=planned,
                dispatched=dispatched,
                cumulative=cumulative,
            )
        )

    dispatch_count = (
        db.scalar(
            select(func.count(Dispatch.id))
            .select_from(Dispatch)
            .join(Item, Item.id == Dispatch.item_id)
            .where(*dispatch_filters)
        )
        or 0
    )

    cumulative_dispatched = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(Dispatch.quantity), literal(0)))
            .select_from(Dispatch)
            .join(Item, Item.id == Dispatch.item_id)
            .where(
                Dispatch.dispatch_date <= end,
                *([Item.family == family] if family else []),
            )
        )
    )

    dispatch_fy = _fiscal_year_expression(Dispatch.dispatch_date)
    planned_fy = _fiscal_year_expression(DispatchPlan.planned_date)
    family_filters = [Item.family == family] if family else []
    dispatch_fy_rows = db.execute(
        select(dispatch_fy, func.sum(Dispatch.quantity))
        .select_from(Dispatch)
        .join(Item, Item.id == Dispatch.item_id)
        .where(*family_filters)
        .group_by(dispatch_fy)
    ).all()
    planned_fy_rows = db.execute(
        select(planned_fy, func.sum(DispatchPlan.quantity))
        .select_from(DispatchPlan)
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(*family_filters)
        .group_by(planned_fy)
    ).all()

    totals: dict[int, dict[str, Decimal]] = {}
    for year, quantity in dispatch_fy_rows:
        totals.setdefault(int(year), {"dispatched": ZERO, "planned": ZERO})[
            "dispatched"
        ] = as_decimal(quantity)
    for year, quantity in planned_fy_rows:
        totals.setdefault(int(year), {"dispatched": ZERO, "planned": ZERO})[
            "planned"
        ] = as_decimal(quantity)

    current_year = fiscal_start_year()
    totals.setdefault(start_year, {"dispatched": ZERO, "planned": ZERO})

    fy_totals = [
        DispatchFYTotal(
            fy=fiscal_label(year),
            start_year=year,
            dispatched=totals[year]["dispatched"],
            planned=totals[year]["planned"],
        )
        for year in sorted(totals)
    ]
    fy_options = [
        fiscal_label(year)
        for year in sorted(set(totals) | {current_year, start_year}, reverse=True)
    ]

    return DispatchReport(
        fy=fiscal_label(start_year),
        fy_start=start,
        fy_end=end,
        fy_options=fy_options,
        months=month_rows,
        fy_totals=fy_totals,
        total_dispatched=total_dispatched,
        total_planned=total_planned,
        cumulative_dispatched=cumulative_dispatched,
        dispatch_count=dispatch_count,
    )


__all__ = ["get_dispatch_report", "list_dispatches", "record_dispatch"]
