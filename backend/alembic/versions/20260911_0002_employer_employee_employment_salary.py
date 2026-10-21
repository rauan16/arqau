"""Add employer, employee, employment, and salary profile tables."""

import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision = "20260911_0002"
down_revision = "20260911_0001"
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
_NEW_TABLES = frozenset({"employers", "employees", "employments", "salary_profiles"})


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _alembic_version_number() -> str | None:
    tables = _table_names()
    if "alembic_version" not in tables:
        return None
    row = op.get_bind().execute(
        text("SELECT version_num FROM alembic_version")
    ).fetchone()
    return row[0] if row else None


def _create_new_tables() -> None:
    op.create_table(
        "employers",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("legal_name", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("registration_number", sa.String(), nullable=True),
        sa.Column("country", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employers_status", "employers", ["status"], unique=False)
    op.create_table(
        "employees",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), sa.ForeignKey("users.id", ondelete="NO ACTION"), nullable=False, unique=True),
        sa.Column("external_employee_id", sa.String(), nullable=True),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_employees_status", "employees", ["status"], unique=False)
    op.create_index("ix_employees_user_id", "employees", ["user_id"], unique=True)
    op.create_table(
        "employments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("employee_id", sa.String(), sa.ForeignKey("employees.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("employer_id", sa.String(), sa.ForeignKey("employers.id", ondelete="NO ACTION"), nullable=False),
        sa.Column("employment_type", sa.String(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("start_date", sa.DateTime(), nullable=True),
        sa.Column("end_date", sa.DateTime(), nullable=True),
        sa.Column("eligible_from", sa.DateTime(), nullable=True),
        sa.Column("eligible_to", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "(end_date IS NULL OR end_date >= start_date) AND (eligible_to IS NULL OR eligible_to >= eligible_from)",
            name="ck_employments_dates",
        ),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="NO ACTION"),
        sa.ForeignKeyConstraint(["employer_id"], ["employers.id"], ondelete="NO ACTION"),
    )
    op.create_index("ix_employments_employee_id", "employments", ["employee_id"], unique=False)
    op.create_index("ix_employments_employer_id", "employments", ["employer_id"], unique=False)
    op.create_index("ix_employments_status", "employments", ["status"], unique=False)
    op.create_table(
        "salary_profiles",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("employment_id", sa.String(), sa.ForeignKey("employments.id", ondelete="NO ACTION"), nullable=False, unique=True),
        sa.Column("currency", sa.String(), server_default="USD"),
        sa.Column("monthly_salary_amount_minor", sa.Integer(), nullable=False),
        sa.Column("pay_schedule", sa.String(), server_default="monthly"),
        sa.Column("payday_day", sa.Integer(), nullable=True),
        sa.Column("effective_from", sa.DateTime(), nullable=False),
        sa.Column("effective_to", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(), server_default="active"),
        sa.Column("source", sa.String(), server_default="manual"),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), onupdate=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "(effective_to IS NULL OR effective_to >= effective_from)",
            name="ck_salary_profiles_effective_dates",
        ),
    )
    op.create_index("ix_salary_profiles_status", "salary_profiles", ["status"], unique=False)
    op.create_index("ix_salary_profiles_employment_id", "salary_profiles", ["employment_id"], unique=True)


def _drop_new_tables() -> None:
    op.drop_index("ix_salary_profiles_status", table_name="salary_profiles")
    op.drop_index("ix_salary_profiles_employment_id", table_name="salary_profiles")
    op.drop_table("salary_profiles")
    op.drop_index("ix_employments_status", table_name="employments")
    op.drop_index("ix_employments_employer_id", table_name="employments")
    op.drop_index("ix_employments_employee_id", table_name="employments")
    op.drop_table("employments")
    op.drop_index("ix_employees_status", table_name="employees")
    op.drop_index("ix_employees_user_id", table_name="employees")
    op.drop_table("employees")
    op.drop_index("ix_employers_status", table_name="employers")
    op.drop_table("employers")


def upgrade() -> None:
    tables = _table_names()
    version = _alembic_version_number()
    existing_application_tables = tables & _APPLICATION_TABLES

    if version == "20260911_0001":
        _create_new_tables()
        return

    if existing_application_tables:
        missing_tables = _APPLICATION_TABLES - tables
        if missing_tables:
            missing = ", ".join(sorted(missing_tables))
            raise RuntimeError(
                "Refusing to baseline a partial legacy database; missing tables: " + missing
            )
        return

    _create_new_tables()


def downgrade() -> None:
    version = _alembic_version_number()
    if version in ("20260911_0002", "20260911_0001"):
        tables = _table_names()
        if _NEW_TABLES.issubset(tables):
            _drop_new_tables()
        elif version == "20260911_0002":
            raise RuntimeError("Phase 1.2 tables are missing before downgrade")

