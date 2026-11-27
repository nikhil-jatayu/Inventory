"""Reclassify existing plans using their planned date range, not today's date."""
from alembic import op
import sqlalchemy as sa
from app.core.config import settings

revision = "c4f7a91d2e60"
down_revision = "b3e8a1d6c204"
branch_labels = None
depends_on = None


def upgrade():
    # PostgreSQL DATE subtraction yields integer days. Only classification columns change.
    normal = int(settings.lead_time_normal_days)
    urgent = int(settings.lead_time_urgent_days)
    for table, column in (("dispatch_plans", "priority"), ("purchase_plans", "category")):
        op.execute(sa.text(f"""UPDATE {table} SET {column} = CASE
            WHEN planned_end_date - planned_date > {normal} THEN 'NORMAL'
            WHEN planned_end_date - planned_date > {urgent} THEN 'URGENT'
            ELSE 'EMERGENCY' END
            WHERE {column} IS DISTINCT FROM CASE
            WHEN planned_end_date - planned_date > {normal} THEN 'NORMAL'
            WHEN planned_end_date - planned_date > {urgent} THEN 'URGENT'
            ELSE 'EMERGENCY' END"""))


def downgrade():
    raise RuntimeError("Previous classifications cannot be reconstructed; restore the pre-migration backup instead.")
