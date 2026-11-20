from datetime import date

from app.schemas.common import APIModel, Quantity


class DashboardKPIs(APIModel):
    critical_items: int
    below_reorder_items: int
    total_shortfall: Quantity
    month_planned: Quantity
    month_dispatched: Quantity
    month_rejected: Quantity


class DashboardMonth(APIModel):
    month: str
    label: str
    planned: Quantity
    dispatched: Quantity
    rejected: Quantity


class DashboardCalendarDay(APIModel):
    date: date
    planned: Quantity
    count: int
    normal: int
    urgent: int
    emergency: int


class DashboardIssue(APIModel):
    issue_id: int
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
    issues: list[DashboardIssue]
