"""add stock reservations (ledger + cached reserved_stock)

Revision ID: c3d4reserv01
Revises: b2c3refresh01
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4reserv01"
down_revision: Union[str, None] = "b2c3refresh01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("products") as batch_op:
        batch_op.add_column(
            sa.Column(
                "reserved_stock", sa.Float(), nullable=False, server_default="0"
            )
        )

    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("order_id", sa.Integer(), nullable=True),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "CONSUMED", "RELEASED", "EXPIRED", name="reservationstatus"),
            nullable=False,
        ),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="ORDER"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_reservations_id", "stock_reservations", ["id"])
    op.create_index("ix_stock_reservations_product_id", "stock_reservations", ["product_id"])
    op.create_index("ix_stock_reservations_order_id", "stock_reservations", ["order_id"])
    op.create_index("ix_stock_reservations_status", "stock_reservations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_stock_reservations_status", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_order_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_product_id", table_name="stock_reservations")
    op.drop_index("ix_stock_reservations_id", table_name="stock_reservations")
    op.drop_table("stock_reservations")
    with op.batch_alter_table("products") as batch_op:
        batch_op.drop_column("reserved_stock")
