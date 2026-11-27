from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models import Role, User
from app.schemas.units import UnitCreate, UnitOut, UnitUpdate
from app.services import units as unit_service

router = APIRouter(prefix="/units", tags=["units"])
Writer = Annotated[User, Depends(require_roles(Role.ADMIN, Role.STORE))]


@router.get("", response_model=list[UnitOut])
def list_units(
    _: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    include_inactive: bool = False,
) -> list[UnitOut]:
    return unit_service.list_units(db, include_inactive=include_inactive)


@router.post("", response_model=UnitOut, status_code=201)
def create_unit(payload: UnitCreate, _: Writer, db: Annotated[Session, Depends(get_db)]) -> UnitOut:
    return unit_service.create_unit(db, payload)


@router.patch("/{unit_id}", response_model=UnitOut)
def update_unit(
    unit_id: int, payload: UnitUpdate, _: Writer, db: Annotated[Session, Depends(get_db)]
) -> UnitOut:
    return unit_service.update_unit(db, unit_id, payload)
