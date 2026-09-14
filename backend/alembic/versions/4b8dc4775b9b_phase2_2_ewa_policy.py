"""phase2_2_ewa_policy

Revision ID: 4b8dc4775b9b
Revises: 20260912_0004
Create Date: 2026-09-13 23:11:32.941808
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4b8dc4775b9b'
down_revision: Union[str, Sequence[str], None] = '20260912_0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "ewa_policies",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("employer_id", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("max_access_percentage", sa.Integer(), nullable=False),
        sa.Column("max_withdrawals_per_period", sa.Integer(), nullable=True),
        sa.Column("minimum_tenure_days", sa.Integer(), nullable=True),
        sa.Column("minimum_remaining_salary_minor", sa.Integer(), nullable=True),
        sa.Column("minimum_withdrawal_minor", sa.Integer(), nullable=True),
        sa.Column("maximum_withdrawal_minor", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["employer_id"], ["employers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("employer_id", name="uq_ewa_policies_employer_id"),
        sa.CheckConstraint("max_access_percentage >= 0 AND max_access_percentage <= 100", name="ck_ewa_policy_percentage"),
        sa.CheckConstraint("max_withdrawals_per_period IS NULL OR max_withdrawals_per_period >= 0", name="ck_ewa_policy_max_withdrawals"),
        sa.CheckConstraint("minimum_tenure_days IS NULL OR minimum_tenure_days >= 0", name="ck_ewa_policy_tenure"),
        sa.CheckConstraint("minimum_remaining_salary_minor IS NULL OR minimum_remaining_salary_minor >= 0", name="ck_ewa_policy_min_remaining"),
        sa.CheckConstraint("minimum_withdrawal_minor IS NULL OR minimum_withdrawal_minor >= 0", name="ck_ewa_policy_min_withdrawal"),
        sa.CheckConstraint("maximum_withdrawal_minor IS NULL OR maximum_withdrawal_minor >= 0", name="ck_ewa_policy_max_withdrawal"),
        sa.CheckConstraint(
            "minimum_withdrawal_minor IS NULL OR maximum_withdrawal_minor IS NULL OR minimum_withdrawal_minor <= maximum_withdrawal_minor",
            name="ck_ewa_policy_withdrawal_bounds",
        ),
    )
    op.create_index("ix_ewa_policies_employer_id", "ewa_policies", ["employer_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_ewa_policies_employer_id", table_name="ewa_policies")
    op.drop_table("ewa_policies")