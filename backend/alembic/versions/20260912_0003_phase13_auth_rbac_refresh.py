"""Phase 1.3: auth, RBAC, employer isolation.

Adds:
- users.role (NOT NULL, server_default 'employee')
- refresh_tokens table
- employer_admins table

Revision ID: 20260912_0003
Revises: 20260911_0002
Create Date: 2026-09-12 00:00:00
"""

import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision = "20260912_0003"
down_revision = "20260911_0002"
branch_labels = None
depends_on = None

_PHASE13_TABLES = frozenset({"refresh_tokens", "employer_admins"})
_PHASE12_TABLES = frozenset({"employers", "employees", "employments", "salary_profiles"})
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


def _alembic_version_number() -> str | None:
    tables = _table_names()
    if "alembic_version" not in tables:
        return None
    row = op.get_bind().execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def _add_phase13() -> None:
    # users.role — additive, non-destructive. Legacy rows default to employee.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_cols = {col["name"] for col in inspector.get_columns("users")}
    existing_tables = set(inspector.get_table_names())

    if "role" not in user_cols:
        op.add_column(
            "users",
            sa.Column("role", sa.String(), nullable=False, server_default="employee"),
        )

    if "refresh_tokens" not in existing_tables:
        op.create_table(
            "refresh_tokens",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("token_hash", sa.String(), nullable=False),
            sa.Column("family_id", sa.String(), nullable=False),
            sa.Column(
                "rotated_from_id",
                sa.String(),
                sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
        )
        op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)
        op.create_index("ix_refresh_tokens_family_id", "refresh_tokens", ["family_id"], unique=False)
        op.create_index("ix_refresh_tokens_revoked_at", "refresh_tokens", ["revoked_at"], unique=False)

    if "employer_admins" not in existing_tables:
        op.create_table(
            "employer_admins",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column(
                "user_id",
                sa.String(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "employer_id",
                sa.String(),
                sa.ForeignKey("employers.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", "employer_id", name="uq_employer_admins_user_employer"),
        )
        op.create_index("ix_employer_admins_user_id", "employer_admins", ["user_id"], unique=False)
        op.create_index("ix_employer_admins_employer_id", "employer_admins", ["employer_id"], unique=False)


def _drop_phase13() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())
    user_cols = {col["name"] for col in inspector.get_columns("users")}

    if "employer_admins" in existing_tables:
        op.drop_index("ix_employer_admins_employer_id", table_name="employer_admins")
        op.drop_index("ix_employer_admins_user_id", table_name="employer_admins")
        op.drop_table("employer_admins")
    if "refresh_tokens" in existing_tables:
        op.drop_index("ix_refresh_tokens_revoked_at", table_name="refresh_tokens")
        op.drop_index("ix_refresh_tokens_family_id", table_name="refresh_tokens")
        op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
        op.drop_table("refresh_tokens")
    if "role" in user_cols:
        op.drop_column("users", "role")


def upgrade() -> None:
    tables = _table_names()
    version = _alembic_version_number()

    # Phase 1.3 already applied.
    if version == "20260912_0003":
        return

    # Baseline detection: require Phase 1.2 tables present before applying.
    if _PHASE12_TABLES.issubset(tables) or version == "20260911_0002":
        _add_phase13()
        return

    # Legacy baseline: application tables present but no alembic history.
    existing_application_tables = tables & _APPLICATION_TABLES
    if existing_application_tables:
        missing = _APPLICATION_TABLES - tables
        if missing:
            missing = ", ".join(sorted(missing))
            raise RuntimeError(
                "Refusing to baseline a partial legacy database; missing tables: " + missing
            )
        _add_phase13()
        return

    # Fresh database: apply everything.
    _add_phase13()


def downgrade() -> None:
    version = _alembic_version_number()
    if version == "20260912_0003":
        bind = op.get_bind()
        tables = set(sa.inspect(bind).get_table_names())
        user_cols = {col["name"] for col in sa.inspect(bind).get_columns("users")}
        if _PHASE13_TABLES.issubset(tables) or "role" in user_cols:
            _drop_phase13()
        return
    if version in ("20260911_0002", "20260911_0001"):
        # Nothing to remove for this phase.
        return