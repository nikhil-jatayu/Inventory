from datetime import date
from decimal import Decimal

from sqlalchemy import select
from uuid import uuid4
from app.services.balances import purchase_balances
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import (
    Item, Priority, Purchase, PurchaseLine, PurchasePlan, PurchaseRejection,
    StockTransaction, StockTxnType, Unit, User,
)
from app.schemas.purchases import (
    PurchaseCreate, PurchaseOut, PurchasePlanCreateBatch, PurchasePlanCreate, PurchasePlanOut,
    PurchaseRejectionBatchCreate, PurchaseRejectionCreate, PurchaseRejectionOut, PurchaseLineOut,
)

ZERO = Decimal("0")


def _active_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise AppError(404, "Item not found")
    if not item.is_active:
        raise AppError(422, f"{item.name} is inactive and cannot be used in a new transaction")
    return item


def _active_unit(db: Session, unit_id: int | None) -> Unit | None:
    if unit_id is None:
        return None
    unit = db.get(Unit, unit_id)
    if unit is None or not unit.is_active:
        raise AppError(422, "Select an active unit")
    return unit


def _lock_plans(db, lines):
    ids = [line.plan_id for line in lines]
    if None in ids or len(set(ids)) != len(ids):
        raise AppError(422, "Select a different purchase plan for each row")
    plans = {p.id: p for p in db.scalars(select(PurchasePlan).where(PurchasePlan.id.in_(ids)).order_by(PurchasePlan.id).with_for_update().execution_options(populate_existing=True)).all()}
    for line in lines:
        plan = plans.get(line.plan_id)
        if plan is None or plan.item_id != line.item_id:
            raise AppError(422, "Purchase plan does not match the item")
        if line.quantity > purchase_balances(db, plan)[2]:
            raise AppError(422, f"Quantity exceeds outstanding balance of purchase plan #{plan.id}")
    return plans


