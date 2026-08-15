"""Persist maintenance start month and notification idempotency.

Revision ID: 20260811_maintenance_start_and_notification_idempotency
Revises: 20260811_notification_log_user_fields
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_maintenance_start_and_notification_idempotency"
down_revision = "20260811_notification_log_user_fields"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "maintenance_start_month" not in user_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("maintenance_start_month", sa.String(length=7), nullable=True)
            )

    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_notification_log_user_month_type",
            ["user_id", "billing_month", "notification_type"],
        )


def downgrade():
    with op.batch_alter_table("notification_logs", schema=None) as batch_op:
        batch_op.drop_constraint("uq_notification_log_user_month_type", type_="unique")
