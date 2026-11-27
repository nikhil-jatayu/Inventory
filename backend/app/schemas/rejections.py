from datetime import date
from decimal import Decimal
import re

from pydantic import Field, field_validator, model_validator

from app.schemas.common import APIModel, Quantity


class RejectionIssueCreate(APIModel):
    name: str = Field(min_length=1, max_length=160)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Issue name is required")
        return cleaned


class RejectionIssueUpdate(APIModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    is_active: bool | None = None

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Issue name is required")
        return cleaned


class RejectionIssueOut(APIModel):
    id: int
    name: str
    is_active: bool
    rejection_count: int = 0


class RejectionIssueList(APIModel):
    issues: list[RejectionIssueOut]


class RejectionCreate(APIModel):
    dispatch_id: int = Field(gt=0)
    rgp_number: str = Field(min_length=1, max_length=80)
    unit_id: int
    item_id: int
    rejection_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)
    issue_id: int | None = None
    issue_name: str | None = Field(default=None, max_length=160)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("rgp_number")
    @classmethod
    def validate_rgp_number(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9/-]{1,80}", cleaned):
            raise ValueError("RGP No. may contain letters, numbers, hyphens and slashes only")
        return cleaned

    @field_validator("issue_name", "remarks")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class RejectionLineCreate(APIModel):
    dispatch_id: int = Field(gt=0)
    issue_id: int | None = None
    item_id: int
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"), decimal_places=2)


class RejectionBatchCreate(APIModel):
    rgp_number: str = Field(min_length=1, max_length=80)
    unit_id: int
    rejection_date: date
    lines: list[RejectionLineCreate] = Field(min_length=1, max_length=100)

    @field_validator("rgp_number")
    @classmethod
    def validate_batch_rgp_number(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not re.fullmatch(r"[A-Z0-9/-]{1,80}", cleaned):
            raise ValueError("RGP No. may contain letters, numbers, hyphens and slashes only")
        return cleaned

    @model_validator(mode="after")
    def validate_unique_items(self) -> "RejectionBatchCreate":
        item_ids = [line.dispatch_id for line in self.lines if line.dispatch_id is not None]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("A dispatch can appear only once within an RGP entry")
        return self


class RejectionOut(APIModel):
    dispatch_id: int | None = None
    invoice_number: str | None = None
    batch_id: str | None = None
    id: int
    rgp_number: str | None
    unit_id: int | None
    unit_name: str | None
    item_id: int
    item_name: str
    item_family: str
    project: str
    rejection_date: date
    quantity: Quantity
    issue_id: int | None
    issue_name: str | None
    remarks: str | None
    recorded_by: int
    recorded_by_name: str


class RejectionMonth(APIModel):
    month: str
    label: str
    quantity: Quantity


class RejectionIssueStat(APIModel):
    issue_id: int
    name: str
    quantity: Quantity
    count: int
    share: float
    cumulative_share: float


class RejectionReport(APIModel):
    fy: str
    fy_start: date
    fy_end: date
    fy_options: list[str]
    months: list[RejectionMonth]
    issues: list[RejectionIssueStat]
    total_quantity: Quantity
    rejection_count: int
    top_issue: str | None
