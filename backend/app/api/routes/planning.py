from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import PlanStatus, Priority, Role, User
from app.schemas.common import Message
from app.schemas.planning import (
    GanttPlan,
    DispatchPlanCreate,
    DispatchPlanOut,
    DispatchPlanUpdate,
    PlanningSettingsOut,
    ScheduleFilter,
    StockVsSchedulePage,
)
from app.services import planning as planning_service

router = APIRouter(tags=["planning"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("/planning/settings", response_model=PlanningSettingsOut)
def planning_settings(
    _: Annotated[User, Depends(get_current_user)],
) -> PlanningSettingsOut:
    return planning_service.get_planning_settings()


@router.get("/dispatch-plans", response_model=list[DispatchPlanOut])
def list_dispatch_plans(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    priority: Priority | None = None,
    status_filter: Annotated[PlanStatus | None, Query(alias="status")] = None,
    search: str | None = None,
) -> list[DispatchPlanOut]:
    return planning_service.list_dispatch_plans(
        db,
        date_from=date_from,
        date_to=date_to,
        priority=priority,
        status_filter=status_filter,
        search=search,
    )


@router.post(
    "/dispatch-plans", response_model=DispatchPlanOut, status_code=status.HTTP_201_CREATED
)
def create_dispatch_plan(
    payload: DispatchPlanCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> DispatchPlanOut:
    return planning_service.create_dispatch_plan(db, payload)


@router.patch("/dispatch-plans/{plan_id}", response_model=DispatchPlanOut)
def update_dispatch_plan(
    plan_id: int,
    payload: DispatchPlanUpdate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> DispatchPlanOut:
    return planning_service.update_dispatch_plan(db, plan_id, payload)


@router.delete("/dispatch-plans/{plan_id}", response_model=Message)
def delete_dispatch_plan(
    plan_id: int,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> Message:
    planning_service.delete_dispatch_plan(db, plan_id)
    return Message(message="Dispatch plan deleted")


@router.get("/stock-vs-schedule", response_model=StockVsSchedulePage)
def stock_vs_schedule(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    date_from: date | None = None,
    date_to: date | None = None,
    family: str | None = None,
    status_filter: Annotated[ScheduleFilter, Query(alias="status")] = ScheduleFilter.ALL,
    sort: Annotated[
        str, Query(pattern="^(name|available|planned|shortfall|status)$")
    ] = "shortfall",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 25,
) -> StockVsSchedulePage:
    return planning_service.get_stock_vs_schedule(
        db,
        date_from=date_from,
        date_to=date_to,
        family=family,
        status_filter=status_filter,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.get("/dispatch-gantt", response_model=list[GanttPlan])
def dispatch_gantt(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    date_from: date, date_to: date,
    family: str | None = None, priority: Priority | None = None,
    status_filter: Annotated[PlanStatus | None, Query(alias="status")] = None,
    search: str | None = None,
) -> list[GanttPlan]:
    return planning_service.list_gantt_plans(db, date_from=date_from, date_to=date_to,
        family=family, priority=priority, status_filter=status_filter, search=search)


from app.schemas.planning import DispatchPlanCreateBatch

@router.post("/dispatch-plans/batch", response_model=list[DispatchPlanOut], status_code=201)
def create_plan_batch(payload: DispatchPlanCreateBatch, _: Writer, db: Annotated[Session, Depends(get_db)]) -> list[DispatchPlanOut]:
    return planning_service.create_plan_batch(db, payload)
