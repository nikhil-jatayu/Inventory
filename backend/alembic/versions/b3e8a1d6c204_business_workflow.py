"""Link receipts/cancellations to purchase plans and unit rejections to dispatches.

Existing history remains unallocated; no financial or stock data is rewritten.
"""
from alembic import op
import sqlalchemy as sa

revision = "b3e8a1d6c204"
down_revision = "a2f9c7d4e601"
branch_labels = None
depends_on = None

LINKS = [("rejections", "dispatch_id", "dispatches"), ("purchase_lines", "plan_id", "purchase_plans"), ("purchase_rejections", "plan_id", "purchase_plans")]

def upgrade():
    op.alter_column("rejections", "issue_id", existing_type=sa.Integer(), nullable=True)
    for table, column, target in LINKS:
        op.add_column(table, sa.Column(column, sa.Integer(), nullable=True))
        op.create_foreign_key(f"fk_{table}_{column}_{target}", table, target, [column], ["id"])
        op.create_index(f"ix_{table}_{column}", table, [column])
    for table in ("rejections", "purchase_rejections"):
        op.add_column(table, sa.Column("batch_id", sa.String(36), nullable=True))
        op.create_index(f"ix_{table}_batch_id", table, ["batch_id"])
    op.drop_constraint("purchase_item", "purchase_lines", type_="unique")
    op.create_unique_constraint("purchase_plan_line", "purchase_lines", ["purchase_id", "plan_id"])

def downgrade():
    # Downgrading after linked writes would erase business history. Restore a verified backup instead.
    raise RuntimeError("Business workflow migration is intentionally forward-only; restore a pre-migration backup if required.")
