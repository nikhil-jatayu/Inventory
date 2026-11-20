from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator

from app.schemas.common import APIModel, Quantity


class DispatchCreate(APIModel):
    po_line_id: int
    dispatch_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("remarks")
    @classmethod
    def strip_remarks(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class DispatchOut(APIModel):
    id: int
    po_line_id: int
    po_id: int
    po_number: str
    customer_name: str
    unit_number: str
    item_id: int
    item_name: str
    item_family: str
    dispatch_date: date
    quantity: Quantity
    remarks: str | None


class DispatchMonth(APIModel):
    month: str
    label: str
    planned: Quantity
    dispatched: Quantity
    cumulative: Quantity


class DispatchFYTotal(APIModel):
    fy: str
    start_year: int
    dispatched: Quantity
    planned: Quantity


class DispatchReport(APIModel):
    fy: str
    fy_start: date
    fy_end: date
    fy_options: list[str]
    months: list[DispatchMonth]
    fy_totals: list[DispatchFYTotal]
    total_dispatched: Quantity
    total_planned: Quantity
    cumulative_dispatched: Quantity
    dispatch_count: int
