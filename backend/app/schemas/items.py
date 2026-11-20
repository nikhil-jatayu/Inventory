from datetime import datetime
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel, Quantity


class ItemCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)
    family: str = Field(min_length=1, max_length=80)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999"))
    critical_level: Decimal = Field(default=Decimal("0"), ge=0, le=Decimal("9999999999"))

    @field_validator("name", "family")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @model_validator(mode="after")
    def validate_levels(self) -> "ItemCreate":
        if self.critical_level > self.reorder_level:
            raise ValueError("Critical level cannot be higher than reorder level")
        return self


class ItemUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    family: str | None = Field(default=None, min_length=1, max_length=80)
    reorder_level: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    critical_level: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999"))
    is_active: bool | None = None

    @field_validator("name", "family")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class ItemOut(APIModel):
    id: int
    name: str
    family: str
    reorder_level: Quantity
    critical_level: Quantity
    is_active: bool
    created_at: datetime


class ItemFamilyList(APIModel):
    families: list[str]
