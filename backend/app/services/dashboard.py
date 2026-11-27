from app.services.balances import net_sale
from app.models import Unit
from datetime import date

from sqlalchemy import and_, case, func, literal, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import AppError
from app.core.fiscal import (
    fiscal_bounds,
    fiscal_label,
    fiscal_months,
    fiscal_start_year,
    month_bounds,
    month_label,
    parse_fiscal_year,
    parse_month,
)
from app.models import (
    Dispatch,
    DispatchPlan,
    Item,
    PlanStatus,
    Priority,
    Rejection,
    SalesRecord,
)
from app.schemas.dashboard import (
    DashboardCalendarDay,
    DashboardUnit,
    DashboardKPIs,
    DashboardMonth,
    DashboardSummary,
)
from app.services.purchase_orders import ZERO, as_decimal
from app.services.stock import stock_sums_subquery

PRIORITY_COLUMNS = {
    Priority.NORMAL: "normal",
    Priority.URGENT: "urgent",
    Priority.EMERGENCY: "emergency",
}


def _fiscal_year_expression(column):
    month = func.extract("month", column)
    year = func.extract("year", column)
    return case((month >= settings.fy_start_month, year), else_=year - 1)


def _planned_by_item(date_from: date, date_to: date):
    return (
        select(
            DispatchPlan.item_id.label("item_id"),
            func.sum(
                DispatchPlan.quantity - DispatchPlan.fulfilled_quantity
            ).label("planned"),
        )
        .where(
            DispatchPlan.planned_date >= date_from,
            DispatchPlan.planned_date <= date_to,
            DispatchPlan.status != PlanStatus.DONE,
        )
        .group_by(DispatchPlan.item_id)
        .subquery()
    )


def _fy_options(db: Session, start_year: int) -> list[str]:
    years: set[int] = {fiscal_start_year(), start_year}
    for column in (
        DispatchPlan.planned_date,
        Dispatch.dispatch_date,
        Rejection.rejection_date,
    ):
        expression = _fiscal_year_expression(column)
        for (year,) in db.execute(select(expression).distinct()).all():
            if year is not None:
                years.add(int(year))
    return [fiscal_label(year) for year in sorted(years, reverse=True)]


