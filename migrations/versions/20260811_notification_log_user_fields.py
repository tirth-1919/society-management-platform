
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


TABLE_NAME = "notification_logs"

EXPECTED_COLUMNS = {
    "user_id": sa.Column(
        "user_id",
        sa.Integer(),
        nullable=True,
    ),
    "notification_type": sa.Column(
        "notification_type",
        sa.String(length=50),
        nullable=True,
    ),
    "billing_month": sa.Column(
        "billing_month",
        sa.String(length=7),
        nullable=True,
    ),
    "sent_at": sa.Column(
        "sent_at",
        sa.DateTime(),
        nullable=True,
    ),
}

EXPECTED_INDEXES = {
    "ix_notification_logs_user_id": ["user_id"],
    "ix_notification_logs_notification_type": ["notification_type"],
    "ix_notification_logs_billing_month": ["billing_month"],
}


def _get_inspector():
    return sa.inspect(op.get_bind())


def _check_table():
    inspector = _get_inspector()

    if not inspector.has_table(TABLE_NAME):
        raise RuntimeError(
            f"Required table '{TABLE_NAME}' does not exist."
        )

    return inspector


def upgrade():
    """Add missing notification fields and indexes safely."""

    inspector = _check_table()

    existing_columns = {
        column["name"]
        for column in inspector.get_columns(TABLE_NAME)
    }

    # Add only missing columns.
    for column_name, column in EXPECTED_COLUMNS.items():
        if column_name not in existing_columns:
            op.add_column(
                TABLE_NAME,
                column.copy(),
            )
            print(
                f"[MIGRATION] Added column: {column_name}"
            )

    # Refresh index information after column changes.
    inspector = _get_inspector()

    indexes = inspector.get_indexes(TABLE_NAME)
    existing_indexes = {
        index["name"]: tuple(index.get("column_names") or ())
        for index in indexes
        if index.get("name")
    }
    existing_unique_constraints = inspector.get_unique_constraints(TABLE_NAME)
    existing_unique_index_columns = {
        tuple(item.get("column_names") or ())
        for item in indexes if item.get("unique")
    } | {
        tuple(item.get("column_names") or ())
        for item in existing_unique_constraints
    }

    # Create only missing indexes.
    for index_name, column_names in EXPECTED_INDEXES.items():
        expected_columns = tuple(column_names)
        if existing_indexes.get(index_name) not in (None, expected_columns):
            raise RuntimeError(
                f"Index '{index_name}' already exists with columns "
                f"{existing_indexes[index_name]}, expected {expected_columns}."
            )
        if (index_name not in existing_indexes
                and expected_columns not in existing_unique_index_columns
                and not any(
                    tuple(item.get("column_names") or ()) == expected_columns
                    and not item.get("unique") for item in indexes
                )):
            op.create_index(
                index_name,
                TABLE_NAME,
                column_names,
                unique=False,
            )
            print(
                f"[MIGRATION] Created index: {index_name}"
            )


def downgrade():
    """
    Intentionally preserve existing columns and indexes.

    This migration may run against a database where these fields
    existed before Alembic began tracking migrations. Automatically
    dropping them could destroy pre-existing application schema.
    """

    print(
        "[MIGRATION] Downgrade skipped to preserve existing "
        "notification schema and data."
    )
