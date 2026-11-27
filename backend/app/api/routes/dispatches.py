from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.common import Page
from app.schemas.dispatches import DispatchCreate, DispatchOut, DispatchReport
from app.schemas.sales import SalesRecordOut
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


@router.get("/sales", response_model=list[SalesRecordOut])
def list_sales(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    family: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> list[SalesRecordOut]:
    return dispatch_service.list_sales(
        db, date_from=date_from, date_to=date_to, family=family, search=search, limit=limit,
    )


@router.get("/reports/dispatch", response_model=DispatchReport)
def dispatch_report(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fy: str | None = None,
    family: str | None = None,
) -> DispatchReport:
    return dispatch_service.get_dispatch_report(db, fy=fy, family=family)


from app.schemas.dispatches import DispatchBatchCreate
from app.core.errors import AppError

@router.post("/dispatches/batch", response_model=list[DispatchOut], status_code=201)
def record_dispatch_batch(payload: DispatchBatchCreate, _: Writer, db: Annotated[Session, Depends(get_db)]) -> list[DispatchOut]:
    return dispatch_service.record_dispatch_batch(db, payload)


@router.get("/sales/month-lines", response_model=list[SalesRecordOut])
def monthly_sales_lines(_: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], date_from: date, date_to: date) -> list[SalesRecordOut]:
    if (date_to - date_from).days not in range(31):
        raise AppError(422, "Select a date range of at most 31 days")
    return dispatch_service.list_sales(db, date_from=date_from, date_to=date_to, limit=None)
