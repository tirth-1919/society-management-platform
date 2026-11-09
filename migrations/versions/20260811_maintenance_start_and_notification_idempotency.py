
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

UNIQUE_COLUMNS = (
    "user_id",
    "billing_month",
    "notification_type",
)


def _normalized_columns(columns):
    return tuple(column for column in (columns or ()) if column is not None)


def _check_required_tables(bind):
    inspector = sa.inspect(bind)

    for table_name in ("users", "notification_logs"):
        if not inspector.has_table(table_name):
            raise RuntimeError(
                f"Required table '{table_name}' does not exist."
            )

    return inspector


def _notification_uniqueness_exists(bind):
    inspector = sa.inspect(bind)

    constraints = inspector.get_unique_constraints(
        "notification_logs"
    )

    indexes = inspector.get_indexes(
        "notification_logs"
    )

    named_object = None

    for item in constraints:
        columns = _normalized_columns(item.get("column_names"))

        if item.get("name") == UNIQUE_CONSTRAINT_NAME:
            named_object = item

        if columns == UNIQUE_COLUMNS:
            return True

    for item in indexes:
        columns = _normalized_columns(item.get("column_names"))

        if item.get("name") == UNIQUE_CONSTRAINT_NAME:
            named_object = item

        if item.get("unique") and columns == UNIQUE_COLUMNS:
            return True

    if named_object is not None:
        actual = _normalized_columns(
            named_object.get("column_names")
        )

        raise RuntimeError(
            f"Object '{UNIQUE_CONSTRAINT_NAME}' already exists "
            f"with columns {actual}; expected {UNIQUE_COLUMNS}."
        )

    return False


def upgrade():
    bind = op.get_bind()

    inspector = _check_required_tables(bind)

    # Add maintenance_start_month only if missing.
    user_columns = {
        column["name"]
        for column in inspector.get_columns("users")
    }

    if "maintenance_start_month" not in user_columns:
        op.add_column(
            "users",
            sa.Column(
                "maintenance_start_month",
                sa.String(length=7),
                nullable=True,
            ),
        )

        print(
            "[MIGRATION] Added users.maintenance_start_month."
        )
    else:
        print(
            "[MIGRATION] maintenance_start_month already exists. "
            "Skipping."
        )

    # Verify notification fields exist before creating uniqueness.
    inspector = sa.inspect(bind)

    notification_columns = {
        column["name"]
        for column in inspector.get_columns("notification_logs")
    }

    missing_columns = [
        column
        for column in UNIQUE_COLUMNS
        if column not in notification_columns
    ]

    if missing_columns:
        raise RuntimeError(
            "Cannot create notification uniqueness. Missing columns: "
            + ", ".join(missing_columns)
        )

    # Do not create a duplicate unique constraint or index.
    if _notification_uniqueness_exists(bind):
        print(
            "[MIGRATION] Notification uniqueness already exists. "
            "Skipping."
        )
        return

    # Check duplicates before creating the unique constraint.
    duplicate_count = bind.execute(
        sa.text("""
            SELECT COUNT(*)
            FROM (
                SELECT user_id, billing_month, notification_type
                FROM notification_logs
                WHERE user_id IS NOT NULL
                  AND billing_month IS NOT NULL
                  AND notification_type IS NOT NULL
                GROUP BY user_id, billing_month, notification_type
                HAVING COUNT(*) > 1
            ) AS duplicates
        """)
    ).scalar_one()

    if duplicate_count:
        raise RuntimeError(
            f"Found {duplicate_count} duplicate notification groups. "
            "Resolve them manually before running migrations. "
            "No notification records were deleted."
        )

    op.create_unique_constraint(
        UNIQUE_CONSTRAINT_NAME,
        "notification_logs",
        list(UNIQUE_COLUMNS),
    )

    print(
        "[MIGRATION] Notification idempotency constraint created."
    )


def downgrade():
    # Preserve existing database schema and notification data.
    # This is intentional because the migration may be adopting
    # a schema that already contained these fields or constraints.
    print(
        "[MIGRATION] Downgrade skipped to preserve existing "
        "users and notification schema."
    )
