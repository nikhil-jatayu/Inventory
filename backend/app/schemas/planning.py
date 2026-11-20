from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import Field

from app.models import PlanStatus, Priority
from app.schemas.common import APIModel, Quantity
from app.schemas.stock import StockStatus


class DispatchPlanCreate(APIModel):
    po_line_id: int
    planned_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))
    priority: Priority = Priority.NORMAL


class DispatchPlanUpdate(APIModel):
    planned_date: date | None = None
    quantity: Decimal | None = Field(default=None, gt=0, le=Decimal("9999999999"))
    priority: Priority | None = None


class DispatchPlanOut(APIModel):
    id: int
    po_line_id: int
    po_id: int
    po_number: str
    customer_name: str
    unit_number: str
    item_id: int
    item_name: str
    item_family: str
    planned_date: date
    quantity: Quantity
    fulfilled_quantity: Quantity
    outstanding_quantity: Quantity
    priority: Priority
    status: PlanStatus
    lead_time_days: int
    days_until: int
    warning: bool
    po_quantity: Quantity
    po_planned: Quantity
    po_dispatched: Quantity
    po_balance: Quantity
    po_available_to_plan: Quantity


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
