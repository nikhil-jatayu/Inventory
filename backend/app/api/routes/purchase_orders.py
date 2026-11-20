from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import POStatus, Role, User
from app.schemas.common import Message, Page
from app.schemas.purchase_orders import (
    POLineOption,
    PurchaseOrderCreate,
    PurchaseOrderOut,
    PurchaseOrderSummary,
    PurchaseOrderUpdate,
)
from app.services import purchase_orders as po_service

router = APIRouter(prefix="/purchase-orders", tags=["purchase-orders"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("/lines", response_model=list[POLineOption])
def list_po_lines(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    available_only: bool = True,
    balance_only: bool = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[POLineOption]:
    return po_service.list_po_lines(
        db,
        search=search,
        available_only=available_only,
        balance_only=balance_only,
        limit=limit,
    )


@router.get("", response_model=Page[PurchaseOrderSummary])
def list_purchase_orders(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    status_filter: Annotated[POStatus | None, Query(alias="status")] = None,
    sort: Annotated[
        str,
        Query(
            pattern="^(po_number|customer_name|po_date|status|total_quantity|total_planned|total_dispatched)$"
        ),
    ] = "po_date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[PurchaseOrderSummary]:
    return po_service.list_purchase_orders(
        db,
        search=search,
        status_filter=status_filter,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=PurchaseOrderOut, status_code=status.HTTP_201_CREATED)
def create_purchase_order(
    payload: PurchaseOrderCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderOut:
    return po_service.create_purchase_order(db, payload)


@router.get("/{po_id}", response_model=PurchaseOrderOut)
def get_purchase_order(
    po_id: int,
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderOut:
    return po_service.get_purchase_order(db, po_id)


@router.patch("/{po_id}", response_model=PurchaseOrderOut)
def update_purchase_order(
    po_id: int,
    payload: PurchaseOrderUpdate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> PurchaseOrderOut:
    return po_service.update_purchase_order(db, po_id, payload)


@router.post("/{po_id}/cancel", response_model=Message)
def cancel_purchase_order(
    po_id: int,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> Message:
    po = po_service.cancel_purchase_order(db, po_id)
    return Message(message=f"Purchase order {po.po_number} cancelled")
