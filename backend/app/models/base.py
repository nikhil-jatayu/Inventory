from datetime import date, datetime
from decimal import Decimal
from enum import Enum as PyEnum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Role(str, PyEnum):
    ADMIN = "ADMIN"
    STORE = "STORE"
    QUALITY = "QUALITY"
    VIEWER = "VIEWER"


class StockTxnType(str, PyEnum):
    OPENING = "OPENING"
    RECEIPT = "RECEIPT"
    ADJUSTMENT = "ADJUSTMENT"
    DISPATCH = "DISPATCH"


class POStatus(str, PyEnum):
    OPEN = "OPEN"
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Priority(str, PyEnum):
    NORMAL = "NORMAL"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class PlanStatus(str, PyEnum):
    PLANNED = "PLANNED"
    PARTIAL = "PARTIAL"
    DONE = "DONE"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120))
    hashed_password: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False, length=20), default=Role.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (UniqueConstraint("name", "project", name="uq_items_item_name_project"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    project: Mapped[str] = mapped_column(String(160), default="General", server_default="General", index=True)
    family: Mapped[str] = mapped_column(String(80), index=True)
    model_no: Mapped[str | None] = mapped_column(String(120))
    reorder_level: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    critical_level: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Kept as text to preserve leading zeroes. New API writes enforce exactly 8 digits.
    po_number: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    customer_name: Mapped[str] = mapped_column(String(160), index=True)
    unit_number: Mapped[str] = mapped_column(String(80))
    po_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[POStatus] = mapped_column(Enum(POStatus, native_enum=False, length=20), default=POStatus.OPEN)


class PurchaseOrderUnit(Base):
    __tablename__ = "purchase_order_units"

    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id", ondelete="CASCADE"), primary_key=True)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"), primary_key=True, index=True)


class POLine(Base):
    __tablename__ = "po_lines"
    __table_args__ = (UniqueConstraint("po_id", "item_id", name="po_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    po_id: Mapped[int] = mapped_column(ForeignKey("purchase_orders.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class StockTransaction(Base):
    __tablename__ = "stock_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    type: Mapped[StockTxnType] = mapped_column(Enum(StockTxnType, native_enum=False, length=20))
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    date: Mapped[date] = mapped_column(Date, index=True)
    ref: Mapped[str | None] = mapped_column(String(120))
    remarks: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DispatchPlan(Base):
    __tablename__ = "dispatch_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable for new independent plans; populated on legacy PO-linked plans.
    po_line_id: Mapped[int | None] = mapped_column(ForeignKey("po_lines.id"), index=True, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True, nullable=True)
    planned_date: Mapped[date] = mapped_column(Date, index=True)
    planned_end_date: Mapped[date] = mapped_column(Date, index=True, default=date.today)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    fulfilled_quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0"), server_default="0")
    priority: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False, length=20), default=Priority.NORMAL)
    status: Mapped[PlanStatus] = mapped_column(Enum(PlanStatus, native_enum=False, length=20), default=PlanStatus.PLANNED)


class Dispatch(Base):
    __tablename__ = "dispatches"

    id: Mapped[int] = mapped_column(primary_key=True)
    # Nullable for plan-based dispatches that have no corresponding PO.
    po_line_id: Mapped[int | None] = mapped_column(ForeignKey("po_lines.id"), index=True, nullable=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_plans.id"), index=True, nullable=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    dispatch_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    remarks: Mapped[str | None] = mapped_column(Text)


class SalesRecord(Base):
    __tablename__ = "sales_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    dispatch_id: Mapped[int] = mapped_column(ForeignKey("dispatches.id"), unique=True, index=True)
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("dispatch_plans.id"), index=True, nullable=True)
    invoice_number: Mapped[str] = mapped_column(String(32), index=True)
    invoice_date: Mapped[date] = mapped_column(Date, index=True)
    po_number: Mapped[str | None] = mapped_column(String(50))
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class RejectionIssue(Base):
    __tablename__ = "rejection_issues"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Rejection(Base):
    __tablename__ = "rejections"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True, nullable=True)
    rgp_number: Mapped[str | None] = mapped_column(String(80), index=True)
    rejection_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("rejection_issues.id"), index=True)
    dispatch_id: Mapped[int | None] = mapped_column(ForeignKey("dispatches.id"), index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True)
    remarks: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_date: Mapped[date] = mapped_column(Date, index=True)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class PurchaseLine(Base):
    __tablename__ = "purchase_lines"
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_plans.id"), index=True)
    __table_args__ = (UniqueConstraint("purchase_id", "plan_id", name="purchase_plan_line"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id", ondelete="CASCADE"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class PurchasePlan(Base):
    __tablename__ = "purchase_plans"

    id: Mapped[int] = mapped_column(primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    planned_date: Mapped[date] = mapped_column(Date, index=True)
    planned_end_date: Mapped[date] = mapped_column(Date, index=True)
    category: Mapped[Priority] = mapped_column(Enum(Priority, native_enum=False, length=20))
    remarks: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)


class PurchaseRejection(Base):
    __tablename__ = "purchase_rejections"
    plan_id: Mapped[int | None] = mapped_column(ForeignKey("purchase_plans.id"), index=True)
    batch_id: Mapped[str | None] = mapped_column(String(36), index=True)

    id: Mapped[int] = mapped_column(primary_key=True)
    rgp_number: Mapped[str] = mapped_column(String(80), index=True)
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"), index=True, nullable=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), index=True)
    rejection_date: Mapped[date] = mapped_column(Date, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    remarks: Mapped[str | None] = mapped_column(Text)
    recorded_by: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
