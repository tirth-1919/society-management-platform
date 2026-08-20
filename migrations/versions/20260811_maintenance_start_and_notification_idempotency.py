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


UNIQUE_CONSTRAINT_NAME = "uq_notification_log_user_month_type"
UNIQUE_COLUMNS = ("user_id", "billing_month", "notification_type")


def _normalized_columns(columns):
    return tuple(column for column in columns if column is not None)


def _notification_uniqueness_exists(bind):
    # Return whether the required uniqueness is already enforced.
    # Existing deployments may have the named constraint, a differently named
    # unique constraint, or a unique index. Treat any exact column match as
    # already satisfied, but do not hide an object with the expected name that
    # protects a different column set.
    inspector = sa.inspect(bind)
    expected = UNIQUE_COLUMNS
    constraints = inspector.get_unique_constraints("notification_logs")
    indexes = inspector.get_indexes("notification_logs")

    named_object = None
    for item in constraints:
        if item.get("name") == UNIQUE_CONSTRAINT_NAME:
            named_object = item
        if _normalized_columns(tuple(item.get("column_names") or ())) == expected:
            return True
    for item in indexes:
        if item.get("name") == UNIQUE_CONSTRAINT_NAME:
            named_object = item
        if item.get("unique") and _normalized_columns(tuple(item.get("column_names") or ())) == expected:
            return True
    if named_object is not None:
        actual = _normalized_columns(tuple(named_object.get("column_names") or ()))
        raise RuntimeError(
            f"{UNIQUE_CONSTRAINT_NAME} already exists on notification_logs "
            f"with columns {actual}, expected {expected}"
        )
    return False

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "maintenance_start_month" not in user_columns:
        with op.batch_alter_table("users", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column("maintenance_start_month", sa.String(length=7), nullable=True)
            )

    if not _notification_uniqueness_exists(bind):
        with op.batch_alter_table("notification_logs", schema=None) as batch_op:
            batch_op.create_unique_constraint(
                UNIQUE_CONSTRAINT_NAME,
                list(UNIQUE_COLUMNS),
            )


def downgrade():
    bind = op.get_bind()
    if _notification_uniqueness_exists(bind):
        with op.batch_alter_table("notification_logs", schema=None) as batch_op:
            batch_op.drop_constraint(UNIQUE_CONSTRAINT_NAME, type_="unique")
