from datetime import date
from decimal import Decimal

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel, Quantity


class DispatchCreate(APIModel):
    plan_id: int
    po_number: str | None = Field(default=None, min_length=8, max_length=8, pattern=r"^[0-9]{8}$")
    unit_id: int | None = None
    dispatch_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("remarks")
    @classmethod
    def strip_remarks(cls, value: str | None) -> str | None:
        return value.strip() if value and value.strip() else None


class DispatchOut(APIModel):
    id: int
    plan_id: int | None
    po_line_id: int | None
    po_id: int | None
    po_number: str | None
    customer_name: str | None
    unit_number: str | None
    unit_id: int | None
    unit_name: str | None
    invoice_number: str | None
    item_id: int
    item_name: str
    item_family: str
    project: str
    dispatch_date: date
    quantity: Quantity
    remarks: str | None


class DispatchMonth(APIModel):
    month: str
    label: str
    planned: Quantity
    dispatched: Quantity
    sales: Quantity
    cumulative: Quantity


class DispatchFYTotal(APIModel):
    fy: str
    start_year: int
    dispatched: Quantity
    planned: Quantity
    sales: Quantity


class DispatchReport(APIModel):
    fy: str
    fy_start: date
    fy_end: date
    fy_options: list[str]
    months: list[DispatchMonth]
    fy_totals: list[DispatchFYTotal]
    total_dispatched: Quantity
    total_planned: Quantity
    total_sales: Quantity
    cumulative_dispatched: Quantity
    dispatch_count: int


class DispatchBatchLine(APIModel):
    plan_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)


class DispatchBatchCreate(APIModel):
    po_number: str | None = Field(default=None, pattern=r"^[0-9]{8}$")
    unit_id: int
    remarks: str | None = Field(default=None, max_length=2000)
    lines: list[DispatchBatchLine] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_plans(self):
        if len({line.plan_id for line in self.lines}) != len(self.lines):
            raise ValueError("Each dispatch plan may appear only once per invoice")
        return self
