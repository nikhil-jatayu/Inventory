from datetime import date, datetime
from decimal import Decimal
import re

from pydantic import Field, field_validator, model_validator

from app.models import Priority
from app.schemas.common import APIModel, Quantity


def _clean_rgp(value: str) -> str:
    cleaned = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9/-]{1,80}", cleaned):
        raise ValueError("RGP No. may contain letters, numbers, hyphens and slashes only")
    return cleaned


class PurchaseLineInput(APIModel):
    plan_id: int = Field(gt=0)
    item_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)


class PurchaseCreate(APIModel):
    purchase_date: date = Field(default_factory=date.today)
    lines: list[PurchaseLineInput] = Field(min_length=1, max_length=100)


class PurchaseLineOut(APIModel):
    plan_id: int | None = None
    id: int
    item_id: int
    item_name: str
    project: str
    family: str
    quantity: Quantity


class PurchaseOut(APIModel):
    id: int
    purchase_date: date
    recorded_by: int
    created_at: datetime
    lines: list[PurchaseLineOut]


class PurchasePlanCreate(APIModel):
    item_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)
    planned_date: date
    planned_end_date: date
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("remarks")
    @classmethod
    def strip_remarks(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None

    @model_validator(mode="after")
    def validate_dates(self) -> "PurchasePlanCreate":
        if self.planned_end_date < self.planned_date:
            raise ValueError("Date range end must be on or after the start date")
        return self


class PurchasePlanOut(APIModel):
    received_quantity: Quantity = Decimal(0)
    cancelled_quantity: Quantity = Decimal(0)
    outstanding_quantity: Quantity = Decimal(0)
    status: str = "PLANNED"
    id: int
    item_id: int
    item_name: str
    project: str
    family: str
    quantity: Quantity
    planned_date: date
    planned_end_date: date
    category: Priority
    remarks: str | None
    recorded_by: int


class PurchaseRejectionCreate(APIModel):
    plan_id: int = Field(gt=0)
    rgp_number: str = Field(min_length=1, max_length=80)
    unit_id: int | None = None
    item_id: int
    rejection_date: date = Field(default_factory=date.today)
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("rgp_number")
    @classmethod
    def validate_rgp(cls, value: str) -> str:
        return _clean_rgp(value)

    @field_validator("remarks")
    @classmethod
    def strip_remarks(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class PurchaseRejectionBatchCreate(APIModel):
    rgp_number: str = Field(min_length=1, max_length=80)
    rejection_date: date = Field(default_factory=date.today)
    lines: list[PurchaseLineInput] = Field(min_length=1, max_length=100)

    @field_validator("rgp_number")
    @classmethod
    def validate_batch_rgp(cls, value: str) -> str:
        return _clean_rgp(value)

    @model_validator(mode="after")
    def validate_unique_items(self) -> "PurchaseRejectionBatchCreate":
        item_ids = [line.plan_id for line in self.lines if line.plan_id is not None]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A purchase plan can appear only once within an RGP entry")
        return self


class PurchaseRejectionOut(APIModel):
    plan_id: int | None = None
    batch_id: str | None = None
    id: int
    rgp_number: str
    unit_id: int | None
    unit_name: str | None
    item_id: int
    item_name: str
    project: str
    family: str
    rejection_date: date
    quantity: Quantity
    remarks: str | None
    recorded_by: int


class PurchasePlanCreateBatch(APIModel):
    lines: list[PurchasePlanCreate] = Field(min_length=1, max_length=100)
