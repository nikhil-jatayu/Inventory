"""add plan fulfilled quantity

Revision ID: 07c83db70056
Revises: 58795fe86be6
Create Date: 2026-11-19 13:58:08.315918

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '07c83db70056'
down_revision: str | None = '58795fe86be6'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dispatch_plans",
        sa.Column(
            "fulfilled_quantity",
            sa.Numeric(precision=14, scale=2),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.execute(
        "UPDATE dispatch_plans SET fulfilled_quantity = quantity WHERE status = 'DONE'"
    )


def downgrade() -> None:
    op.drop_column("dispatch_plans", "fulfilled_quantity")
