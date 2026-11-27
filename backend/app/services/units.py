from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.models import Unit
from app.schemas.units import UnitCreate, UnitOut, UnitUpdate


def list_units(db: Session, *, include_inactive: bool = False) -> list[UnitOut]:
    query = select(Unit).order_by(Unit.name)
    if not include_inactive:
        query = query.where(Unit.is_active.is_(True))
    return [UnitOut.model_validate(row) for row in db.scalars(query).all()]


def create_unit(db: Session, payload: UnitCreate) -> UnitOut:
    name = payload.name
    existing = db.scalar(select(Unit.id).where(func.lower(Unit.name) == name.lower()))
    if existing:
        raise AppError(409, "A unit with this name already exists")
    unit = Unit(name=name, is_active=True)
    db.add(unit)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "A unit with this name already exists") from exc
    db.refresh(unit)
    return UnitOut.model_validate(unit)


def update_unit(db: Session, unit_id: int, payload: UnitUpdate) -> UnitOut:
    unit = db.get(Unit, unit_id)
    if unit is None:
        raise AppError(404, "Unit not found")
    if not payload.is_active:
        # Existing history keeps its FK; deactivation only removes it from new forms.
        unit.is_active = False
    else:
        unit.is_active = True
    db.commit()
    db.refresh(unit)
    return UnitOut.model_validate(unit)
