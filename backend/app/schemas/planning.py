from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import Field, model_validator

from app.models import PlanStatus, Priority
from app.schemas.common import APIModel, Quantity
from app.schemas.stock import StockStatus


class DispatchPlanCreate(APIModel):
    # New dispatch plans are independent of PO bookkeeping.
    item_id: int
    unit_id: int
    planned_date: date
    planned_end_date: date | None = None
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))
    priority: Priority | None = None

    @model_validator(mode="after")
    def validate_date_range(self) -> "DispatchPlanCreate":
        if self.planned_end_date is not None and self.planned_end_date < self.planned_date:
            raise ValueError("Date range end must be on or after the start date")
        return self


class DispatchPlanUpdate(APIModel):
    item_id: int | None = None
    unit_id: int | None = None
    planned_date: date | None = None
    planned_end_date: date | None = None
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("9999999999"))
    priority: Priority | None = None


class DispatchPlanOut(APIModel):
    id: int
    po_line_id: int | None
    po_id: int | None
    po_number: str | None
    customer_name: str | None
    unit_number: str | None
    unit_id: int | None
    unit_name: str | None
    item_id: int
    item_name: str
    item_family: str
    project: str
    planned_date: date
    planned_end_date: date
    quantity: Quantity
    fulfilled_quantity: Quantity
    outstanding_quantity: Quantity
    priority: Priority
    status: PlanStatus
    lead_time_days: int
    days_until: int
    days_until_end: int
    warning: bool
    po_quantity: Quantity
    po_planned: Quantity
    po_dispatched: Quantity
    po_balance: Quantity
    po_available_to_plan: Quantity


class GanttDispatch(APIModel):
    id: int
    dispatch_date: date
    quantity: Quantity


class GanttPlan(DispatchPlanOut):
    actual_dispatches: list[GanttDispatch]


class PlanningSettingsOut(APIModel):
    today: date
    fy_start_month: int
    lead_times: dict[str, int]


class ScheduleFilter(str, Enum):
    ALL = "ALL"
    CRITICAL = "CRITICAL"
    BELOW_REORDER = "BELOW_REORDER"
    SHORTFALL = "SHORTFALL"
    REPLENISH = "REPLENISH"
    OK = "OK"


class StockVsScheduleRow(APIModel):
    item_id: int
    name: str
    project: str
    family: str
    available: Quantity
    planned_quantity: Quantity
    shortfall: Quantity
    reorder_level: Quantity
    critical_level: Quantity
    stock_status: StockStatus
    needs_replenishment: bool
    flags: list[str]


class ScheduleSummary(APIModel):
    total_items: int
    shortfall_items: int
    total_shortfall: Quantity
    critical: int
    below_reorder: int
    needs_replenishment: int


class StockVsSchedulePage(APIModel):
    items: list[StockVsScheduleRow]
    total: int
    page: int
    page_size: int
    pages: int
    date_from: date
    date_to: date
    summary: ScheduleSummary


class DispatchPlanCreateBatch(APIModel):
    lines: list[DispatchPlanCreate] = Field(min_length=1, max_length=100)
