from datetime import date

from app.schemas.common import APIModel, Quantity


class DashboardKPIs(APIModel):
    critical_items: int
    below_reorder_items: int
    total_shortfall: Quantity
    month_planned: Quantity
    month_stock_available: Quantity
    month_dispatched: Quantity
    month_sales: Quantity
    month_gross_sales: Quantity
    month_sales_rejected: Quantity
    month_unlinked_rejected: Quantity
    month_rejected: Quantity


class DashboardMonth(APIModel):
    month: str
    label: str
    planned: Quantity
    dispatched: Quantity
    sales: Quantity
    rejected: Quantity


class DashboardCalendarDay(APIModel):
    date: date
    planned: Quantity
    count: int
    normal: int
    urgent: int
    emergency: int


class DashboardUnit(APIModel):
    unit_id: int
    name: str
    quantity: Quantity
    count: int


class DashboardSummary(APIModel):
    month: str
    month_label: str
    month_start: date
    month_end: date
    fy: str
    fy_start: date
    fy_end: date
    fy_options: list[str]
    kpis: DashboardKPIs
    months: list[DashboardMonth]
    calendar: list[DashboardCalendarDay]
    unit_rejections: list[DashboardUnit]
