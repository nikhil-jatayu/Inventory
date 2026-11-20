from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, StockTxnType, User
from app.schemas.common import Page
from app.schemas.stock import (
    StockStatus,
    StockStatusOut,
    StockSummary,
    TransactionCreate,
    TransactionOut,
)
from app.services import stock as stock_service

router = APIRouter(prefix="/stock", tags=["stock"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("/summary", response_model=StockSummary)
def stock_summary(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StockSummary:
    return stock_service.get_stock_summary(db)


@router.get("/status", response_model=Page[StockStatusOut])
def stock_status(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    family: str | None = None,
    status_filter: Annotated[StockStatus | None, Query(alias="status")] = None,
    sort: Annotated[str, Query(pattern="^(name|family|available|status)$")] = "status",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[StockStatusOut]:
    return stock_service.list_stock_status(
        db,
        search=search,
        family=family,
        status_filter=status_filter,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/transactions", response_model=Page[TransactionOut])
def list_transactions(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    item_id: int | None = None,
    txn_type: Annotated[StockTxnType | None, Query(alias="type")] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    search: str | None = None,
    sort: Annotated[str, Query(pattern="^(date|quantity|type|item)$")] = "date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[TransactionOut]:
    return stock_service.list_transactions(
        db,
        item_id=item_id,
        txn_type=txn_type,
        date_from=date_from,
        date_to=date_to,
        search=search,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.post("/transactions", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def create_transaction(
    payload: TransactionCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> TransactionOut:
    return stock_service.create_transaction(db, payload)
