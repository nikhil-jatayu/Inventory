"""Allow several dispatch lines to share an invoice number."""
from alembic import op
import sqlalchemy as sa

revision = "a2f9c7d4e601"
down_revision = "91c2f6e8a4b1"
branch_labels = None
depends_on = None

def upgrade():
    op.drop_index("ix_sales_records_invoice_number", table_name="sales_records")
    op.create_index("ix_sales_records_invoice_number", "sales_records", ["invoice_number"], unique=False)

def downgrade():
    connection = op.get_bind()
    if not op.get_context().as_sql and connection.execute(sa.text("SELECT 1 FROM sales_records GROUP BY invoice_number HAVING count(*) > 1 LIMIT 1")).first():
        raise RuntimeError("Multi-line invoices exist; downgrade would violate invoice uniqueness.")
    op.drop_index("ix_sales_records_invoice_number", table_name="sales_records")
    op.create_index("ix_sales_records_invoice_number", "sales_records", ["invoice_number"], unique=True)
