from app.services.balances import net_sale, rejected_for_dispatch
from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.fiscal import (
    fiscal_bounds, fiscal_label, fiscal_months, fiscal_start_year,
    month_label, parse_fiscal_year,
)
from app.models import (
    Dispatch, DispatchPlan, Item, PlanStatus, POLine, POStatus, PurchaseOrder,
    SalesRecord, StockTransaction, StockTxnType, Unit,
)
from app.schemas.common import Page
from app.schemas.sales import SalesRecordOut
from app.schemas.dispatches import (
    DispatchBatchCreate, DispatchCreate, DispatchFYTotal, DispatchMonth, DispatchOut, DispatchReport,
)
from app.services.purchase_orders import ZERO, as_decimal, format_quantity, refresh_po_status

DISPATCH_SORT_COLUMNS = {
    "dispatch_date": Dispatch.dispatch_date,
    "quantity": Dispatch.quantity,
    "item": Item.name,
    "po_number": PurchaseOrder.po_number,
}


def _available_stock(db: Session, item_id: int) -> Decimal:
    return as_decimal(db.scalar(
        select(func.coalesce(func.sum(StockTransaction.quantity), literal(0)))
        .where(StockTransaction.item_id == item_id)
    ))


def _ensure_unit(db: Session, unit_id: int | None, fallback_unit_id: int | None = None) -> Unit | None:
    selected_id = unit_id if unit_id is not None else fallback_unit_id
    if selected_id is None:
        return None
    unit = db.get(Unit, selected_id)
    if unit is None or not unit.is_active:
        raise AppError(422, "Select an active dispatch unit")
    return unit


def _create_sales_record(
    db: Session, *, dispatch: Dispatch, plan: DispatchPlan | None,
    po: PurchaseOrder | None, item: Item, unit: Unit | None,
    po_number_reference: str | None = None,
    invoice_number: str | None = None,
) -> SalesRecord:
    sale = SalesRecord(
        dispatch_id=dispatch.id,
        plan_id=plan.id if plan else None,
        # Dispatch IDs are already unique and flushed before this record is created.
        invoice_number=invoice_number or f"INV-{dispatch.id:08d}",
        invoice_date=dispatch.dispatch_date,
        po_number=po.po_number if po else po_number_reference,
        item_id=item.id,
        unit_id=unit.id if unit else None,
        quantity=dispatch.quantity,
    )
    db.add(sale)
    db.flush()
    return sale


def _apply_to_legacy_plans(db: Session, line_id: int, quantity: Decimal) -> None:
    """Compatibility path for dispatches against old PO-linked plans."""
    remaining = quantity
    plans = db.scalars(
        select(DispatchPlan)
        .where(DispatchPlan.po_line_id == line_id, DispatchPlan.status != PlanStatus.DONE)
        .order_by(DispatchPlan.planned_date, DispatchPlan.id)
        .with_for_update()
    ).all()
    for plan in plans:
        outstanding = plan.quantity - plan.fulfilled_quantity
        if outstanding <= 0:
            plan.status = PlanStatus.DONE
            continue
        taken = min(remaining, outstanding)
        plan.fulfilled_quantity += taken
        plan.status = PlanStatus.DONE if plan.fulfilled_quantity >= plan.quantity else PlanStatus.PARTIAL
        remaining -= taken
        if remaining <= 0:
            break


