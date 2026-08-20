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


def _existing_columns():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {
        column["name"]
        for column in inspector.get_columns("notification_logs")
    }


def _existing_indexes():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return {
        index["name"]
        for index in inspector.get_indexes("notification_logs")
    }


def upgrade():
    """Add notification fields without rebuilding the SQLite table."""

    columns = _existing_columns()

    if "user_id" not in columns:
        op.add_column(
            "notification_logs",
            sa.Column(
                "user_id",
                sa.Integer(),
                nullable=True,
            ),
        )

    if "notification_type" not in columns:
        op.add_column(
            "notification_logs",
            sa.Column(
                "notification_type",
                sa.String(length=50),
                nullable=True,
            ),
        )

    if "billing_month" not in columns:
        op.add_column(
            "notification_logs",
            sa.Column(
                "billing_month",
                sa.String(length=7),
                nullable=True,
            ),
        )

    if "sent_at" not in columns:
        op.add_column(
            "notification_logs",
            sa.Column(
                "sent_at",
                sa.DateTime(),
                nullable=True,
            ),
        )

    indexes = _existing_indexes()

    if "ix_notification_logs_user_id" not in indexes:
        op.create_index(
            "ix_notification_logs_user_id",
            "notification_logs",
            ["user_id"],
            unique=False,
        )

    if "ix_notification_logs_notification_type" not in indexes:
        op.create_index(
            "ix_notification_logs_notification_type",
            "notification_logs",
            ["notification_type"],
            unique=False,
        )

    if "ix_notification_logs_billing_month" not in indexes:
        op.create_index(
            "ix_notification_logs_billing_month",
            "notification_logs",
            ["billing_month"],
            unique=False,
        )


def downgrade():
    indexes = _existing_indexes()
    columns = _existing_columns()

    if "ix_notification_logs_billing_month" in indexes:
        op.drop_index(
            "ix_notification_logs_billing_month",
            table_name="notification_logs",
        )

    if "ix_notification_logs_notification_type" in indexes:
        op.drop_index(
            "ix_notification_logs_notification_type",
            table_name="notification_logs",
        )

    if "ix_notification_logs_user_id" in indexes:
        op.drop_index(
            "ix_notification_logs_user_id",
            table_name="notification_logs",
        )

    # Only remove columns that this migration added.
    if "sent_at" in columns:
        op.drop_column("notification_logs", "sent_at")

    if "billing_month" in columns:
        op.drop_column("notification_logs", "billing_month")

    if "notification_type" in columns:
        op.drop_column("notification_logs", "notification_type")

    if "user_id" in columns:
        op.drop_column("notification_logs", "user_id")