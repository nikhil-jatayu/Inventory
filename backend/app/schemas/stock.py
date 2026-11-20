from datetime import date as date_type
from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import Field, field_validator

from app.models import StockTxnType
from app.schemas.common import APIModel, Quantity


class StockStatus(str, Enum):
    OK = "OK"
    BELOW_REORDER = "BELOW_REORDER"
    CRITICAL = "CRITICAL"


class TransactionCreate(APIModel):
    item_id: int
    type: StockTxnType
    quantity: Decimal = Field(le=Decimal("9999999999"), ge=Decimal("-9999999999"))
    date: date_type | None = None
    ref: str | None = Field(default=None, max_length=120)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("quantity")
    @classmethod
    def non_zero(cls, value: Decimal) -> Decimal:
        if value == 0:
            raise ValueError("Quantity must not be zero")
        return value


class TransactionOut(APIModel):
    id: int
    item_id: int
    item_name: str
    type: StockTxnType
    quantity: Quantity
    date: date_type
    ref: str | None
    remarks: str | None
    created_at: datetime


class StockStatusOut(APIModel):
    item_id: int
    name: str
    family: str
    available: Quantity
    reorder_level: Quantity
    critical_level: Quantity
    status: StockStatus


class StockSummary(APIModel):
    total_items: int
    critical: int
    below_reorder: int
    ok: int
