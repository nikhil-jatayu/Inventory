from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Item
from app.schemas.common import Page
from app.schemas.items import ItemCreate, ItemOut, ItemUpdate

ITEM_SORT_COLUMNS = {
    "name": Item.name,
    "family": Item.family,
    "reorder_level": Item.reorder_level,
    "critical_level": Item.critical_level,
    "created_at": Item.created_at,
}


def list_items(
    db: Session,
    *,
    search: str | None,
    family: str | None,
    is_active: bool | None,
    sort: str,
    order: str,
    page: int,
    page_size: int,
) -> Page[ItemOut]:
    filters = []
    if search:
        needle = f"%{search.strip()}%"
        filters.append(Item.name.ilike(needle) | Item.family.ilike(needle))
    if family:
        filters.append(Item.family == family)
    if is_active is not None:
        filters.append(Item.is_active.is_(is_active))

    total = db.scalar(select(func.count(Item.id)).where(*filters)) or 0
    sort_column = ITEM_SORT_COLUMNS.get(sort, Item.name)
    ordering = sort_column.desc() if order == "desc" else sort_column.asc()

    items = db.scalars(
        select(Item)
        .where(*filters)
        .order_by(ordering, Item.name)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()

    return Page[ItemOut](
        items=[ItemOut.model_validate(item) for item in items],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


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


def create_item(db: Session, payload: ItemCreate) -> Item:
    if db.scalar(select(Item.id).where(func.lower(Item.name) == payload.name.lower())):
        raise AppError(409, "An item with this name already exists")

    _validate_levels(payload.reorder_level, payload.critical_level)
    item = Item(**payload.model_dump())
    db.add(item)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "An item with this name already exists") from exc
    db.refresh(item)
    return item


def update_item(db: Session, item_id: int, payload: ItemUpdate) -> Item:
    item = get_item(db, item_id)
    changes = payload.model_dump(exclude_unset=True)

    if "name" in changes and changes["name"].lower() != item.name.lower():
        if db.scalar(select(Item.id).where(func.lower(Item.name) == changes["name"].lower(), Item.id != item.id)):
            raise AppError(409, "An item with this name already exists")

    reorder_level = changes.get("reorder_level", item.reorder_level)
    critical_level = changes.get("critical_level", item.critical_level)
    _validate_levels(reorder_level, critical_level)

    for field, value in changes.items():
        setattr(item, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "An item with this name already exists") from exc
    db.refresh(item)
    return item
