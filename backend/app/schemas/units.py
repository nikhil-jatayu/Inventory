from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import APIModel


class UnitCreate(APIModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def normalise_name(cls, value: str) -> str:
        return " ".join(value.split())


class UnitUpdate(APIModel):
    is_active: bool


class UnitOut(APIModel):
    id: int
    name: str
    is_active: bool
    created_at: datetime
