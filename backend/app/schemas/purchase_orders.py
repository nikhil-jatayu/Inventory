from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator

from app.models import POStatus
from app.schemas.common import APIModel, Quantity


class POLineInput(APIModel):
    item_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))


class PurchaseOrderCreate(APIModel):
    po_number: str = Field(min_length=1, max_length=50)
    customer_name: str = Field(min_length=1, max_length=160)
    unit_number: str = Field(min_length=1, max_length=80)
    po_date: date
    lines: list[POLineInput] = Field(min_length=1)

    @field_validator("po_number", "customer_name", "unit_number")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class PurchaseOrderUpdate(APIModel):
    po_number: str | None = Field(default=None, min_length=1, max_length=50)
    customer_name: str | None = Field(default=None, min_length=1, max_length=160)
    unit_number: str | None = Field(default=None, min_length=1, max_length=80)
    po_date: date | None = None
    lines: list[POLineInput] | None = Field(default=None, min_length=1)

    @field_validator("po_number", "customer_name", "unit_number")
    @classmethod
    def strip_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class POLineOut(APIModel):
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