def record_dispatch(db: Session, payload: DispatchCreate, *, commit: bool = True, invoice_number: str | None = None) -> DispatchOut:
    referenced_po = None
    if payload.po_number:
        referenced_po = db.scalar(
            select(PurchaseOrder).where(PurchaseOrder.po_number == payload.po_number)
        )
        if referenced_po is None:
            raise AppError(422, "The PO reference must exist in the Purchase Orders bookkeeping list")

    plan = db.scalar(
        select(DispatchPlan)
        .where(DispatchPlan.id == payload.plan_id)
        .with_for_update()
    )
    if plan is None:
        raise AppError(404, "Dispatch plan not found")
    if plan.status == PlanStatus.DONE:
        raise AppError(422, "This dispatch plan is already complete")

    item = db.scalar(select(Item).where(Item.id == plan.item_id).with_for_update())
    if item is None:
        raise AppError(404, "Item on dispatch plan not found")
    if not item.is_active:
        raise AppError(422, f"{item.name} is inactive and cannot be dispatched")

    outstanding = plan.quantity - plan.fulfilled_quantity
    if payload.quantity > outstanding:
        raise AppError(
            422,
            f"Dispatch quantity exceeds the plan's outstanding quantity. Remaining: {format_quantity(outstanding)}",
        )

    # For plans created under the old PO-driven workflow, retain their original
    # PO relation for history; all new plans have no PO line.
    legacy_po = None
    if plan.po_line_id is not None:
        legacy_line = db.get(POLine, plan.po_line_id)
        legacy_po = db.get(PurchaseOrder, legacy_line.po_id) if legacy_line else None
        if legacy_po is not None and legacy_po.status == POStatus.CANCELLED:
            raise AppError(422, "Cannot dispatch against a cancelled legacy purchase order")

    if legacy_po is not None and invoice_number is not None and legacy_po.po_number != payload.po_number:
        raise AppError(422, "Legacy plan PO must match the invoice reference")
    if plan.unit_id is not None and payload.unit_id is not None and payload.unit_id != plan.unit_id:
        raise AppError(422, "The actual dispatch unit must match the unit on the dispatch plan")
    unit = _ensure_unit(db, payload.unit_id, fallback_unit_id=plan.unit_id)
    if unit is None:
        raise AppError(422, "Select a dispatch unit")

    available = _available_stock(db, item.id)
    if available < payload.quantity:
        raise AppError(422, f"Only {format_quantity(available)} units are available in stock")

    dispatch = Dispatch(
        po_line_id=plan.po_line_id,
        plan_id=plan.id,
        unit_id=unit.id,
        item_id=item.id,
        dispatch_date=payload.dispatch_date,
        quantity=payload.quantity,
        remarks=payload.remarks,
    )
    db.add(dispatch)
    db.flush()

    plan.fulfilled_quantity += payload.quantity
    plan.status = (
        PlanStatus.DONE
        if plan.fulfilled_quantity >= plan.quantity
        else PlanStatus.PARTIAL
    )

    db.add(StockTransaction(
        item_id=item.id,
        type=StockTxnType.DISPATCH,
        quantity=-payload.quantity,
        date=payload.dispatch_date,
        ref=legacy_po.po_number if legacy_po else (referenced_po.po_number if referenced_po else f"PLAN-{plan.id}"),
        remarks=payload.remarks,
    ))
    _create_sales_record(
        db,
        dispatch=dispatch,
        plan=plan,
        po=legacy_po,
        item=item,
        unit=unit,
        po_number_reference=referenced_po.po_number if referenced_po else None,
        invoice_number=invoice_number,
    )
    if legacy_po is not None:
        refresh_po_status(db, legacy_po)

    try:
        db.flush()
        if commit:
            db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "Unable to create the dispatch and corresponding sales record") from exc
    db.refresh(dispatch)
    return _dispatch_out(db, dispatch.id)


def _dispatch_out(db: Session, dispatch_id: int) -> DispatchOut:
    row = db.execute(
        select(Dispatch, POLine, PurchaseOrder, Item, Unit, SalesRecord)
        .outerjoin(POLine, POLine.id == Dispatch.po_line_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == Dispatch.item_id)
        .outerjoin(Unit, Unit.id == Dispatch.unit_id)
        .outerjoin(SalesRecord, SalesRecord.dispatch_id == Dispatch.id)
        .where(Dispatch.id == dispatch_id)
    ).first()
    if row is None:
        raise AppError(404, "Dispatch not found")
    dispatch, line, po, item, unit, sale = row
    return DispatchOut(
        id=dispatch.id, plan_id=dispatch.plan_id, po_line_id=dispatch.po_line_id,
        po_id=po.id if po else None, po_number=po.po_number if po else (sale.po_number if sale else None),
        customer_name=po.customer_name if po else None,
        unit_number=unit.name if unit else (po.unit_number if po else None),
        unit_id=unit.id if unit else None, unit_name=unit.name if unit else None,
        invoice_number=sale.invoice_number if sale else None,
        item_id=item.id, item_name=item.name, item_family=item.family, project=item.project,
        dispatch_date=dispatch.dispatch_date, quantity=dispatch.quantity, remarks=dispatch.remarks,
    )