def get_dashboard(
    db: Session,
    *,
    month: str | None,
    fy: str | None,
    family: str | None,
) -> DashboardSummary:
    if month:
        try:
            month_start = parse_month(month)
        except ValueError as exc:
            raise AppError(422, str(exc)) from exc
    else:
        month_start = date.today().replace(day=1)
    month_start, month_end = month_bounds(month_start)

    if fy:
        try:
            start_year = parse_fiscal_year(fy)
        except ValueError as exc:
            raise AppError(422, str(exc)) from exc
    else:
        start_year = fiscal_start_year(month_start)
    fy_start, fy_end = fiscal_bounds(start_year)
    months = fiscal_months(start_year)

    family_filters = [Item.family == family] if family else []
    active_item_filters = [Item.is_active.is_(True), *family_filters]

    sums = stock_sums_subquery()
    planned_sums = _planned_by_item(month_start, month_end)
    available = func.coalesce(sums.c.available, literal(0))
    planned = func.coalesce(planned_sums.c.planned, literal(0))
    shortfall = case((planned > available, planned - available), else_=literal(0))

    status_row = db.execute(
        select(
            func.coalesce(
                func.sum(case((available < Item.critical_level, 1), else_=0)), 0
            ),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(
                                available >= Item.critical_level,
                                available < Item.reorder_level,
                            ),
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            ),
            func.coalesce(func.sum(shortfall), 0),
        )
        .select_from(Item)
        .outerjoin(sums, sums.c.item_id == Item.id)
        .outerjoin(planned_sums, planned_sums.c.item_id == Item.id)
        .where(*active_item_filters)
    ).one()

    month_planned = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(DispatchPlan.quantity), literal(0)))
            .select_from(DispatchPlan)
            .join(Item, Item.id == DispatchPlan.item_id)
            .where(
                DispatchPlan.planned_date >= month_start,
                DispatchPlan.planned_date <= month_end,
                *family_filters,
            )
        )
    )
    # This is current real-time stock, compared against the selected month's plan.
    month_stock_available = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(available), literal(0)))
            .select_from(Item)
            .outerjoin(sums, sums.c.item_id == Item.id)
            .where(*active_item_filters)
        )
    )
    month_dispatched = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(Dispatch.quantity), literal(0)))
            .select_from(Dispatch)
            .join(Item, Item.id == Dispatch.item_id)
            .where(
                Dispatch.dispatch_date >= month_start,
                Dispatch.dispatch_date <= month_end,
                *family_filters,
            )
        )
    )
    month_sales = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(net_sale()), literal(0)))
            .select_from(SalesRecord)
            .join(Item, Item.id == SalesRecord.item_id)
            .where(
                SalesRecord.invoice_date >= month_start,
                SalesRecord.invoice_date <= month_end,
                *family_filters,
            )
        )
    )
    month_gross_sales = as_decimal(db.scalar(select(func.coalesce(func.sum(SalesRecord.quantity),0)).select_from(SalesRecord).join(Item,Item.id==SalesRecord.item_id).where(SalesRecord.invoice_date>=month_start,SalesRecord.invoice_date<=month_end,*family_filters)))
    month_unlinked_rejected = as_decimal(db.scalar(select(func.coalesce(func.sum(Rejection.quantity),0)).select_from(Rejection).join(Item,Item.id==Rejection.item_id).where(Rejection.rejection_date>=month_start,Rejection.rejection_date<=month_end,Rejection.dispatch_id.is_(None),*family_filters)))
    month_rejected = as_decimal(
        db.scalar(
            select(func.coalesce(func.sum(Rejection.quantity), literal(0)))
            .select_from(Rejection)
            .join(Item, Item.id == Rejection.item_id)
            .where(
                Rejection.rejection_date >= month_start,
                Rejection.rejection_date <= month_end,
                *family_filters,
            )
        )
    )

    kpis = DashboardKPIs(
        critical_items=int(status_row[0] or 0),
        below_reorder_items=int(status_row[1] or 0),
        total_shortfall=as_decimal(status_row[2]),
        month_planned=month_planned,
        month_stock_available=month_stock_available,
        month_dispatched=month_dispatched,
        month_sales=month_sales,
        month_gross_sales=month_gross_sales,
        month_sales_rejected=month_gross_sales-month_sales,
        month_unlinked_rejected=month_unlinked_rejected,
        month_rejected=month_rejected,
    )

    priority_sums = [
        func.sum(case((DispatchPlan.priority == priority, 1), else_=0)).label(name)
        for priority, name in PRIORITY_COLUMNS.items()
    ]
    calendar_rows = db.execute(
        select(
            DispatchPlan.planned_date,
            func.sum(DispatchPlan.quantity),
            func.count(DispatchPlan.id),
            *priority_sums,
        )
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(
            DispatchPlan.planned_date >= month_start,
            DispatchPlan.planned_date <= month_end,
            *family_filters,
        )
        .group_by(DispatchPlan.planned_date)
        .order_by(DispatchPlan.planned_date)
    ).all()

    calendar = [
        DashboardCalendarDay(
            date=row[0],
            planned=as_decimal(row[1]),
            count=int(row[2]),
            normal=int(row[3] or 0),
            urgent=int(row[4] or 0),
            emergency=int(row[5] or 0),
        )
        for row in calendar_rows
    ]

    planned_year = func.extract("year", DispatchPlan.planned_date)
    planned_month = func.extract("month", DispatchPlan.planned_date)
    dispatched_year = func.extract("year", Dispatch.dispatch_date)
    dispatched_month = func.extract("month", Dispatch.dispatch_date)
    rejected_year = func.extract("year", Rejection.rejection_date)
    rejected_month = func.extract("month", Rejection.rejection_date)
    sales_year = func.extract("year", SalesRecord.invoice_date)
    sales_month = func.extract("month", SalesRecord.invoice_date)

    planned_rows = db.execute(
        select(planned_year, planned_month, func.sum(DispatchPlan.quantity))
        .select_from(DispatchPlan)
        .join(Item, Item.id == DispatchPlan.item_id)
        .where(
            DispatchPlan.planned_date >= fy_start,
            DispatchPlan.planned_date <= fy_end,
            *family_filters,
        )
        .group_by(planned_year, planned_month)
    ).all()
    dispatched_rows = db.execute(
        select(dispatched_year, dispatched_month, func.sum(Dispatch.quantity))
        .select_from(Dispatch)
        .join(Item, Item.id == Dispatch.item_id)
        .where(
            Dispatch.dispatch_date >= fy_start,
            Dispatch.dispatch_date <= fy_end,
            *family_filters,
        )
        .group_by(dispatched_year, dispatched_month)
    ).all()
    rejected_rows = db.execute(
        select(rejected_year, rejected_month, func.sum(Rejection.quantity))
        .select_from(Rejection)
        .join(Item, Item.id == Rejection.item_id)
        .where(
            Rejection.rejection_date >= fy_start,
            Rejection.rejection_date <= fy_end,
            *family_filters,
        )
        .group_by(rejected_year, rejected_month)
    ).all()

    sales_rows = db.execute(
        select(sales_year, sales_month, func.sum(net_sale()))
        .select_from(SalesRecord)
        .join(Item, Item.id == SalesRecord.item_id)
        .where(
            SalesRecord.invoice_date >= fy_start,
            SalesRecord.invoice_date <= fy_end,
            *family_filters,
        )
        .group_by(sales_year, sales_month)
    ).all()

    planned_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in planned_rows
    }
    dispatched_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in dispatched_rows
    }
    rejected_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in rejected_rows
    }
    sales_by_month = {
        (int(row[0]), int(row[1])): as_decimal(row[2]) for row in sales_rows
    }

    month_stats = []
    for bucket in months:
        key = (bucket.year, bucket.month)
        month_stats.append(
            DashboardMonth(
                month=bucket.strftime("%Y-%m"),
                label=month_label(bucket),
                planned=planned_by_month.get(key, ZERO),
                dispatched=dispatched_by_month.get(key, ZERO),
                sales=sales_by_month.get(key, ZERO),
                rejected=rejected_by_month.get(key, ZERO),
            )
        )

    unit_rows = db.execute(
        select(
            func.coalesce(Unit.id, 0),
            func.coalesce(Unit.name, "Unassigned"),
            func.sum(Rejection.quantity),
            func.count(Rejection.id),
        )
        .select_from(Rejection)
        .outerjoin(Unit, Unit.id == Rejection.unit_id)
        .join(Item, Item.id == Rejection.item_id)
        .where(
            Rejection.rejection_date >= fy_start,
            Rejection.rejection_date <= fy_end,
            *family_filters,
        )
        .group_by(Unit.id, Unit.name)
        .order_by(func.sum(Rejection.quantity).desc(), Unit.name)
    ).all()

    units = [
        DashboardUnit(
            unit_id=unit_id,
            name=name,
            quantity=as_decimal(quantity),
            count=int(count),
        )
        for unit_id, name, quantity, count in unit_rows
    ]

    return DashboardSummary(
        month=month_start.strftime("%Y-%m"),
        month_label=month_label(month_start),
        month_start=month_start,
        month_end=month_end,
        fy=fiscal_label(start_year),
        fy_start=fy_start,
        fy_end=fy_end,
        fy_options=_fy_options(db, start_year),
        kpis=kpis,
        months=month_stats,
        calendar=calendar,
        unit_rejections=units,
    )


__all__ = ["get_dashboard"]
