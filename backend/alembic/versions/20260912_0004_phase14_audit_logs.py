"""Phase 1.4: additive audit trail."""

import sqlalchemy as sa
from sqlalchemy import text
from alembic import op

revision = "20260912_0004"
down_revision = "20260912_0003"
branch_labels = None
depends_on = None

_AUDIT_TABLE = "audit_logs"
_AUDIT_INDEXES = (
    "ix_audit_logs_actor_user_id",
    "ix_audit_logs_employer_id",
    "ix_audit_logs_action",
    "ix_audit_logs_entity_type",
    "ix_audit_logs_entity_id",
    "ix_audit_logs_request_id",
    "ix_audit_logs_created_at",
    "ix_audit_logs_action_created",
    "ix_audit_logs_employer_created",
    "ix_audit_logs_actor_created",
)


def _table_names() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _alembic_version_number() -> str | None:
    if _AUDIT_TABLE not in _table_names():
        return None
    if "alembic_version" not in _table_names():
        return None
    row = op.get_bind().execute(text("SELECT version_num FROM alembic_version")).fetchone()
    return row[0] if row else None


def _create_audit_logs() -> None:
    if _AUDIT_TABLE in _table_names():
        return
    op.create_table(
        _AUDIT_TABLE,
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "employer_id",
            sa.String(),
            sa.ForeignKey("employers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=True),
        sa.Column("entity_id", sa.String(), nullable=True),
        sa.Column("request_id", sa.String(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=True),
        sa.Column("before_data", sa.JSON(), nullable=True),
        sa.Column("after_data", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    for index_name in _AUDIT_INDEXES:
        columns = {
            "ix_audit_logs_action_created": ["action", "created_at"],
            "ix_audit_logs_employer_created": ["employer_id", "created_at"],
            "ix_audit_logs_actor_created": ["actor_user_id", "created_at"],
        }.get(index_name, [index_name.removeprefix("ix_audit_logs_")])
        op.create_index(index_name, _AUDIT_TABLE, columns, unique=False)


def _drop_audit_logs() -> None:
    tables = _table_names()
    if _AUDIT_TABLE not in tables:
        return
    existing_indexes = {
        index["name"] for index in sa.inspect(op.get_bind()).get_indexes(_AUDIT_TABLE)
    }
    for index_name in _AUDIT_INDEXES:
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name=_AUDIT_TABLE)
    op.drop_table(_AUDIT_TABLE)


def upgrade() -> None:
    if _alembic_version_number() == revision:
        return
    _create_audit_logs()


def downgrade() -> None:
    if _alembic_version_number() == revision:
        _drop_audit_logs()
