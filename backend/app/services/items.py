from datetime import date
from decimal import Decimal

from sqlalchemy import func, literal, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Item, StockTransaction, StockTxnType
from app.schemas.common import Page
from app.schemas.items import ItemCreate, ItemOut, ItemUpdate

ITEM_SORT_COLUMNS = {
    "name": Item.name,
    "project": Item.project,
    "family": Item.family,
    "reorder_level": Item.reorder_level,
    "critical_level": Item.critical_level,
    "created_at": Item.created_at,
}


def get_item_out(db: Session, item: Item) -> ItemOut:
    current_inventory = db.scalar(
        select(func.coalesce(func.sum(StockTransaction.quantity), literal(0))).where(
            StockTransaction.item_id == item.id
        )
    ) or ZERO
    result = ItemOut.model_validate(item)
    return result.model_copy(update={"current_inventory": current_inventory})


ZERO = Decimal("0")


def list_items(
    db: Session, *, search: str | None, family: str | None, is_active: bool | None,
    sort: str, order: str, page: int, page_size: int,
) -> Page[ItemOut]:
    filters = []
    if search:
        needle = f"%{search.strip()}%"
        filters.append(Item.name.ilike(needle) | Item.project.ilike(needle) | Item.family.ilike(needle) | Item.model_no.ilike(needle))
    if family:
        filters.append(Item.family == family)
    if is_active is not None:
        filters.append(Item.is_active.is_(is_active))
    total = db.scalar(select(func.count(Item.id)).where(*filters)) or 0
    sort_column = ITEM_SORT_COLUMNS.get(sort, Item.name)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()
    items = db.scalars(select(Item).where(*filters).order_by(ordering, Item.name).offset((page - 1) * page_size).limit(page_size)).all()
    return Page[ItemOut](items=[get_item_out(db, item) for item in items], total=total, page=page, page_size=page_size, pages=max(1, (total + page_size - 1) // page_size))


def list_families(db: Session) -> list[str]:
    return list(db.scalars(select(Item.family).distinct().order_by(Item.family)).all())


def get_item(db: Session, item_id: int) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise AppError(404, "Item not found")
    return item


def _validate_levels(reorder_level: Decimal, critical_level: Decimal) -> None:
    if critical_level > reorder_level:
        raise AppError(422, "Critical level cannot be higher than reorder level")


def _duplicate_item(db: Session, name: str, project: str, exclude_id: int | None = None) -> bool:
    statement = select(Item.id).where(func.lower(Item.name) == name.lower(), func.lower(Item.project) == project.lower())
    if exclude_id is not None:
        statement = statement.where(Item.id != exclude_id)
    return db.scalar(statement) is not None


def create_item(db: Session, payload: ItemCreate) -> Item:
    if _duplicate_item(db, payload.name, payload.project):
        raise AppError(409, "An item with this name already exists in this project")
    _validate_levels(payload.reorder_level, payload.critical_level)
    data = payload.model_dump(exclude={"opening_inventory"})
    item = Item(**data)
    db.add(item)
    try:
        db.flush()
        if payload.opening_inventory > 0:
            db.add(StockTransaction(item_id=item.id, type=StockTxnType.OPENING, quantity=payload.opening_inventory, date=date.today(), ref="ITEM-MASTER", remarks="Opening inventory entered in Item Master"))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "An item with this name already exists in this project") from exc
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, payload: ItemUpdate) -> Item:
    item = get_item(db, item_id)
    changes = payload.model_dump(exclude_unset=True)
    name = changes.get("name", item.name)
    project = changes.get("project", item.project)
    if _duplicate_item(db, name, project, exclude_id=item.id):
        raise AppError(409, "An item with this name already exists in this project")
    reorder_level = changes.get("reorder_level", item.reorder_level)
    critical_level = changes.get("critical_level", item.critical_level)
    _validate_levels(reorder_level, critical_level)
    for field, value in changes.items():
        setattr(item, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "An item with this name already exists in this project") from exc
    db.refresh(item)
    return item
