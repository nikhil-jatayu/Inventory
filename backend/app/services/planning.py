from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, case, func, literal, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.models import DispatchPlan, Item, PlanStatus, POLine, POStatus, Priority, PurchaseOrder
from app.schemas.planning import (
    DispatchPlanCreate,
    DispatchPlanOut,
    DispatchPlanUpdate,
    PlanningSettingsOut,
    ScheduleFilter,
    ScheduleSummary,
    StockVsSchedulePage,
    StockVsScheduleRow,
)
from app.schemas.stock import StockStatus
from app.services.purchase_orders import as_decimal, format_quantity, get_line_metrics
from app.services.stock import stock_sums_subquery

ZERO = Decimal("0")

PRIORITY_SEVERITY = case(
    (DispatchPlan.priority == Priority.EMERGENCY, 0),
    (DispatchPlan.priority == Priority.URGENT, 1),
    else_=2,
)


def lead_time_days(priority: Priority) -> int:
    return {
        Priority.NORMAL: settings.lead_time_normal_days,
        Priority.URGENT: settings.lead_time_urgent_days,
        Priority.EMERGENCY: settings.lead_time_emergency_days,
    }[priority]


def get_planning_settings() -> PlanningSettingsOut:
    return PlanningSettingsOut(
        today=date.today(),
        fy_start_month=settings.fy_start_month,
        lead_times={
            Priority.NORMAL.value: settings.lead_time_normal_days,
            Priority.URGENT.value: settings.lead_time_urgent_days,
            Priority.EMERGENCY.value: settings.lead_time_emergency_days,
        },
    )


def _plan_out(
    plan: DispatchPlan,
    line: POLine,
    po: PurchaseOrder,
    item: Item,
    planned: Decimal,
    dispatched: Decimal,
) -> DispatchPlanOut:
    lead_time = lead_time_days(plan.priority)
    days_until = (plan.planned_date - date.today()).days
    warning = plan.status != PlanStatus.DONE and days_until < lead_time

    return DispatchPlanOut(
        id=plan.id,
        po_line_id=line.id,
        po_id=po.id,
        po_number=po.po_number,
        customer_name=po.customer_name,
        unit_number=po.unit_number,
        item_id=item.id,
        item_name=item.name,
        item_family=item.family,
        planned_date=plan.planned_date,
        quantity=plan.quantity,
        fulfilled_quantity=plan.fulfilled_quantity,
        outstanding_quantity=plan.quantity - plan.fulfilled_quantity,
        priority=plan.priority,
        status=plan.status,
        lead_time_days=lead_time,
        days_until=days_until,
        warning=warning,
        po_quantity=line.quantity,
        po_planned=planned,
        po_dispatched=dispatched,
        po_balance=line.quantity - dispatched,
        po_available_to_plan=line.quantity - dispatched - planned,
    )


def list_dispatch_plans(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    priority: Priority | None,
    status_filter: PlanStatus | None,
    search: str | None,
) -> list[DispatchPlanOut]:
    filters = []
    if date_from:
        filters.append(DispatchPlan.planned_date >= date_from)
    if date_to:
        filters.append(DispatchPlan.planned_date <= date_to)
    if priority:
        filters.append(DispatchPlan.priority == priority)
    if status_filter:
        filters.append(DispatchPlan.status == status_filter)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            Item.name.ilike(needle)
            | PurchaseOrder.po_number.ilike(needle)
            | PurchaseOrder.customer_name.ilike(needle)
            | PurchaseOrder.unit_number.ilike(needle)
        )

    rows = db.execute(
        select(DispatchPlan, POLine, PurchaseOrder, Item)
        .join(POLine, POLine.id == DispatchPlan.po_line_id)
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(*filters)
        .order_by(DispatchPlan.planned_date, PRIORITY_SEVERITY, DispatchPlan.id)
    ).all()

    metrics = get_line_metrics(db, [row[0].po_line_id for row in rows])
    plans = []
    for plan, line, po, item in rows:
        planned, dispatched = metrics.get(line.id, (ZERO, ZERO))
        plans.append(_plan_out(plan, line, po, item, planned, dispatched))
    return plans


def _line_context(
    db: Session, line_id: int
) -> tuple[POLine, PurchaseOrder, Item, Decimal, Decimal]:
    row = db.execute(
        select(POLine, PurchaseOrder, Item)
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == POLine.item_id)
        .where(POLine.id == line_id)
    ).first()
    if row is None:
        raise AppError(404, "Purchase order line not found")

    line, po, item = row
    planned, dispatched = get_line_metrics(db, [line.id]).get(line.id, (ZERO, ZERO))
    return line, po, item, planned, dispatched


