"""convert money fields from Float to Numeric(12,2)

Revision ID: a1f2money001
Revises: 6b003a86a122
Create Date: 2026-06-02

Money columns move from FLOAT to NUMERIC(12,2) for exact monetary storage
(no binary-float drift). Quantities/stock stay FLOAT on purpose. Uses batch
mode so the migration also works on SQLite.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a1f2money001"
down_revision: Union[str, None] = "6b003a86a122"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (table, column, nullable)
_MONEY_COLUMNS = [
    ("products", "price_cost", True),
    ("movement_lines", "unit_price", True),
    ("employees", "salary_base", False),
    ("payrolls", "salary_base", False),
    ("payrolls", "bonuses", False),
    ("payrolls", "deductions", False),
    ("payrolls", "net_salary", False),
    ("truck_schedules", "estimated_cost", True),
    ("truck_schedules", "actual_cost", True),
]


def upgrade() -> None:
    for table, column, nullable in _MONEY_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                type_=sa.Numeric(12, 2),
                existing_type=sa.Float(),
                existing_nullable=nullable,
            )


def downgrade() -> None:
    for table, column, nullable in _MONEY_COLUMNS:
        with op.batch_alter_table(table) as batch_op:
            batch_op.alter_column(
                column,
                type_=sa.Float(),
                existing_type=sa.Numeric(12, 2),
                existing_nullable=nullable,
            )
