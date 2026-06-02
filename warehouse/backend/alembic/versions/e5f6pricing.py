"""add sale pricing: products.price_base + product_tier_prices

Revision ID: e5f6pricing1
Revises: d4e5customer1
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e5f6pricing1"
down_revision: Union[str, None] = "d4e5customer1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(sa.Column("price_base", sa.Numeric(12, 2), nullable=True))

    op.create_table(
        "product_tier_prices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("tier", sa.String(length=50), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("product_id", "tier", name="uq_product_tier"),
    )
    op.create_index("ix_product_tier_prices_id", "product_tier_prices", ["id"])
    op.create_index(
        "ix_product_tier_prices_product_id", "product_tier_prices", ["product_id"]
    )
    op.create_index("ix_product_tier_prices_tier", "product_tier_prices", ["tier"])


def downgrade() -> None:
    op.drop_table("product_tier_prices")
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("price_base")
