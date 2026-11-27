from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.purchases import (
    PurchaseCreate, PurchaseOut, PurchasePlanCreate, PurchasePlanOut,
    PurchaseRejectionBatchCreate, PurchaseRejectionCreate, PurchaseRejectionOut,
)
from app.services import purchases as purchase_service

router = APIRouter(tags=["client purchase workflows"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("/purchases", response_model=list[PurchaseOut])
def list_purchases(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[PurchaseOut]:
    return purchase_service.list_purchases(db, limit=limit)


@router.post("/purchases", response_model=PurchaseOut, status_code=status.HTTP_201_CREATED)
def create_purchase(payload: PurchaseCreate, user: Writer, db: Annotated[Session, Depends(get_db)]) -> PurchaseOut:
    return purchase_service.create_purchase(db, payload, recorded_by=user)


@router.get("/purchase-plans", response_model=list[PurchasePlanOut])
def list_purchase_plans(_: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)]) -> list[PurchasePlanOut]:
    return purchase_service.list_purchase_plans(db)


@router.post("/purchase-plans", response_model=PurchasePlanOut, status_code=status.HTTP_201_CREATED)
def create_purchase_plan(payload: PurchasePlanCreate, user: Writer, db: Annotated[Session, Depends(get_db)]) -> PurchasePlanOut:
    return purchase_service.create_purchase_plan(db, payload, recorded_by=user)


@router.post("/purchase-rejections/batch", response_model=list[PurchaseRejectionOut], status_code=status.HTTP_201_CREATED)
def create_purchase_rejection_batch(
    payload: PurchaseRejectionBatchCreate, user: Writer, db: Annotated[Session, Depends(get_db)]
) -> list[PurchaseRejectionOut]:
    return purchase_service.create_purchase_rejection_batch(db, payload, recorded_by=user)


@router.get("/purchase-rejections", response_model=list[PurchaseRejectionOut])
def list_purchase_rejections(_: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], date_from: date | None = None, date_to: date | None = None) -> list[PurchaseRejectionOut]:
    return purchase_service.list_purchase_rejections(db, date_from=date_from, date_to=date_to)


@router.post("/purchase-rejections", response_model=PurchaseRejectionOut, status_code=status.HTTP_201_CREATED)
def create_purchase_rejection(payload: PurchaseRejectionCreate, user: Writer, db: Annotated[Session, Depends(get_db)]) -> PurchaseRejectionOut:
    return purchase_service.create_purchase_rejection(db, payload, recorded_by=user)


from app.schemas.purchases import PurchasePlanCreateBatch

@router.post("/purchase-plans/batch", response_model=list[PurchasePlanOut], status_code=201)
def create_plan_batch(payload: PurchasePlanCreateBatch, user: Writer, db: Annotated[Session, Depends(get_db)]) -> list[PurchasePlanOut]:
    return purchase_service.create_plan_batch(db, payload, recorded_by=user)


@router.patch("/purchase-plans/{plan_id}", response_model=PurchasePlanOut)
def update_purchase_plan(plan_id: int, payload: PurchasePlanCreate, _: Writer, db: Annotated[Session, Depends(get_db)]) -> PurchasePlanOut:
    return purchase_service.update_purchase_plan(db, plan_id, payload)

@router.delete("/purchase-plans/{plan_id}")
def cancel_purchase_plan(plan_id: int, _: Writer, db: Annotated[Session, Depends(get_db)]) -> dict[str, str]:
    purchase_service.cancel_purchase_plan(db, plan_id)
    return {"message": "Purchase plan removed"}
