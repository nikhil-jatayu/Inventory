from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.common import Message, Page
from app.schemas.items import ItemCreate, ItemFamilyList, ItemOut, ItemUpdate
from app.services import items as item_service

router = APIRouter(prefix="/items", tags=["items"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("", response_model=Page[ItemOut])
def list_items(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    family: str | None = None,
    is_active: bool | None = None,
    sort: Annotated[str, Query(pattern="^(name|family|reorder_level|critical_level|created_at)$")] = "name",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[ItemOut]:
    return item_service.list_items(
        db,
        search=search,
        family=family,
        is_active=is_active,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/families", response_model=ItemFamilyList)
def list_families(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ItemFamilyList:
    return ItemFamilyList(families=item_service.list_families(db))


@router.post("", response_model=ItemOut, status_code=status.HTTP_201_CREATED)
def create_item(
    payload: ItemCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> ItemOut:
    return ItemOut.model_validate(item_service.create_item(db, payload))


@router.patch("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> ItemOut:
    return ItemOut.model_validate(item_service.update_item(db, item_id, payload))


@router.delete("/{item_id}", response_model=Message)
def deactivate_item(
    item_id: int,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> Message:
    item = item_service.get_item(db, item_id)
    item_service.update_item(db, item_id, ItemUpdate(is_active=False))
    return Message(message=f"{item.name} deactivated")