def create_purchase(db: Session, payload: PurchaseCreate, *, recorded_by: User) -> PurchaseOut:
    try:
        _lock_plans(db, payload.lines)
        items = db.scalars(select(Item).where(Item.id.in_({line.item_id for line in payload.lines})).order_by(Item.id).with_for_update()).all()
        if len(items) != len({line.item_id for line in payload.lines}) or any(not item.is_active for item in items):
            raise AppError(422, "All received items must be active")
        if payload.purchase_date > date.today():
            raise AppError(422, "Purchase date cannot be in the future")
        purchase = Purchase(purchase_date=payload.purchase_date, recorded_by=recorded_by.id)
        db.add(purchase)
        db.flush()
        for line in payload.lines:
            db.add(PurchaseLine(purchase_id=purchase.id, plan_id=line.plan_id, item_id=line.item_id, quantity=line.quantity))
            db.add(StockTransaction(item_id=line.item_id, type=StockTxnType.RECEIPT, quantity=line.quantity,
                date=payload.purchase_date, ref=f"PURCHASE-{purchase.id}", remarks=f"Receipt against purchase plan #{line.plan_id}"))
        db.flush()
        result = get_purchase(db, purchase.id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def _purchase_out(db: Session, purchase: Purchase) -> PurchaseOut:
    rows = db.execute(
        select(PurchaseLine, Item).join(Item, Item.id == PurchaseLine.item_id)
        .where(PurchaseLine.purchase_id == purchase.id).order_by(PurchaseLine.id)
    ).all()
    return PurchaseOut(
        id=purchase.id, purchase_date=purchase.purchase_date,
        recorded_by=purchase.recorded_by, created_at=purchase.created_at,
        lines=[PurchaseLineOut(
            id=line.id, plan_id=line.plan_id, item_id=item.id, item_name=item.name, project=item.project,
            family=item.family, quantity=line.quantity,
        ) for line, item in rows],
    )


def get_purchase(db: Session, purchase_id: int) -> PurchaseOut:
    purchase = db.get(Purchase, purchase_id)
    if purchase is None:
        raise AppError(404, "Purchase record not found")
    return _purchase_out(db, purchase)


def list_purchases(db: Session, *, limit: int = 100) -> list[PurchaseOut]:
    rows = db.scalars(select(Purchase).order_by(Purchase.purchase_date.desc(), Purchase.id.desc()).limit(limit)).all()
    return [_purchase_out(db, row) for row in rows]


def _purchase_plan_category(start: date, end: date) -> Priority:
    from app.services.planning import priority_for_range
    return priority_for_range(start, end)


def create_purchase_plan(db: Session, payload: PurchasePlanCreate, *, recorded_by: User, commit: bool = True) -> PurchasePlanOut:
    item = _active_item(db, payload.item_id)
    plan = PurchasePlan(
        item_id=item.id, quantity=payload.quantity, planned_date=payload.planned_date,
        planned_end_date=payload.planned_end_date,
        category=_purchase_plan_category(payload.planned_date, payload.planned_end_date), remarks=payload.remarks,
        recorded_by=recorded_by.id,
    )
    db.add(plan)
    db.flush()
    if commit:
        db.commit()
    db.refresh(plan)
    return _purchase_plan_out(db, plan)


def _purchase_plan_out(db: Session, plan: PurchasePlan) -> PurchasePlanOut:
    item = db.get(Item, plan.item_id)
    if item is None:
        raise AppError(404, "Item for purchase plan not found")
    received, cancelled, outstanding = purchase_balances(db, plan)
    return PurchasePlanOut(
        received_quantity=received, cancelled_quantity=cancelled, outstanding_quantity=outstanding,
        status=("CANCELLED" if cancelled == plan.quantity else "CLOSED" if outstanding == 0 else "PARTIAL" if received or cancelled else "PLANNED"),
        id=plan.id, item_id=item.id, item_name=item.name, project=item.project,
        family=item.family, quantity=plan.quantity, planned_date=plan.planned_date,
        planned_end_date=plan.planned_end_date, category=plan.category,
        remarks=plan.remarks, recorded_by=plan.recorded_by,
    )


def list_purchase_plans(db: Session) -> list[PurchasePlanOut]:
    rows = db.scalars(select(PurchasePlan).order_by(PurchasePlan.planned_date, PurchasePlan.id)).all()
    return [_purchase_plan_out(db, row) for row in rows]


def create_purchase_rejection(db: Session, payload: PurchaseRejectionCreate, *, recorded_by: User) -> PurchaseRejectionOut:
    if payload.unit_id is not None:
        raise AppError(422, "Purchase rejection has no destination unit")
    return create_purchase_rejection_batch(db, PurchaseRejectionBatchCreate(rgp_number=payload.rgp_number, rejection_date=payload.rejection_date, lines=[payload.model_dump()]), recorded_by=recorded_by, remarks=payload.remarks)[0]


def create_purchase_rejection_batch(db: Session, payload: PurchaseRejectionBatchCreate, *, recorded_by: User, remarks=None) -> list[PurchaseRejectionOut]:
    try:
        _lock_plans(db, payload.lines)
        if payload.rejection_date > date.today():
            raise AppError(422, "Rejection date cannot be in the future")
        batch_id = str(uuid4())
        records = [PurchaseRejection(rgp_number=payload.rgp_number, plan_id=line.plan_id, batch_id=batch_id,
            item_id=line.item_id, rejection_date=payload.rejection_date, quantity=line.quantity, recorded_by=recorded_by.id, remarks=remarks) for line in payload.lines]
        db.add_all(records)
        db.flush()
        result = [_purchase_rejection_out(db, record) for record in records]
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def _purchase_rejection_out(db, record):
    item = db.get(Item, record.item_id)
    unit = db.get(Unit, record.unit_id) if record.unit_id else None
    return PurchaseRejectionOut(id=record.id, plan_id=record.plan_id, batch_id=record.batch_id,
        rgp_number=record.rgp_number, unit_id=record.unit_id, unit_name=unit.name if unit else None,
        item_id=item.id, item_name=item.name, project=item.project, family=item.family,
        rejection_date=record.rejection_date, quantity=record.quantity, remarks=record.remarks, recorded_by=record.recorded_by)


def list_purchase_rejections(db: Session, *, date_from: date | None = None, date_to: date | None = None) -> list[PurchaseRejectionOut]:
    filters = []
    if date_from: filters.append(PurchaseRejection.rejection_date >= date_from)
    if date_to: filters.append(PurchaseRejection.rejection_date <= date_to)
    if date_from and date_to and date_from > date_to: raise AppError(422, "Invalid date range")
    rows = db.execute(
        select(PurchaseRejection, Item, Unit)
        .join(Item, Item.id == PurchaseRejection.item_id)
        .outerjoin(Unit, Unit.id == PurchaseRejection.unit_id)
        .where(*filters)
        .order_by(PurchaseRejection.rejection_date.desc(), PurchaseRejection.id.desc())
    ).all()
    return [PurchaseRejectionOut(
        id=record.id, plan_id=record.plan_id, batch_id=record.batch_id, rgp_number=record.rgp_number, unit_id=record.unit_id,
        unit_name=unit.name if unit else None, item_id=item.id, item_name=item.name,
        project=item.project, family=item.family, rejection_date=record.rejection_date,
        quantity=record.quantity, remarks=record.remarks, recorded_by=record.recorded_by,
    ) for record, item, unit in rows]


def create_plan_batch(db: Session, payload: PurchasePlanCreateBatch, *, recorded_by: User) -> list[PurchasePlanOut]:
    try:
        result = [create_purchase_plan(db, line, recorded_by=recorded_by, commit=False) for line in payload.lines]
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise


def update_purchase_plan(db: Session, plan_id: int, payload: PurchasePlanCreate) -> PurchasePlanOut:
    plan = db.scalar(select(PurchasePlan).where(PurchasePlan.id == plan_id).with_for_update())
    if plan is None:
        raise AppError(404, "Purchase plan not found")
    item = _active_item(db, payload.item_id)
    received, cancelled, _ = purchase_balances(db, plan)
    if received or cancelled:
        if item.id != plan.item_id or payload.quantity != plan.quantity or payload.planned_date != plan.planned_date or payload.planned_end_date != plan.planned_end_date:
            raise AppError(422, "A purchase plan with transaction history cannot be rewritten; use Purchase Rejections for cancellations")
    plan.item_id = item.id
    plan.quantity = payload.quantity
    plan.planned_date = payload.planned_date
    plan.planned_end_date = payload.planned_end_date
    plan.category = _purchase_plan_category(payload.planned_date, payload.planned_end_date)
    plan.remarks = payload.remarks
    db.commit()
    return _purchase_plan_out(db, plan)

def cancel_purchase_plan(db: Session, plan_id: int) -> None:
    if db.get(PurchasePlan, plan_id) is None:
        raise AppError(404, "Purchase plan not found")
    raise AppError(422, "Use Add Purchase Rejection with an RGP number to cancel outstanding quantity. Plan history is retained.")
