from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, literal, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Dispatch, DispatchPlan, Item, POLine, POStatus, PlanStatus, PurchaseOrder, PurchaseOrderUnit, Unit
from app.schemas.common import Page
from app.schemas.purchase_orders import (
    POLineInput,
    POLineOption,
    POLineOut,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderSummary,
    PurchaseOrderUpdate,
)

ZERO = Decimal("0")

PO_SORT_COLUMNS = {
    "po_number": PurchaseOrder.po_number,
    "customer_name": PurchaseOrder.customer_name,
    "po_date": PurchaseOrder.po_date,
    "status": PurchaseOrder.status,
}


def as_decimal(value: object) -> Decimal:
    if value is None:
        return ZERO
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def format_quantity(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _planned_subquery():
    """Outstanding planned quantity per PO line (fulfilled plans are excluded)."""
    return (
        select(
            DispatchPlan.po_line_id.label("po_line_id"),
            func.sum(DispatchPlan.quantity - DispatchPlan.fulfilled_quantity).label("planned"),
        )
        .where(DispatchPlan.status != PlanStatus.DONE)
        .group_by(DispatchPlan.po_line_id)
        .subquery()
    )


def _dispatched_subquery():
    return (
        select(
            Dispatch.po_line_id.label("po_line_id"),
            func.sum(Dispatch.quantity).label("dispatched"),
        )
        .group_by(Dispatch.po_line_id)
        .subquery()
    )


def get_line_metrics(
    db: Session, line_ids: Sequence[int] | None = None
) -> dict[int, tuple[Decimal, Decimal]]:
    """Return {po_line_id: (outstanding planned, dispatched)}."""
    if line_ids is not None and not line_ids:
        return {}

    planned = _planned_subquery()
    dispatched = _dispatched_subquery()
    statement = (
        select(
            POLine.id,
            func.coalesce(planned.c.planned, literal(0)),
            func.coalesce(dispatched.c.dispatched, literal(0)),
        )
        .select_from(POLine)
        .outerjoin(planned, planned.c.po_line_id == POLine.id)
        .outerjoin(dispatched, dispatched.c.po_line_id == POLine.id)
    )
    if line_ids is not None:
        statement = statement.where(POLine.id.in_(line_ids))

    return {
        row[0]: (as_decimal(row[1]), as_decimal(row[2])) for row in db.execute(statement).all()
    }


def _line_totals_subquery():
    planned = _planned_subquery()
    dispatched = _dispatched_subquery()
    return (
        select(
            POLine.po_id.label("po_id"),
            func.count(POLine.id).label("line_count"),
            func.sum(POLine.quantity).label("total_quantity"),
            func.sum(func.coalesce(planned.c.planned, literal(0))).label("total_planned"),
            func.sum(func.coalesce(dispatched.c.dispatched, literal(0))).label("total_dispatched"),
        )
        .select_from(POLine)
        .outerjoin(planned, planned.c.po_line_id == POLine.id)
        .outerjoin(dispatched, dispatched.c.po_line_id == POLine.id)
        .group_by(POLine.po_id)
        .subquery()
    )


def list_purchase_orders(
    db: Session,
    *,
    search: str | None,
    status_filter: POStatus | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Page[PurchaseOrderSummary]:
    totals = _line_totals_subquery()

    filters = []
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            PurchaseOrder.po_number.ilike(needle)
            | PurchaseOrder.customer_name.ilike(needle)
            | PurchaseOrder.unit_number.ilike(needle)
        )
    if status_filter:
        filters.append(PurchaseOrder.status == status_filter)

    total = db.scalar(select(func.count(PurchaseOrder.id)).where(*filters)) or 0

    sort_columns = {
        **PO_SORT_COLUMNS,
        "total_quantity": totals.c.total_quantity,
        "total_planned": totals.c.total_planned,
        "total_dispatched": totals.c.total_dispatched,
    }
    sort_column = sort_columns.get(sort, PurchaseOrder.po_date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()

    rows = db.execute(
        select(
            PurchaseOrder,
            func.coalesce(totals.c.line_count, 0),
            func.coalesce(totals.c.total_quantity, literal(0)),
            func.coalesce(totals.c.total_planned, literal(0)),
            func.coalesce(totals.c.total_dispatched, literal(0)),
        )
        .select_from(PurchaseOrder)
        .outerjoin(totals, totals.c.po_id == PurchaseOrder.id)
        .where(*filters)
        .order_by(ordering, PurchaseOrder.po_number)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = []
    for po, line_count, total_quantity, total_planned, total_dispatched in rows:
        quantity = as_decimal(total_quantity)
        dispatched = as_decimal(total_dispatched)
        items.append(
            PurchaseOrderSummary(
                unit_ids=_get_po_unit_ids(db, po.id),
                id=po.id,
                po_number=po.po_number,
                customer_name=po.customer_name,
                unit_number=po.unit_number,
                po_date=po.po_date,
                status=po.status,
                line_count=line_count,
                total_quantity=quantity,
                total_planned=as_decimal(total_planned),
                total_dispatched=dispatched,
                total_balance=quantity - dispatched,
            )
        )

    return Page[PurchaseOrderSummary](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def _validate_unit_ids(db: Session, unit_ids: list[int]) -> None:
    if len(unit_ids) > 100 or len(unit_ids) != len(set(unit_ids)):
        raise AppError(422, "Select up to 100 different units")
    if not unit_ids:
        return
    active_ids = set(db.scalars(
        select(Unit.id).where(Unit.id.in_(unit_ids), Unit.is_active.is_(True))
    ).all())
    if active_ids != set(unit_ids):
        raise AppError(422, "One or more selected units are not active")


def _set_po_units(db: Session, po_id: int, unit_ids: list[int]) -> None:
    _validate_unit_ids(db, unit_ids)
    db.query(PurchaseOrderUnit).filter(PurchaseOrderUnit.po_id == po_id).delete(synchronize_session=False)
    for unit_id in unit_ids:
        db.add(PurchaseOrderUnit(po_id=po_id, unit_id=unit_id))


def _get_po_unit_ids(db: Session, po_id: int) -> list[int]:
    return list(db.scalars(
        select(PurchaseOrderUnit.unit_id)
        .where(PurchaseOrderUnit.po_id == po_id)
        .order_by(PurchaseOrderUnit.unit_id)
    ).all())


def get_purchase_order(db: Session, po_id: int) -> PurchaseOrderOut:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise AppError(404, "Purchase order not found")

    rows = db.execute(
        select(POLine, Item)
        .join(Item, Item.id == POLine.item_id)
        .where(POLine.po_id == po_id)
        .order_by(Item.name)
    ).all()
    metrics = get_line_metrics(db, [line.id for line, _ in rows])

    lines: list[POLineOut] = []
    total_quantity = ZERO
    total_planned = ZERO
    total_dispatched = ZERO
    for line, item in rows:
        planned, dispatched = metrics.get(line.id, (ZERO, ZERO))
        balance = line.quantity - dispatched
        total_quantity += line.quantity
        total_planned += planned
        total_dispatched += dispatched
        lines.append(
            POLineOut(
                project=item.project,
                id=line.id,
                item_id=item.id,
                item_name=item.name,
                item_family=item.family,
                quantity=line.quantity,
                planned_quantity=planned,
                dispatched_quantity=dispatched,
                balance_quantity=balance,
                available_to_plan=balance - planned,
            )
        )

    return PurchaseOrderOut(
        id=po.id,
        po_number=po.po_number,
        customer_name=po.customer_name,
        unit_number=po.unit_number,
        po_date=po.po_date,
        status=po.status,
        line_count=len(lines),
        total_quantity=total_quantity,
        total_planned=total_planned,
        total_dispatched=total_dispatched,
        total_balance=total_quantity - total_dispatched,
        unit_ids=_get_po_unit_ids(db, po.id),
        lines=lines,
    )


def list_po_lines(
    db: Session,
    *,
    search: str | None,
    available_only: bool,
    balance_only: bool,
    limit: int,
) -> list[POLineOption]:
    planned = _planned_subquery()
    dispatched = _dispatched_subquery()
    planned_quantity = func.coalesce(planned.c.planned, literal(0))
    dispatched_quantity = func.coalesce(dispatched.c.dispatched, literal(0))
    balance = POLine.quantity - dispatched_quantity
    available_to_plan = balance - planned_quantity

    filters = [PurchaseOrder.status != POStatus.CANCELLED, Item.is_active.is_(True)]
    if search:
        needle = f"%{search.strip()}%"
        filters.append(
            PurchaseOrder.po_number.ilike(needle)
            | PurchaseOrder.customer_name.ilike(needle)
            | PurchaseOrder.unit_number.ilike(needle)
            | Item.name.ilike(needle)
        )
    if available_only:
        filters.append(available_to_plan > 0)
    if balance_only:
        filters.append(balance > 0)

    rows = db.execute(
        select(
            POLine,
            PurchaseOrder,
            Item,
            planned_quantity,
            dispatched_quantity,
        )
        .join(PurchaseOrder, PurchaseOrder.id == POLine.po_id)
        .join(Item, Item.id == POLine.item_id)
        .outerjoin(planned, planned.c.po_line_id == POLine.id)
        .outerjoin(dispatched, dispatched.c.po_line_id == POLine.id)
        .where(*filters)
        .order_by(PurchaseOrder.po_date, PurchaseOrder.po_number, Item.name)
        .limit(limit)
    ).all()

    options: list[POLineOption] = []
    for line, po, item, line_planned, line_dispatched in rows:
        planned_qty = as_decimal(line_planned)
        dispatched_qty = as_decimal(line_dispatched)
        balance = line.quantity - dispatched_qty
        options.append(
            POLineOption(
                po_line_id=line.id,
                po_id=po.id,
                po_number=po.po_number,
                customer_name=po.customer_name,
                unit_number=po.unit_number,
                po_date=po.po_date,
                item_id=item.id,
                item_name=item.name,
                item_family=item.family,
                quantity=line.quantity,
                planned_quantity=planned_qty,
                dispatched_quantity=dispatched_qty,
                balance_quantity=balance,
                available_to_plan=balance - planned_qty,
            )
        )
    return options


def _ensure_unique_number(db: Session, po_number: str, exclude_id: int | None = None) -> None:
    statement = select(PurchaseOrder.id).where(
        func.lower(PurchaseOrder.po_number) == po_number.lower()
    )
    if exclude_id is not None:
        statement = statement.where(PurchaseOrder.id != exclude_id)
    if db.scalar(statement):
        raise AppError(409, "A purchase order with this number already exists")


def _items_by_id(db: Session, item_ids: set[int]) -> dict[int, Item]:
    if not item_ids:
        return {}
    items = db.scalars(select(Item).where(Item.id.in_(item_ids))).all()
    return {item.id: item for item in items}


def _validate_line_items(db: Session, lines: list[POLineInput]) -> None:
    item_ids = [line.item_id for line in lines]
    if len(item_ids) != len(set(item_ids)):
        raise AppError(422, "An item can only appear once on a purchase order")

    items = _items_by_id(db, set(item_ids))
    for item_id in item_ids:
        item = items.get(item_id)
        if item is None:
            raise AppError(422, "One of the selected items no longer exists")
        if not item.is_active:
            raise AppError(422, f"{item.name} is inactive and cannot be added to a purchase order")


def create_purchase_order(db: Session, payload: PurchaseOrderCreate) -> PurchaseOrderOut:
    _ensure_unique_number(db, payload.po_number)
    _validate_line_items(db, payload.lines)
    _validate_unit_ids(db, payload.unit_ids)

    po = PurchaseOrder(
        po_number=payload.po_number,
        customer_name=payload.customer_name,
        unit_number=payload.unit_number,
        po_date=payload.po_date,
        status=POStatus.OPEN,
    )
    db.add(po)
    try:
        db.flush()
        _set_po_units(db, po.id, payload.unit_ids)
        for line in payload.lines:
            db.add(POLine(po_id=po.id, item_id=line.item_id, quantity=line.quantity))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "A purchase order with this number already exists") from exc

    db.refresh(po)
    return get_purchase_order(db, po.id)


def _apply_lines(db: Session, po: PurchaseOrder, lines: list[POLineInput]) -> None:
    item_ids = [line.item_id for line in lines]
    if len(item_ids) != len(set(item_ids)):
        raise AppError(422, "An item can only appear once on a purchase order")

    existing = {
        line.item_id: line
        for line in db.scalars(select(POLine).where(POLine.po_id == po.id)).all()
    }
    metrics = get_line_metrics(db, [line.id for line in existing.values()])
    items = _items_by_id(db, set(existing) | set(item_ids))
    seen: set[int] = set()

    for input_line in lines:
        seen.add(input_line.item_id)
        current = existing.get(input_line.item_id)
        if current is None:
            item = items.get(input_line.item_id)
            if item is None:
                raise AppError(422, "One of the selected items no longer exists")
            if not item.is_active:
                raise AppError(422, f"{item.name} is inactive and cannot be added to a purchase order")
            db.add(POLine(po_id=po.id, item_id=input_line.item_id, quantity=input_line.quantity))
            continue

        planned, dispatched = metrics.get(current.id, (ZERO, ZERO))
        committed = planned + dispatched
        if input_line.quantity < committed:
            name = items[current.item_id].name
            raise AppError(
                422,
                f"{name} cannot be reduced below its planned and dispatched quantity ({committed:g})",
            )
        current.quantity = input_line.quantity

    for item_id, line in existing.items():
        if item_id in seen:
            continue
        planned, dispatched = metrics.get(line.id, (ZERO, ZERO))
        if planned or dispatched:
            name = items[item_id].name
            raise AppError(
                422,
                f"{name} has planning or dispatch history and cannot be removed from the purchase order",
            )
        db.delete(line)


def refresh_po_status(db: Session, po: PurchaseOrder) -> None:
    if po.status == POStatus.CANCELLED:
        return

    db.flush()
    rows = db.execute(select(POLine.id, POLine.quantity).where(POLine.po_id == po.id)).all()
    if not rows:
        po.status = POStatus.OPEN
        return

    metrics = get_line_metrics(db, [row[0] for row in rows])
    total_quantity = sum((as_decimal(row[1]) for row in rows), ZERO)
    total_dispatched = sum((metrics.get(row[0], (ZERO, ZERO))[1] for row in rows), ZERO)

    if total_quantity > 0 and total_dispatched >= total_quantity:
        po.status = POStatus.COMPLETED
    elif total_dispatched > 0:
        po.status = POStatus.PARTIAL
    else:
        po.status = POStatus.OPEN


def update_purchase_order(
    db: Session, po_id: int, payload: PurchaseOrderUpdate
) -> PurchaseOrderOut:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise AppError(404, "Purchase order not found")
    if po.status == POStatus.CANCELLED:
        raise AppError(422, "Cancelled purchase orders cannot be edited")

    changes = payload.model_dump(exclude_unset=True)
    if "po_number" in changes:
        _ensure_unique_number(db, changes["po_number"], exclude_id=po.id)

    for field in ("po_number", "customer_name", "unit_number", "po_date"):
        if field in changes:
            setattr(po, field, changes[field])

    if payload.lines is not None:
        _apply_lines(db, po, payload.lines)
    if payload.unit_ids is not None:
        _set_po_units(db, po.id, payload.unit_ids)

    refresh_po_status(db, po)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "A purchase order with this number already exists") from exc

    db.refresh(po)
    return get_purchase_order(db, po.id)


def cancel_purchase_order(db: Session, po_id: int) -> PurchaseOrder:
    po = db.get(PurchaseOrder, po_id)
    if po is None:
        raise AppError(404, "Purchase order not found")
    if po.status == POStatus.CANCELLED:
        return po

    rows = db.execute(select(POLine.id).where(POLine.po_id == po.id)).all()
    metrics = get_line_metrics(db, [row[0] for row in rows])
    total_planned = sum((value[0] for value in metrics.values()), ZERO)
    total_dispatched = sum((value[1] for value in metrics.values()), ZERO)

    if total_dispatched > 0:
        raise AppError(422, "Purchase orders with recorded dispatches cannot be cancelled")
    if total_planned > 0:
        raise AppError(422, "Remove or complete the outstanding dispatch plans before cancelling")

    po.status = POStatus.CANCELLED
    db.commit()
    db.refresh(po)
    return po


__all__ = [
    "as_decimal",
    "cancel_purchase_order",
    "create_purchase_order",
    "format_quantity",
    "get_line_metrics",
    "get_purchase_order",
    "list_po_lines",
    "list_purchase_orders",
    "refresh_po_status",
    "update_purchase_order",
]
