"""add customer_refresh_tokens (portal refresh)

Revision ID: f6a7portalrt1
Revises: e5f6pricing1
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f6a7portalrt1"
down_revision: Union[str, None] = "e5f6pricing1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "customer_refresh_tokens",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("customer_user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False,
        ),
        sa.ForeignKeyConstraint(["customer_user_id"], ["customer_users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_refresh_tokens_id", "customer_refresh_tokens", ["id"])
    op.create_index("ix_customer_refresh_tokens_jti", "customer_refresh_tokens", ["jti"], unique=True)
    op.create_index(
        "ix_customer_refresh_tokens_customer_user_id", "customer_refresh_tokens", ["customer_user_id"]
    )


def downgrade() -> None:
    op.drop_table("customer_refresh_tokens")
