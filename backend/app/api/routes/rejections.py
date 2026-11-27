from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.common import Message, Page
from app.schemas.rejections import (
    RejectionBatchCreate,
    RejectionCreate,
    RejectionIssueCreate,
    RejectionIssueList,
    RejectionIssueOut,
    RejectionIssueUpdate,
    RejectionOut,
    RejectionReport,
)
from app.services import rejections as rejection_service

router = APIRouter(tags=["rejections"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.QUALITY))]


@router.get("/rejections", response_model=Page[RejectionOut])
def list_rejections(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    search: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    family: str | None = None,
    issue_id: int | None = None,
    unit_id: int | None = None,
    sort: Annotated[
        str, Query(pattern="^(rejection_date|quantity|item|issue)$")
    ] = "rejection_date",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=5, le=100)] = 20,
) -> Page[RejectionOut]:
    return rejection_service.list_rejections(
        db,
        search=search,
        date_from=date_from,
        date_to=date_to,
        family=family,
        issue_id=issue_id, unit_id=unit_id,
        sort=sort,
        order=order,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/rejections", response_model=RejectionOut, status_code=status.HTTP_201_CREATED
)
def record_rejection(
    payload: RejectionCreate,
    user: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> RejectionOut:
    return rejection_service.record_rejection(db, payload, recorded_by=user)


@router.post("/rejections/batch", response_model=list[RejectionOut], status_code=status.HTTP_201_CREATED)
def record_rejection_batch(
    payload: RejectionBatchCreate,
    user: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> list[RejectionOut]:
    return rejection_service.record_rejection_batch(db, payload, recorded_by=user)


@router.get("/rejection-issues", response_model=RejectionIssueList, deprecated=True)
def list_rejection_issues(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = False,
) -> RejectionIssueList:
    return rejection_service.list_issues(db, include_inactive=include_inactive)


@router.post(
    "/rejection-issues",
    response_model=RejectionIssueOut,
    status_code=status.HTTP_201_CREATED,
)
def create_rejection_issue(
    payload: RejectionIssueCreate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> RejectionIssueOut:
    return rejection_service.create_issue(db, payload)


@router.patch("/rejection-issues/{issue_id}", response_model=RejectionIssueOut)
def update_rejection_issue(
    issue_id: int,
    payload: RejectionIssueUpdate,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> RejectionIssueOut:
    return rejection_service.update_issue(db, issue_id, payload)


@router.delete("/rejection-issues/{issue_id}", response_model=Message)
def deactivate_rejection_issue(
    issue_id: int,
    _: Writer,
    db: Annotated[Session, Depends(get_db)],
) -> Message:
    issue = rejection_service.deactivate_issue(db, issue_id)
    return Message(message=f"{issue.name} deactivated")


@router.get("/reports/rejections", response_model=RejectionReport, deprecated=True)
def rejection_report(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    fy: str | None = None,
    family: str | None = None,
) -> RejectionReport:
    return rejection_service.get_rejection_report(db, fy=fy, family=family)

@router.get('/rejections/eligible-dispatches')
def eligible_dispatches(_: Writer, db: Annotated[Session, Depends(get_db)], unit_id: int):
    from sqlalchemy import select
    from app.models import Dispatch, SalesRecord, Item
    from app.services.balances import rejected_for_dispatch
    rejected = rejected_for_dispatch(Dispatch.id)
    rows = db.execute(select(Dispatch, SalesRecord.invoice_number, Item.name, Item.project, rejected)
        .join(SalesRecord, SalesRecord.dispatch_id == Dispatch.id).join(Item, Item.id == Dispatch.item_id)
        .where(Dispatch.unit_id == unit_id, Dispatch.dispatch_date <= date.today(), Dispatch.quantity > rejected)
        .order_by(Dispatch.dispatch_date.desc(), Dispatch.id.desc())).all()
    return [{'id':d.id,'item_id':d.item_id,'item_name':name,'project':project,'invoice_number':invoice,'dispatch_date':d.dispatch_date,'outstanding_quantity':float(d.quantity-r)} for d,invoice,name,project,r in rows]

@router.get('/rejections/register', response_model=list[RejectionOut])
def rejection_register(_: Annotated[User, Depends(get_current_user)], db: Annotated[Session, Depends(get_db)], date_from: date, date_to: date, unit_id: int | None = None):
    from app.core.errors import AppError
    if not 0 <= (date_to-date_from).days <= 366:
        raise AppError(422, 'Choose a valid period of at most 367 days')
    return rejection_service.list_rejections(db, search=None,date_from=date_from,date_to=date_to,family=None,issue_id=None,unit_id=unit_id,sort='rejection_date',order='desc',page=1,page_size=2_147_483_647).items
