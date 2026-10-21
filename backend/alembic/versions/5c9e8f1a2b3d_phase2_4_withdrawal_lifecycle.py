"""phase2_4_withdrawal_lifecycle

Revision ID: 5c9e8f1a2b3d
Revises: 4b8dc4775b9b
Create Date: 2026-09-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5c9e8f1a2b3d'
down_revision: Union[str, Sequence[str], None] = '4b8dc4775b9b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch mode for SQLite compatibility (foreign keys need table rebuild)
    with op.batch_alter_table("wage_access_requests") as batch_op:
        batch_op.add_column(sa.Column("pay_period_start", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("pay_period_end", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejected_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("paid_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("approved_by_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("rejected_by_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("cancelled_by_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("paid_by_user_id", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("idempotency_key", sa.String(), nullable=True))
        batch_op.add_column(sa.Column("updated_at", sa.DateTime(), nullable=True))
        # SQLite batch mode can add FKs via the copy-and-move strategy
        batch_op.create_foreign_key(
            "fk_wara_approved_by_user_id",
            "users",
            ["approved_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_wara_rejected_by_user_id",
            "users",
            ["rejected_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_wara_cancelled_by_user_id",
            "users",
            ["cancelled_by_user_id"],
            ["id"],
        )
        batch_op.create_foreign_key(
            "fk_wara_paid_by_user_id",
            "users",
            ["paid_by_user_id"],
            ["id"],
        )

    # Create indexes (outside batch for clarity)
    op.create_index(
        "ix_wage_access_requests_user_pay_period",
        "wage_access_requests",
        ["user_id", "pay_period_start", "pay_period_end"],
    )
    op.create_index(
        "ix_wage_access_requests_status_created",
        "wage_access_requests",
        ["status", "created_at"],
    )
    op.create_index(
        "ix_wage_access_requests_idempotency_key",
        "wage_access_requests",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index("ix_wage_access_requests_idempotency_key", table_name="wage_access_requests")
    op.drop_index("ix_wage_access_requests_status_created", table_name="wage_access_requests")
    op.drop_index("ix_wage_access_requests_user_pay_period", table_name="wage_access_requests")

    # Use batch mode to drop columns
    with op.batch_alter_table("wage_access_requests") as batch_op:
        batch_op.drop_constraint("fk_wara_paid_by_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_wara_cancelled_by_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_wara_rejected_by_user_id", type_="foreignkey")
        batch_op.drop_constraint("fk_wara_approved_by_user_id", type_="foreignkey")
        batch_op.drop_column("updated_at")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("paid_by_user_id")
        batch_op.drop_column("cancelled_by_user_id")
        batch_op.drop_column("rejected_by_user_id")
        batch_op.drop_column("approved_by_user_id")
        batch_op.drop_column("paid_at")
        batch_op.drop_column("cancelled_at")
        batch_op.drop_column("rejected_at")
        batch_op.drop_column("approved_at")
        batch_op.drop_column("pay_period_end")
        batch_op.drop_column("pay_period_start")