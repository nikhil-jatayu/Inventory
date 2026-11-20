from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.users import UserCreate, UserListItem, UserUpdate
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["users"])
AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]


@router.get("", response_model=Page[UserListItem])
def list_users(
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[UserListItem]:
    return user_service.list_users(db, search, page, page_size)


@router.post("", response_model=UserListItem, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    _: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    return UserListItem.model_validate(user_service.create_user(db, payload))


@router.patch("/{user_id}", response_model=UserListItem)
def update_user(
    user_id: int,
    payload: UserUpdate,
    actor: AdminUser,
    db: Annotated[Session, Depends(get_db)],
) -> UserListItem:
    return UserListItem.model_validate(user_service.update_user(db, actor, user_id, payload))
