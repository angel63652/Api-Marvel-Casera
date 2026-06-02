"""add client portal domain (customers, users, addresses, change requests)

Revision ID: d4e5customer1
Revises: c3d4reserv01
Create Date: 2026-06-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d4e5customer1"
down_revision: Union[str, None] = "c3d4reserv01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text("(CURRENT_TIMESTAMP)")


def upgrade() -> None:
    op.create_table(
        "customers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("tax_id", sa.String(length=50), nullable=False),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("contact_phone", sa.String(length=50), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SUSPENDED", "PENDING", name="customerstatus"),
            nullable=False,
        ),
        sa.Column("price_tier", sa.String(length=50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_id", "customers", ["id"])
    op.create_index("ix_customers_company_name", "customers", ["company_name"])
    op.create_index("ix_customers_tax_id", "customers", ["tax_id"], unique=True)
    op.create_index("ix_customers_status", "customers", ["status"])

    op.create_table(
        "customer_users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=True),
        sa.Column(
            "role", sa.Enum("OWNER", "STAFF", name="customeruserrole"), nullable=False
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_users_id", "customer_users", ["id"])
    op.create_index("ix_customer_users_customer_id", "customer_users", ["customer_id"])
    op.create_index("ix_customer_users_email", "customer_users", ["email"], unique=True)

    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column(
            "type", sa.Enum("SHIPPING", "BILLING", name="addresstype"), nullable=False
        ),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("line1", sa.String(length=255), nullable=False),
        sa.Column("line2", sa.String(length=255), nullable=True),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("province", sa.String(length=100), nullable=True),
        sa.Column("postal_code", sa.String(length=20), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False, server_default="ES"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_addresses_id", "customer_addresses", ["id"])
    op.create_index(
        "ix_customer_addresses_customer_id", "customer_addresses", ["customer_id"]
    )

    op.create_table(
        "customer_change_requests",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("requested_by", sa.Integer(), nullable=True),
        sa.Column(
            "target", sa.Enum("FISCAL", "ADDRESS", name="changerequesttarget"), nullable=False
        ),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PENDING", "APPROVED", "REJECTED", name="changerequeststatus"),
            nullable=False,
        ),
        sa.Column("reviewer_id", sa.Integer(), nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=_TS, nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["customer_users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["employees.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customer_change_requests_id", "customer_change_requests", ["id"])
    op.create_index(
        "ix_customer_change_requests_customer_id", "customer_change_requests", ["customer_id"]
    )
    op.create_index(
        "ix_customer_change_requests_status", "customer_change_requests", ["status"]
    )


def downgrade() -> None:
    op.drop_table("customer_change_requests")
    op.drop_table("customer_addresses")
    op.drop_table("customer_users")
    op.drop_table("customers")
