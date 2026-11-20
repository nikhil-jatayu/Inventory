from datetime import date
from decimal import Decimal

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
    item_id: int
    rejection_date: date
    quantity: Decimal = Field(gt=0, le=Decimal("9999999999"))
    issue_id: int | None = None
    issue_name: str | None = Field(default=None, max_length=160)
    remarks: str | None = Field(default=None, max_length=2000)

    @field_validator("issue_name", "remarks")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @model_validator(mode="after")
    def require_issue(self) -> "RejectionCreate":
        if self.issue_id is None and not self.issue_name:
            raise ValueError("Select an existing issue or enter a new issue")
        return self


class RejectionOut(APIModel):
    id: int
    item_id: int
    item_name: str
    item_family: str
    rejection_date: date
    quantity: Quantity
    issue_id: int
    issue_name: str
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
