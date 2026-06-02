"""add order_lines.unit_price (frozen sale price)

Revision ID: a7b8olprice1
Revises: f6a7portalrt1
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a7b8olprice1"
down_revision: Union[str, None] = "f6a7portalrt1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("order_lines") as batch_op:
        batch_op.add_column(sa.Column("unit_price", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_lines") as batch_op:
        batch_op.drop_column("unit_price")
