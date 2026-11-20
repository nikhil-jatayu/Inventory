from datetime import date
from decimal import Decimal

from sqlalchemy import case, func, literal, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Item, StockTransaction, StockTxnType
from app.schemas.common import Page
from app.schemas.stock import StockStatus, StockStatusOut, StockSummary, TransactionCreate, TransactionOut

TX_SORT_COLUMNS = {
    "date": StockTransaction.date,
    "quantity": StockTransaction.quantity,
    "type": StockTransaction.type,
    "item": Item.name,
}


def stock_sums_subquery():
    return (
        select(
            StockTransaction.item_id.label("item_id"),
            func.sum(StockTransaction.quantity).label("available"),
        )
        .group_by(StockTransaction.item_id)
        .subquery()
    )


def _available_column(sums):
    return func.coalesce(sums.c.available, literal(0))


def _status_expression(available):
    return case(
        (available < Item.critical_level, literal(StockStatus.CRITICAL.value)),
        (available < Item.reorder_level, literal(StockStatus.BELOW_REORDER.value)),
        else_=literal(StockStatus.OK.value),
    )


def get_stock_summary(db: Session) -> StockSummary:
    sums = stock_sums_subquery()
    available = _available_column(sums)
    status = _status_expression(available)

    rows = db.execute(
        select(status.label("status"), func.count(Item.id))
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .where(Item.is_active.is_(True))
        .group_by(status)
    ).all()

    counts = {row[0]: row[1] for row in rows}
    critical = counts.get(StockStatus.CRITICAL.value, 0)
    below = counts.get(StockStatus.BELOW_REORDER.value, 0)
    ok = counts.get(StockStatus.OK.value, 0)
    return StockSummary(total_items=critical + below + ok, critical=critical, below_reorder=below, ok=ok)


def list_stock_status(
    db: Session,
    *,
    search: str | None,
    family: str | None,
    status_filter: StockStatus | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Page[StockStatusOut]:
    sums = stock_sums_subquery()
    available = _available_column(sums)
    status = _status_expression(available)

    filters = [Item.is_active.is_(True)]
    if search:
        needle = f"%{search.strip()}%"
        filters.append(Item.name.ilike(needle) | Item.family.ilike(needle))
    if family:
        filters.append(Item.family == family)
    if status_filter:
        filters.append(status == status_filter.value)

    total = (
        db.scalar(
            select(func.count(Item.id))
            .select_from(Item)
            .outerjoin(sums, sums.c.item_id == Item.id)
            .where(*filters)
        )
        or 0
    )

    sort_columns = {
        "name": Item.name,
        "family": Item.family,
        "available": available,
        "status": status,
    }
    if sort == "status":
        # Sort by severity rather than the label's alphabetical order.
        severity = case((status == StockStatus.CRITICAL.value, 0), (status == StockStatus.BELOW_REORDER.value, 1), else_=2)
        sort_column = severity
    else:
        sort_column = sort_columns.get(sort, Item.name)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()

    rows = db.execute(
        select(
            Item.id,
            Item.name,
            Item.family,
            available.label("available"),
            Item.reorder_level,
            Item.critical_level,
            status.label("status"),
        )
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .where(*filters)
        .order_by(ordering, Item.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        StockStatusOut(
            item_id=row.id,
            name=row.name,
            family=row.family,
            available=row.available,
            reorder_level=row.reorder_level,
            critical_level=row.critical_level,
            status=StockStatus(row.status),
        )
        for row in rows
    ]

    return Page[StockStatusOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def list_transactions(
    db: Session,
    *,
    item_id: int | None,
    txn_type: StockTxnType | None,
    date_from: date | None,
    date_to: date | None,
    search: str | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Page[TransactionOut]:
    filters = []
    if item_id:
        filters.append(StockTransaction.item_id == item_id)
    if txn_type:
        filters.append(StockTransaction.type == txn_type)
    if date_from:
        filters.append(StockTransaction.date >= date_from)
    if date_to:
        filters.append(StockTransaction.date <= date_to)
    if search:
        needle = f"%{search.strip()}%"
        filters.append(Item.name.ilike(needle) | StockTransaction.ref.ilike(needle))

    base = select(StockTransaction, Item.name).join(Item, Item.id == StockTransaction.item_id).where(*filters)
    total = (
        db.scalar(
            select(func.count(StockTransaction.id))
            .select_from(StockTransaction)
            .join(Item, Item.id == StockTransaction.item_id)
            .where(*filters)
        )
        or 0
    )

    sort_column = TX_SORT_COLUMNS.get(sort, StockTransaction.date)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    rows = db.execute(
        base.order_by(ordering, StockTransaction.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    items = [
        TransactionOut(
            id=txn.id,
            item_id=txn.item_id,
            item_name=item_name,
            type=txn.type,
            quantity=txn.quantity,
            date=txn.date,
            ref=txn.ref,
            remarks=txn.remarks,
            created_at=txn.created_at,
        )
        for txn, item_name in rows
    ]

    return Page[TransactionOut](
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def create_transaction(db: Session, payload: TransactionCreate) -> TransactionOut:
    if payload.type == StockTxnType.DISPATCH:
        raise AppError(422, "Dispatch entries are created by recording an actual dispatch")
    if payload.type in (StockTxnType.OPENING, StockTxnType.RECEIPT) and payload.quantity < 0:
        raise AppError(422, "Opening stock and receipts must have a positive quantity")

    item = db.scalar(select(Item).where(Item.id == payload.item_id).with_for_update())
    if item is None:
        raise AppError(404, "Item not found")
    if not item.is_active:
        raise AppError(422, "Cannot post stock against an inactive item")

    current = db.scalar(
        select(func.coalesce(func.sum(StockTransaction.quantity), literal(0))).where(
            StockTransaction.item_id == item.id
        )
    ) or Decimal("0")
    if current + payload.quantity < 0:
        raise AppError(422, f"This adjustment would make stock negative. Available: {current}")

    txn = StockTransaction(
        item_id=item.id,
        type=payload.type,
        quantity=payload.quantity,
        date=payload.date or date.today(),
        ref=payload.ref.strip() if payload.ref else None,
        remarks=payload.remarks.strip() if payload.remarks else None,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    return TransactionOut(
        id=txn.id,
        item_id=txn.item_id,
        item_name=item.name,
        type=txn.type,
        quantity=txn.quantity,
        date=txn.date,
        ref=txn.ref,
        remarks=txn.remarks,
        created_at=txn.created_at,
    )
