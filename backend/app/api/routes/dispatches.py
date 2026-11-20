from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.dispatches import DispatchCreate, DispatchOut, DispatchReport
from app.services import dispatches as dispatch_service

router = APIRouter(tags=["dispatches"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("/dispatches", response_model=Page[DispatchOut])
def list_dispatches(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    family: str | None = None,
    sort: Annotated[
        str, Query(pattern="^(dispatch_date|quantity|item|po_number)$")
    ] = "dispatch_date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[DispatchOut]:
    return dispatch_service.list_dispatches(
        db,
        search=search,
        date_from=date_from,
        date_to=date_to,
        family=family,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/dispatches", response_model=DispatchOut, status_code=status.HTTP_201_CREATED
)
def record_dispatch(
    payload: DispatchCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> DispatchOut:
    return dispatch_service.record_dispatch(db, payload)


@router.get("/reports/dispatch", response_model=DispatchReport)
def dispatch_report(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fy: str | None = None,
    family: str | None = None,
) -> DispatchReport:
    return dispatch_service.get_dispatch_report(db, fy=fy, family=family)
