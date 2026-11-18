"""Create the legacy-compatible application schema."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "20260911_0001"
down_revision = None
branch_labels = None
depends_on = None

_APPLICATION_TABLES = frozenset(
    {
        "users",
        "onboarding",
        "transactions",
        "budgets",
        "goals",
        "earned_wages",
        "wage_access_requests",
    }
)


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def upgrade() -> None:
    tables = _table_names()
    existing_application_tables = tables & _APPLICATION_TABLES

    if existing_application_tables:
        missing_tables = _APPLICATION_TABLES - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise RuntimeError(
                "Refusing to baseline a partial legacy database; missing tables: " + missing
            )
        return

    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("is_verified", sa.Boolean(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "onboarding",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("pay_frequency", sa.String(), nullable=True),
        sa.Column("monthly_income_range", sa.String(), nullable=True),
        sa.Column("payday_range", sa.String(), nullable=True),
        sa.Column("financial_pressure", sa.String(), nullable=True),
        sa.Column("early_access_use_case", sa.String(), nullable=True),
        sa.Column("ai_help_preference", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("category", sa.String(), nullable=True),
        sa.Column("merchant", sa.String(), nullable=True),
        sa.Column("description", sa.String(), nullable=True),
        sa.Column("date", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_table(
        "budgets",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("limit_minor", sa.Integer(), nullable=False),
        sa.Column("spent_minor", sa.Integer(), nullable=True),
        sa.Column("period", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_table(
        "goals",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("target_minor", sa.Integer(), nullable=False),
        sa.Column("current_minor", sa.Integer(), nullable=True),
        sa.Column("deadline", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )
    op.create_table(
        "earned_wages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("earned_amount_minor", sa.Integer(), nullable=True),
        sa.Column("accessed_amount_minor", sa.Integer(), nullable=True),
        sa.Column("available_amount_minor", sa.Integer(), nullable=True),
        sa.Column("period_start", sa.String(), nullable=True),
        sa.Column("period_end", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("user_id"),
    )
    op.create_table(
        "wage_access_requests",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("amount_minor", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
    )


def downgrade() -> None:
    tables = _table_names()
    existing_application_tables = tables & _APPLICATION_TABLES

    if existing_application_tables != _APPLICATION_TABLES:
        raise RuntimeError("Refusing to downgrade a partial application schema")
