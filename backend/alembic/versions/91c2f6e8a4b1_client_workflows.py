"""client workflows: units, independent plans, sales and purchase forms

Revision ID: 91c2f6e8a4b1
Revises: 07c83db70056
Create Date: 2026-11-24
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "91c2f6e8a4b1"
down_revision: str | None = "07c83db70056"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Central location master. Seed only the four locations in the supplied workbook.
    op.create_table(
        "units",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_units_name", "units", ["name"], unique=True)
    op.create_index("ix_units_is_active", "units", ["is_active"], unique=False)
    op.create_table(
        "purchase_order_units",
        sa.Column("po_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["po_id"], ["purchase_orders.id"], name="fk_purchase_order_units_po_id_purchase_orders", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_purchase_order_units_unit_id_units"),
        sa.PrimaryKeyConstraint("po_id", "unit_id", name="pk_purchase_order_units"),
    )
    op.create_index("ix_purchase_order_units_unit_id", "purchase_order_units", ["unit_id"], unique=False)
    units = sa.table("units", sa.column("name", sa.String()), sa.column("is_active", sa.Boolean()))
    op.bulk_insert(units, [{"name": f"Unit-{number}", "is_active": True} for number in range(1, 5)])

    # Item details from the client Excel: project and model number are part of identity/context.
    op.add_column("items", sa.Column("project", sa.String(length=160), nullable=False, server_default="General"))
    op.add_column("items", sa.Column("model_no", sa.String(length=120), nullable=True))
    op.create_index("ix_items_project", "items", ["project"], unique=False)
    op.drop_index("ix_items_name", table_name="items")
    op.create_index("ix_items_name", "items", ["name"], unique=False)
    op.create_unique_constraint("uq_items_item_name_project", "items", ["name", "project"])

    # Existing PO-linked plans are retained. New plans may be created without a PO line.
    op.add_column("dispatch_plans", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.add_column("dispatch_plans", sa.Column("planned_end_date", sa.Date(), nullable=True))
    op.execute("UPDATE dispatch_plans SET planned_end_date = planned_date WHERE planned_end_date IS NULL")
    op.alter_column("dispatch_plans", "planned_end_date", nullable=False)
    op.create_foreign_key("fk_dispatch_plans_unit_id_units", "dispatch_plans", "units", ["unit_id"], ["id"])
    op.create_index("ix_dispatch_plans_unit_id", "dispatch_plans", ["unit_id"], unique=False)
    op.create_index("ix_dispatch_plans_planned_end_date", "dispatch_plans", ["planned_end_date"], unique=False)
    op.alter_column("dispatch_plans", "po_line_id", nullable=True)

    # Actual dispatches can be linked to a single dispatch plan and an actual destination unit.
    op.add_column("dispatches", sa.Column("plan_id", sa.Integer(), nullable=True))
    op.add_column("dispatches", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_dispatches_plan_id_dispatch_plans", "dispatches", "dispatch_plans", ["plan_id"], ["id"])
    op.create_foreign_key("fk_dispatches_unit_id_units", "dispatches", "units", ["unit_id"], ["id"])
    op.create_index("ix_dispatches_plan_id", "dispatches", ["plan_id"], unique=False)
    op.create_index("ix_dispatches_unit_id", "dispatches", ["unit_id"], unique=False)
    op.alter_column("dispatches", "po_line_id", nullable=True)

    # RGP details belong to each row in the grouped RGP form; multiple items may share one RGP.
    op.add_column("rejections", sa.Column("rgp_number", sa.String(length=80), nullable=True))
    op.add_column("rejections", sa.Column("unit_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_rejections_unit_id_units", "rejections", "units", ["unit_id"], ["id"])
    op.create_index("ix_rejections_rgp_number", "rejections", ["rgp_number"], unique=False)
    op.create_index("ix_rejections_unit_id", "rejections", ["unit_id"], unique=False)

    # Sales rows are generated from actual dispatches. Backfill legacy dispatch history.
    op.create_table(
        "sales_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dispatch_id", sa.Integer(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=True),
        sa.Column("invoice_number", sa.String(length=32), nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("po_number", sa.String(length=50), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["dispatch_id"], ["dispatches.id"], name="fk_sales_records_dispatch_id_dispatches"),
        sa.ForeignKeyConstraint(["plan_id"], ["dispatch_plans.id"], name="fk_sales_records_plan_id_dispatch_plans"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_sales_records_item_id_items"),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_sales_records_unit_id_units"),
    )
    op.create_index("ix_sales_records_dispatch_id", "sales_records", ["dispatch_id"], unique=True)
    op.create_index("ix_sales_records_plan_id", "sales_records", ["plan_id"], unique=False)
    op.create_index("ix_sales_records_invoice_number", "sales_records", ["invoice_number"], unique=True)
    op.create_index("ix_sales_records_invoice_date", "sales_records", ["invoice_date"], unique=False)
    op.create_index("ix_sales_records_item_id", "sales_records", ["item_id"], unique=False)
    op.create_index("ix_sales_records_unit_id", "sales_records", ["unit_id"], unique=False)
    op.execute(
        """
        INSERT INTO sales_records
            (dispatch_id, plan_id, invoice_number, invoice_date, po_number, item_id, unit_id, quantity)
        SELECT d.id, d.plan_id, 'INV-LEGACY-' || CAST(d.id AS VARCHAR), d.dispatch_date,
               po.po_number, d.item_id, d.unit_id, d.quantity
        FROM dispatches d
        LEFT JOIN po_lines pol ON pol.id = d.po_line_id
        LEFT JOIN purchase_orders po ON po.id = pol.po_id
        """
    )

    # Workbook's ADD PURCHASE: a posted purchase increases inventory through the stock ledger.
    op.create_table(
        "purchases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], name="fk_purchases_recorded_by_users"),
    )
    op.create_index("ix_purchases_purchase_date", "purchases", ["purchase_date"], unique=False)
    op.create_index("ix_purchases_recorded_by", "purchases", ["recorded_by"], unique=False)
    op.create_table(
        "purchase_lines",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("purchase_id", sa.Integer(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"], name="fk_purchase_lines_purchase_id_purchases", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_purchase_lines_item_id_items"),
        sa.UniqueConstraint("purchase_id", "item_id", name="purchase_item"),
    )
    op.create_index("ix_purchase_lines_purchase_id", "purchase_lines", ["purchase_id"], unique=False)
    op.create_index("ix_purchase_lines_item_id", "purchase_lines", ["item_id"], unique=False)

    # Workbook's CREATE PURCHASE PLAN: date-range commitments, with category calculated from lead time.
    op.create_table(
        "purchase_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=False),
        sa.Column("planned_end_date", sa.Date(), nullable=False),
        sa.Column("category", sa.Enum("NORMAL", "URGENT", "EMERGENCY", name="priority", native_enum=False, length=20), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_purchase_plans_item_id_items"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], name="fk_purchase_plans_recorded_by_users"),
    )
    op.create_index("ix_purchase_plans_item_id", "purchase_plans", ["item_id"], unique=False)
    op.create_index("ix_purchase_plans_planned_date", "purchase_plans", ["planned_date"], unique=False)
    op.create_index("ix_purchase_plans_planned_end_date", "purchase_plans", ["planned_end_date"], unique=False)
    op.create_index("ix_purchase_plans_recorded_by", "purchase_plans", ["recorded_by"], unique=False)

    # Workbook's ADD PURCHASE REJECTION. Kept separate from customer rejection records.
    op.create_table(
        "purchase_rejections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rgp_number", sa.String(length=80), nullable=False),
        sa.Column("unit_id", sa.Integer(), nullable=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("rejection_date", sa.Date(), nullable=False),
        sa.Column("quantity", sa.Numeric(14, 2), nullable=False),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("recorded_by", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["unit_id"], ["units.id"], name="fk_purchase_rejections_unit_id_units"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_purchase_rejections_item_id_items"),
        sa.ForeignKeyConstraint(["recorded_by"], ["users.id"], name="fk_purchase_rejections_recorded_by_users"),
    )
    op.create_index("ix_purchase_rejections_rgp_number", "purchase_rejections", ["rgp_number"], unique=False)
    op.create_index("ix_purchase_rejections_unit_id", "purchase_rejections", ["unit_id"], unique=False)
    op.create_index("ix_purchase_rejections_item_id", "purchase_rejections", ["item_id"], unique=False)
    op.create_index("ix_purchase_rejections_rejection_date", "purchase_rejections", ["rejection_date"], unique=False)
    op.create_index("ix_purchase_rejections_recorded_by", "purchase_rejections", ["recorded_by"], unique=False)


def downgrade() -> None:
    # New workflows intentionally create records without PO links. A downgrade
    # would either lose sales history or fail when restoring NOT NULL PO columns.
    # Refuse it rather than destructively rewriting or dropping business data.
    if not op.get_context().as_sql:
        bind = op.get_bind()
        sale_count = bind.execute(sa.text("SELECT COUNT(*) FROM sales_records")).scalar_one()
        independent_plans = bind.execute(sa.text("SELECT COUNT(*) FROM dispatch_plans WHERE po_line_id IS NULL")).scalar_one()
        independent_dispatches = bind.execute(sa.text("SELECT COUNT(*) FROM dispatches WHERE po_line_id IS NULL")).scalar_one()
        if sale_count or independent_plans or independent_dispatches:
            raise RuntimeError(
                "Downgrade blocked: sales history or PO-independent plans/dispatches exist. "
                "Back up and migrate the data deliberately before downgrading."
            )

    op.drop_table("purchase_rejections")
    op.drop_table("purchase_plans")
    op.drop_table("purchase_lines")
    op.drop_table("purchases")
    op.drop_table("sales_records")
    op.drop_index("ix_rejections_unit_id", table_name="rejections")
    op.drop_index("ix_rejections_rgp_number", table_name="rejections")
    op.drop_constraint("fk_rejections_unit_id_units", "rejections", type_="foreignkey")
    op.drop_column("rejections", "unit_id")
    op.drop_column("rejections", "rgp_number")
    op.drop_index("ix_dispatches_unit_id", table_name="dispatches")
    op.drop_index("ix_dispatches_plan_id", table_name="dispatches")
    op.drop_constraint("fk_dispatches_unit_id_units", "dispatches", type_="foreignkey")
    op.drop_constraint("fk_dispatches_plan_id_dispatch_plans", "dispatches", type_="foreignkey")
    op.drop_column("dispatches", "unit_id")
    op.drop_column("dispatches", "plan_id")
    op.alter_column("dispatches", "po_line_id", nullable=False)
    op.drop_index("ix_dispatch_plans_planned_end_date", table_name="dispatch_plans")
    op.drop_index("ix_dispatch_plans_unit_id", table_name="dispatch_plans")
    op.drop_constraint("fk_dispatch_plans_unit_id_units", "dispatch_plans", type_="foreignkey")
    op.drop_column("dispatch_plans", "planned_end_date")
    op.drop_column("dispatch_plans", "unit_id")
    op.alter_column("dispatch_plans", "po_line_id", nullable=False)
    op.drop_constraint("uq_items_item_name_project", "items", type_="unique")
    op.drop_index("ix_items_project", table_name="items")
    op.drop_column("items", "model_no")
    op.drop_column("items", "project")
    op.drop_index("ix_purchase_order_units_unit_id", table_name="purchase_order_units")
    op.drop_table("purchase_order_units")
    op.drop_index("ix_units_is_active", table_name="units")
    op.drop_index("ix_units_name", table_name="units")
    op.drop_table("units")
    op.create_index("ix_items_name", "items", ["name"], unique=True)
