from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.users import UserCreate, UserListItem, UserUpdate


def authenticate(db: Session, username: str, password: str) -> User:
    user = db.scalar(select(User).where(func.lower(User.username) == username.strip().lower()))
    if user is None or not verify_password(password, user.hashed_password):
        raise AppError(401, "Incorrect username or password")
    if not user.is_active:
        raise AppError(403, "This account is inactive. Contact an administrator.")
    return user


def list_users(db: Session, search: str | None, page: int, page_size: int) -> Page[UserListItem]:
    filters = []
    if search:
        needle = f"%{search.strip()}%"
        filters.append(User.username.ilike(needle) | User.full_name.ilike(needle))

    total = db.scalar(select(func.count(User.id)).where(*filters)) or 0
    users = db.scalars(
        select(User).where(*filters).order_by(User.username).offset((page - 1) * page_size).limit(page_size)
    ).all()

    return Page[UserListItem](
        items=[UserListItem.model_validate(user) for user in users],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, (total + page_size - 1) // page_size),
    )


def create_user(db: Session, payload: UserCreate) -> User:
    existing = db.scalar(select(User).where(func.lower(User.username) == payload.username))
    if existing:
        raise AppError(409, "Username is already taken")

    user = User(
        username=payload.username,
        full_name=payload.full_name.strip(),
        hashed_password=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "Username is already taken") from exc
    db.refresh(user)
    return user


def update_user(db: Session, actor: User, user_id: int, payload: UserUpdate) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise AppError(404, "User not found")

    changes = payload.model_dump(exclude_unset=True)

    if user.id == actor.id:
        if changes.get("is_active") is False:
            raise AppError(400, "You cannot deactivate your own account")
        if "role" in changes and changes["role"] != actor.role:
            raise AppError(400, "You cannot change your own role")

    losing_admin = user.role == Role.ADMIN and (
        changes.get("role", Role.ADMIN) != Role.ADMIN or changes.get("is_active", True) is False
    )
    if losing_admin:
        other_admins = db.scalar(
            select(func.count(User.id)).where(
                User.role == Role.ADMIN, User.is_active.is_(True), User.id != user.id
            )
        )
        if not other_admins:
            raise AppError(400, "At least one active administrator is required")

    if "full_name" in changes:
        user.full_name = changes["full_name"].strip()
    if "role" in changes:
        user.role = changes["role"]
    if "is_active" in changes:
        user.is_active = changes["is_active"]
    if changes.get("password"):
        user.hashed_password = hash_password(changes["password"])

    db.commit()
    db.refresh(user)
    return user