def create_dispatch_plan(db: Session, payload: DispatchPlanCreate) -> DispatchPlanOut:
    line, po, item, planned, dispatched = _line_context(db, payload.po_line_id)
    if po.status == POStatus.CANCELLED:
        raise AppError(422, "Cannot plan a dispatch for a cancelled purchase order")
    if not item.is_active:
        raise AppError(422, f"{item.name} is inactive and cannot be planned for dispatch")

    available = line.quantity - dispatched - planned
    if payload.quantity > available:
        raise AppError(
            422,
            f"Planned quantity exceeds the available PO balance. Available to plan: {format_quantity(available)}",
        )

    plan = DispatchPlan(
        po_line_id=line.id,
        item_id=item.id,
        planned_date=payload.planned_date,
        quantity=payload.quantity,
        fulfilled_quantity=ZERO,
        priority=payload.priority,
        status=PlanStatus.PLANNED,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    planned, dispatched = get_line_metrics(db, [line.id]).get(line.id, (ZERO, ZERO))
    return _plan_out(plan, line, po, item, planned, dispatched)


def get_dispatch_plan(db: Session, plan_id: int) -> DispatchPlanOut:
    row = db.execute(
        select(DispatchPlan, POLine, PurchaseOrder, Item)
        .join(POLine, POLine.id == DispatchPlan.po_line_id)
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(DispatchPlan.id == plan_id)
    ).first()
    if row is None:
        raise AppError(404, "Dispatch plan not found")

    plan, line, po, item = row
    planned, dispatched = get_line_metrics(db, [line.id]).get(line.id, (ZERO, ZERO))
    return _plan_out(plan, line, po, item, planned, dispatched)


def update_dispatch_plan(
    db: Session, plan_id: int, payload: DispatchPlanUpdate
) -> DispatchPlanOut:
    plan = db.get(DispatchPlan, plan_id)
    if plan is None:
        raise AppError(404, "Dispatch plan not found")
    if plan.status == PlanStatus.DONE:
        raise AppError(422, "Completed dispatch plans cannot be edited")

    line, po, _, _, _ = _line_context(db, plan.po_line_id)
    if po.status == POStatus.CANCELLED:
        raise AppError(422, "Cannot edit a plan for a cancelled purchase order")

    changes = payload.model_dump(exclude_unset=True)
    planned, dispatched = get_line_metrics(db, [line.id]).get(line.id, (ZERO, ZERO))
    plan_remaining = plan.quantity - plan.fulfilled_quantity
    planned_others = planned - plan_remaining
    available = line.quantity - dispatched - planned_others

    new_quantity = changes.get("quantity", plan.quantity)
    if new_quantity < plan.fulfilled_quantity:
        raise AppError(
            422,
            f"Planned quantity cannot be less than the already dispatched quantity ({format_quantity(plan.fulfilled_quantity)})",
        )
    if new_quantity > available:
        raise AppError(
            422,
            f"Planned quantity exceeds the available PO balance. Available to plan: {format_quantity(available)}",
        )

    for field, value in changes.items():
        setattr(plan, field, value)

    if plan.fulfilled_quantity >= plan.quantity:
        plan.status = PlanStatus.DONE
    elif plan.fulfilled_quantity > 0:
        plan.status = PlanStatus.PARTIAL
    else:
        plan.status = PlanStatus.PLANNED

    db.commit()
    return get_dispatch_plan(db, plan.id)


def delete_dispatch_plan(db: Session, plan_id: int) -> DispatchPlan:
    plan = db.get(DispatchPlan, plan_id)
    if plan is None:
        raise AppError(404, "Dispatch plan not found")
    if plan.status != PlanStatus.PLANNED:
        raise AppError(422, "Only plans that have not started dispatching can be deleted")

    db.delete(plan)
    db.commit()
    return plan


def default_period() -> tuple[date, date]:
    today = date.today()
    start = today.replace(day=1)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month - timedelta(days=1)


def _planned_by_item(date_from: date, date_to: date):
    return (
        select(
            DispatchPlan.item_id.label("item_id"),
            func.sum(DispatchPlan.quantity - DispatchPlan.fulfilled_quantity).label("planned"),
        )
        .where(
            DispatchPlan.planned_date >= date_from,
            DispatchPlan.planned_date <= date_to,
            DispatchPlan.status != PlanStatus.DONE,
        )
        .group_by(DispatchPlan.item_id)
        .subquery()
    )


def get_stock_vs_schedule(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    family: str | None,
    status_filter: ScheduleFilter,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> StockVsSchedulePage:
    if (date_from is None) != (date_to is None):
        raise AppError(422, "Provide both the start and end date for the period")
    if date_from is None or date_to is None:
        date_from, date_to = default_period()
    if date_from > date_to:
        raise AppError(422, "The period start date must be on or before the end date")

    sums = stock_sums_subquery()
    planned_sums = _planned_by_item(date_from, date_to)

    available = func.coalesce(sums.c.available, literal(0))
    planned = func.coalesce(planned_sums.c.planned, literal(0))
    shortfall = case((planned > available, planned - available), else_=literal(0))
    stock_status = case(
        (available < Item.critical_level, literal(StockStatus.CRITICAL.value)),
        (available < Item.reorder_level, literal(StockStatus.BELOW_REORDER.value)),
        else_=literal(StockStatus.OK.value),
    )
    needs_replenishment = or_(shortfall > 0, available < Item.reorder_level)

    filters = [Item.is_active.is_(True)]
    if family:
        filters.append(Item.family == family)

    if status_filter == ScheduleFilter.CRITICAL:
        filters.append(available < Item.critical_level)
    elif status_filter == ScheduleFilter.BELOW_REORDER:
        filters.append(
            and_(available >= Item.critical_level, available < Item.reorder_level)
        )
    elif status_filter == ScheduleFilter.SHORTFALL:
        filters.append(shortfall > 0)
    elif status_filter == ScheduleFilter.REPLENISH:
        filters.append(needs_replenishment)
    elif status_filter == ScheduleFilter.OK:
        filters.append(and_(shortfall == 0, available >= Item.reorder_level))

    base = (
        select(Item.id)
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .outerjoin(planned_sums, planned_sums.c.item_id == Item.id)
        .where(*filters)
    )

    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0

    summary_row = db.execute(
        select(
            func.coalesce(func.sum(case((shortfall > 0, 1), else_=0)), 0),
            func.coalesce(func.sum(shortfall), 0),
            func.coalesce(func.sum(case((available < Item.critical_level, 1), else_=0)), 0),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                available >= Item.critical_level,
                                available < Item.reorder_level,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(case((needs_replenishment, 1), else_=0)), 0),
        )
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .outerjoin(planned_sums, planned_sums.c.item_id == Item.id)
        .where(*filters)
    ).one()

    severity = case(
        (stock_status == StockStatus.CRITICAL.value, 0),
        (stock_status == StockStatus.BELOW_REORDER.value, 1),
        else_=2,
    )
    sort_columns = {
        "name": Item.name,
        "available": available,
        "planned": planned,
        "shortfall": shortfall,
        "status": severity,
    }
    sort_column = sort_columns.get(sort, shortfall)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()

    rows = db.execute(
        select(
            Item.id,
            Item.name,
            Item.family,
            available.label("available"),
            planned.label("planned"),
            shortfall.label("shortfall"),
            Item.reorder_level,
            Item.critical_level,
            stock_status.label("stock_status"),
            needs_replenishment.label("needs_replenishment"),
        )
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .outerjoin(planned_sums, planned_sums.c.item_id == Item.id)
        .where(*filters)
        .order_by(ordering, Item.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for row in rows:
        available_qty = as_decimal(row.available)
        planned_qty = as_decimal(row.planned)
        shortfall_qty = as_decimal(row.shortfall)
        reorder_level = as_decimal(row.reorder_level)
        critical_level = as_decimal(row.critical_level)
        row_status = StockStatus(row.stock_status)

        flags = []
        if shortfall_qty > 0:
            flags.append("SHORTFALL")
        if row_status == StockStatus.CRITICAL:
            flags.append("CRITICAL")
        elif row_status == StockStatus.BELOW_REORDER:
            flags.append("BELOW_REORDER")

        items.append(
            StockVsScheduleRow(
                item_id=row.id,
                name=row.name,
                family=row.family,
                available=available_qty,
                planned_quantity=planned_qty,
                shortfall=shortfall_qty,
                reorder_level=reorder_level,
                critical_level=critical_level,
                stock_status=row_status,
                needs_replenishment=bool(row.needs_replenishment),
                flags=flags,
            )
        )

    summary = ScheduleSummary(
        total_items=total,
        shortfall_items=int(summary_row[0] or 0),
        total_shortfall=as_decimal(summary_row[1]),
        critical=int(summary_row[2] or 0),
        below_reorder=int(summary_row[3] or 0),
        needs_replenishment=int(summary_row[4] or 0),
    )

    return StockVsSchedulePage(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
        date_from=date_from,
        date_to=date_to,
        summary=summary,
    )
