import re
from calendar import month_abbr
from datetime import date, timedelta

from app.core.config import settings

FY_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")
MONTH_PATTERN = re.compile(r"^(\d{4})-(\d{2})$")


def fiscal_start_year(on: date | None = None) -> int:
    """Return the April-style financial year start year for a date."""
    today = on or date.today()
    return today.year if today.month >= settings.fy_start_month else today.year - 1


def fiscal_bounds(start_year: int) -> tuple[date, date]:
    start = date(start_year, settings.fy_start_month, 1)
    next_start = date(start_year + 1, settings.fy_start_month, 1)
    return start, next_start - timedelta(days=1)


def fiscal_label(start_year: int) -> str:
    return f"{start_year}-{(start_year + 1) % 100:02d}"


def parse_fiscal_year(value: str) -> int:
    match = FY_PATTERN.match(value.strip())
    if not match:
        raise ValueError("Financial year must look like 2025-26")
    start_year = int(match.group(1))
    if int(match.group(2)) != (start_year + 1) % 100:
        raise ValueError("Financial year must look like 2025-26")
    return start_year


def fiscal_months(start_year: int) -> list[date]:
    months: list[date] = []
    year, month = start_year, settings.fy_start_month
    for _ in range(12):
        months.append(date(year, month, 1))
        month += 1
        if month > 12:
            month = 1
            year += 1
    return months


def month_label(value: date) -> str:
    return f"{month_abbr[value.month]} {value.year}"


def parse_month(value: str) -> date:
    match = MONTH_PATTERN.match(value.strip())
    if not match:
        raise ValueError("Month must look like 2026-04")
    year = int(match.group(1))
    month = int(match.group(2))
    if not 1 <= month <= 12:
        raise ValueError("Month must look like 2026-04")
    return date(year, month, 1)


def month_bounds(value: date) -> tuple[date, date]:
    next_month = (value.replace(day=28) + timedelta(days=4)).replace(day=1)
    return value, next_month - timedelta(days=1)