def list_dispatches(
    db: Session, *, search: str | None, date_from: date | None, date_to: date | None,
    family: str | None, sort: str, order: str, page: int, page_size: int,
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
        filters.append(or_(
            Item.name.ilike(needle), Item.project.ilike(needle),
            PurchaseOrder.po_number.ilike(needle), PurchaseOrder.customer_name.ilike(needle),
            PurchaseOrder.unit_number.ilike(needle), Unit.name.ilike(needle),
            SalesRecord.invoice_number.ilike(needle), Dispatch.remarks.ilike(needle),
        ))
    base = (
        select(Dispatch.id)
        .outerjoin(POLine, POLine.id == Dispatch.po_line_id)
        .outerjoin(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == Dispatch.item_id)
        .outerjoin(Unit, Unit.id == Dispatch.unit_id)
        .outerjoin(SalesRecord, SalesRecord.dispatch_id == Dispatch.id)
        .where(*filters)
    )
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    sort_column = DISPATCH_SORT_COLUMNS.get(sort, Dispatch.dispatch_date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    ids = db.scalars(base.order_by(ordering, Dispatch.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    items = [_dispatch_out(db, dispatch_id) for dispatch_id in ids]
    return Page[DispatchOut](items=items, total=total, page=page, page_size=page_size, pages=max(1, (total + page_size - 1) // page_size))


def list_sales(
    db: Session, *, date_from: date | None = None, date_to: date | None = None,
    family: str | None = None, search: str | None = None, limit: int | None = 200,
) -> list[SalesRecordOut]:
    filters = []
    if date_from and date_to and date_from > date_to:
        raise AppError(422, "The start date must be on or before the end date")
    if date_from:
        filters.append(SalesRecord.invoice_date >= date_from)
    if date_to:
        filters.append(SalesRecord.invoice_date <= date_to)
    if family:
        filters.append(Item.family == family)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(or_(
            SalesRecord.invoice_number.ilike(needle), SalesRecord.po_number.ilike(needle),
            Item.name.ilike(needle), Item.project.ilike(needle), Unit.name.ilike(needle),
        ))
    rows = db.execute(
        select(SalesRecord, Item, Unit, rejected_for_dispatch(SalesRecord.dispatch_id).label("rejected"))
        .join(Item, Item.id == SalesRecord.item_id)
        .outerjoin(Unit, Unit.id == SalesRecord.unit_id)
        .where(*filters)
        .order_by(SalesRecord.invoice_date.desc(), SalesRecord.id.desc())
        .limit(limit)
    ).all()
    return [SalesRecordOut(
        id=sale.id, dispatch_id=sale.dispatch_id, plan_id=sale.plan_id,
        invoice_number=sale.invoice_number, invoice_date=sale.invoice_date,
        po_number=sale.po_number, item_id=item.id, item_name=item.name,
        project=item.project, family=item.family, unit_id=unit.id if unit else None,
        unit_name=unit.name if unit else None, quantity=sale.quantity, rejected_quantity=rejected, net_quantity=sale.quantity-rejected,
    ) for sale, item, unit, rejected in rows]


def _fiscal_year_expression(column):
    month = func.extract("month", column)
    year = func.extract("year", column)
    return case((month >= settings.fy_start_month, year), else_=year - 1)


def get_dispatch_report(db: Session, *, fy: str | None, family: str | None) -> DispatchReport:
    if fy:
        try:
            start_year = parse_fiscal_year(fy)
        except ValueError as exc:
            raise AppError(422, str(exc)) from exc
    else:
        start_year = fiscal_start_year()
    start, end = fiscal_bounds(start_year)
    month_buckets = fiscal_months(start_year)
    family_filters = [Item.family == family] if family else []

    dispatch_year = func.extract("year", Dispatch.dispatch_date)
    dispatch_month = func.extract("month", Dispatch.dispatch_date)
    planned_year = func.extract("year", DispatchPlan.planned_date)
    planned_month = func.extract("month", DispatchPlan.planned_date)
    sales_year = func.extract("year", SalesRecord.invoice_date)
    sales_month = func.extract("month", SalesRecord.invoice_date)

    dispatched_rows = db.execute(
        select(dispatch_year, dispatch_month, func.sum(Dispatch.quantity))
        .select_from(Dispatch).join(Item, Item.id == Dispatch.item_id)
        .where(Dispatch.dispatch_date >= start, Dispatch.dispatch_date <= end, *family_filters)
        .group_by(dispatch_year, dispatch_month)
    ).all()
    planned_rows = db.execute(
        select(planned_year, planned_month, func.sum(DispatchPlan.quantity))
        .select_from(DispatchPlan).join(Item, Item.id == DispatchPlan.item_id)
        .where(DispatchPlan.planned_date >= start, DispatchPlan.planned_date <= end, *family_filters)
        .group_by(planned_year, planned_month)
    ).all()
    sales_rows = db.execute(
        select(sales_year, sales_month, func.sum(net_sale()))
        .select_from(SalesRecord).join(Item, Item.id == SalesRecord.item_id)
        .where(SalesRecord.invoice_date >= start, SalesRecord.invoice_date <= end, *family_filters)
        .group_by(sales_year, sales_month)
    ).all()

    dispatched_by_month = {(int(r[0]), int(r[1])): as_decimal(r[2]) for r in dispatched_rows}
    planned_by_month = {(int(r[0]), int(r[1])): as_decimal(r[2]) for r in planned_rows}
    sales_by_month = {(int(r[0]), int(r[1])): as_decimal(r[2]) for r in sales_rows}
    cumulative = total_dispatched = total_planned = total_sales = ZERO
    month_rows = []
    for bucket in month_buckets:
        key = (bucket.year, bucket.month)
        planned = planned_by_month.get(key, ZERO)
        dispatched = dispatched_by_month.get(key, ZERO)
        sales = sales_by_month.get(key, ZERO)
        total_planned += planned
        total_dispatched += dispatched
        total_sales += sales
        cumulative += dispatched
        month_rows.append(DispatchMonth(
            month=bucket.strftime("%Y-%m"), label=month_label(bucket),
            planned=planned, dispatched=dispatched, sales=sales, cumulative=cumulative,
        ))

    dispatch_count = db.scalar(
        select(func.count(Dispatch.id)).join(Item, Item.id == Dispatch.item_id)
        .where(Dispatch.dispatch_date >= start, Dispatch.dispatch_date <= end, *family_filters)
    ) or 0
    cumulative_dispatched = as_decimal(db.scalar(
        select(func.coalesce(func.sum(Dispatch.quantity), literal(0)))
        .select_from(Dispatch).join(Item, Item.id == Dispatch.item_id)
        .where(Dispatch.dispatch_date <= end, *family_filters)
    ))

    dispatch_fy = _fiscal_year_expression(Dispatch.dispatch_date)
    planned_fy = _fiscal_year_expression(DispatchPlan.planned_date)
    sales_fy = _fiscal_year_expression(SalesRecord.invoice_date)
    dispatch_fy_rows = db.execute(
        select(dispatch_fy, func.sum(Dispatch.quantity)).select_from(Dispatch)
        .join(Item, Item.id == Dispatch.item_id).where(*family_filters).group_by(dispatch_fy)
    ).all()
    planned_fy_rows = db.execute(
        select(planned_fy, func.sum(DispatchPlan.quantity)).select_from(DispatchPlan)
        .join(Item, Item.id == DispatchPlan.item_id).where(*family_filters).group_by(planned_fy)
    ).all()
    sales_fy_rows = db.execute(
        select(sales_fy, func.sum(net_sale())).select_from(SalesRecord)
        .join(Item, Item.id == SalesRecord.item_id).where(*family_filters).group_by(sales_fy)
    ).all()
    totals: dict[int, dict[str, Decimal]] = {}
    for year, quantity in dispatch_fy_rows:
        totals.setdefault(int(year), {"dispatched": ZERO, "planned": ZERO, "sales": ZERO})["dispatched"] = as_decimal(quantity)
    for year, quantity in planned_fy_rows:
        totals.setdefault(int(year), {"dispatched": ZERO, "planned": ZERO, "sales": ZERO})["planned"] = as_decimal(quantity)
    for year, quantity in sales_fy_rows:
        totals.setdefault(int(year), {"dispatched": ZERO, "planned": ZERO, "sales": ZERO})["sales"] = as_decimal(quantity)
    current_year = fiscal_start_year()
    totals.setdefault(start_year, {"dispatched": ZERO, "planned": ZERO, "sales": ZERO})
    fy_totals = [DispatchFYTotal(
        fy=fiscal_label(year), start_year=year,
        dispatched=totals[year]["dispatched"], planned=totals[year]["planned"], sales=totals[year]["sales"],
    ) for year in sorted(totals)]
    fy_options = [fiscal_label(year) for year in sorted(set(totals) | {current_year, start_year}, reverse=True)]
    return DispatchReport(
        fy=fiscal_label(start_year), fy_start=start, fy_end=end, fy_options=fy_options,
        months=month_rows, fy_totals=fy_totals, total_dispatched=total_dispatched,
        total_planned=total_planned, total_sales=total_sales,
        cumulative_dispatched=cumulative_dispatched, dispatch_count=int(dispatch_count),
    )


__all__ = ["get_dispatch_report", "list_dispatches", "list_sales", "record_dispatch"]


def record_dispatch_batch(db: Session, payload: DispatchBatchCreate) -> list[DispatchOut]:
    try:
        # Acquire plan and item locks consistently before processing any line.
        ids = sorted(line.plan_id for line in payload.lines)
        plans = db.scalars(select(DispatchPlan).where(DispatchPlan.id.in_(ids)).order_by(DispatchPlan.id).with_for_update()).all()
        if len(plans) != len(ids):
            raise AppError(404, "One or more dispatch plans no longer exist")
        db.scalars(select(Item).where(Item.id.in_({p.item_id for p in plans})).order_by(Item.id).with_for_update()).all()
        if any(p.po_line_id is not None for p in plans):
            raise AppError(422, "Legacy PO-linked plans must use the original single dispatch workflow")
        result = []
        invoice = None
        today = date.today()
        for line in payload.lines:
            row = record_dispatch(db, DispatchCreate(plan_id=line.plan_id, quantity=line.quantity, unit_id=payload.unit_id, po_number=payload.po_number, dispatch_date=today, remarks=payload.remarks), commit=False, invoice_number=invoice)
            invoice = row.invoice_number
            result.append(row)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
