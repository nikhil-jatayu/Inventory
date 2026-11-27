from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.models import POStatus
from app.schemas.common import APIModel, Quantity


class POLineInput(APIModel):
    item_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))


class PurchaseOrderCreate(APIModel):
    po_number: str = Field(min_length=8, max_length=8, pattern=r"^[0-9]{8}$")
    customer_name: str = Field(default="", max_length=160)
    unit_number: str = Field(default="", max_length=80)
    po_date: date
    unit_ids: list[int] = Field(default_factory=list, max_length=100)
    lines: list[POLineInput] = Field(min_length=1)

    @field_validator("po_number", "customer_name", "unit_number")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("unit_ids")
    @classmethod
    def validate_units(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)):
            raise ValueError("A unit can only be selected once on a purchase order")
        return values


class PurchaseOrderUpdate(APIModel):
    po_number: str | None = Field(default=None, min_length=8, max_length=8, pattern=r"^[0-9]{8}$")
    customer_name: str | None = Field(default=None, max_length=160)
    unit_number: str | None = Field(default=None, max_length=80)
    po_date: date | None = None
    unit_ids: list[int] | None = Field(default=None, max_length=100)
    lines: list[POLineInput] | None = Field(default=None, min_length=1)

    @field_validator("po_number", "customer_name", "unit_number")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None

    @field_validator("unit_ids")
    @classmethod
    def validate_units(cls, values: list[int] | None) -> list[int] | None:
        if values is not None and len(values) != len(set(values)):
            raise ValueError("A unit can only be selected once on a purchase order")
        return values


class POLineOut(APIModel):
    project: str
    id: int
    item_id: int
    item_name: str
    item_family: str
    quantity: Quantity
    planned_quantity: Quantity
    dispatched_quantity: Quantity
    balance_quantity: Quantity
    available_to_plan: Quantity


class PurchaseOrderSummary(APIModel):
    unit_ids: list[int] = Field(default_factory=list)
    id: int
    po_number: str
    customer_name: str
    unit_number: str
    po_date: date
    status: POStatus
    line_count: int
    total_quantity: Quantity
    total_planned: Quantity
    total_dispatched: Quantity
    total_balance: Quantity


class PurchaseOrderOut(PurchaseOrderSummary):
    unit_ids: list[int] = Field(default_factory=list)
    lines: list[POLineOut]


class POLineOption(APIModel):
    po_line_id: int
    po_id: int
    po_number: str
    customer_name: str
    unit_number: str
    po_date: date
    item_id: int
    item_name: str
    item_family: str
    quantity: Quantity
    planned_quantity: Quantity
    dispatched_quantity: Quantity
    balance_quantity: Quantity
    available_to_plan: Quantity
