"""Add resident notification ownership and billing fields.

Revision ID: 20260811_notification_log_user_fields
Revises: 20260811_billing_uniqueness
Create Date: 2026-08-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_notification_log_user_fields"
down_revision = "20260811_billing_uniqueness"
branch_labels = None
depends_on = None


def upgrade():
    """Extend the legacy table without altering or discarding its rows."""
    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", name="fk_notification_logs_user_id_users"),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column("notification_type", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("billing_month", sa.String(length=7), nullable=True)
        )
        batch_op.add_column(sa.Column("sent_at", sa.DateTime(), nullable=True))
        batch_op.create_index("ix_notification_logs_user_id", ["user_id"], unique=False)
        batch_op.create_index(
            "ix_notification_logs_notification_type",
            ["notification_type"],
            unique=False,
        )
        batch_op.create_index(
            "ix_notification_logs_billing_month", ["billing_month"], unique=False
        )


def downgrade():
    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_notification_logs_billing_month")
        batch_op.drop_index("ix_notification_logs_notification_type")
        batch_op.drop_index("ix_notification_logs_user_id")
        batch_op.drop_column("sent_at")
        batch_op.drop_column("billing_month")
        batch_op.drop_column("notification_type")
        batch_op.drop_column("user_id")
