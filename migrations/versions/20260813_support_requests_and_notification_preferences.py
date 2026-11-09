"""Add support_requests and notification_preferences tables.

Revision ID: 20260813_support_requests_and_notification_preferences
Revises: 20260812_resident_notifications_read
Create Date: 2026-08-13

Existing tables are retained. The migration validates their columns and
adds only missing indexes; it does not rebuild or drop existing objects.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_support_requests_and_notification_preferences"
down_revision = "20260812_resident_notifications_read"
branch_labels = None
depends_on = None


TABLE_COLUMNS = {
    "support_requests": {
        "id", "society_id", "user_id", "resident_id", "subject",
        "category", "message", "status", "created_at", "updated_at",
    },
    "notification_preferences": {
        "id", "society_id", "user_id", "resident_id",
        "maintenance_reminders", "payment_reminders",
        "payment_confirmations", "announcements", "created_at", "updated_at",
    },
}

TABLE_INDEXES = {
    "support_requests": {
        "ix_support_requests_society_id": ["society_id"],
        "ix_support_requests_user_id": ["user_id"],
        "ix_support_requests_resident_id": ["resident_id"],
        "ix_support_requests_status": ["status"],
    },
    "notification_preferences": {
        "ix_notification_preferences_society_id": ["society_id"],
        "ix_notification_preferences_user_id": ["user_id"],
        "ix_notification_preferences_resident_id": ["resident_id"],
    },
}


def _ensure_table(inspector, name, create):
    if not inspector.has_table(name):
        create()
        inspector = sa.inspect(op.get_bind())
    else:
        columns = {column["name"] for column in inspector.get_columns(name)}
        missing = TABLE_COLUMNS[name] - columns
        if missing:
            raise RuntimeError(
                f"Existing '{name}' table is missing columns: "
                f"{', '.join(sorted(missing))}. No table was rebuilt."
            )

    indexes = inspector.get_indexes(name)
    constraints = inspector.get_unique_constraints(name)
    by_name = {
        item["name"]: tuple(item.get("column_names") or ())
        for item in indexes + constraints if item.get("name")
    }
    by_columns = {
        tuple(item.get("column_names") or ())
        for item in indexes + constraints
    }
    for index_name, columns in TABLE_INDEXES[name].items():
        expected = tuple(columns)
        if index_name in by_name and by_name[index_name] != expected:
            raise RuntimeError(
                f"Object '{index_name}' exists on '{name}' with columns "
                f"{by_name[index_name]}, expected {expected}."
            )
        if index_name not in by_name and expected not in by_columns:
            op.create_index(index_name, name, columns, unique=False)
            by_columns.add(expected)


def upgrade():
    inspector = sa.inspect(op.get_bind())

    def create_support_requests():
        op.create_table(
            "support_requests",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "society_id",
                sa.Integer(),
                sa.ForeignKey("societies.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "resident_id",
                sa.Integer(),
                sa.ForeignKey("residents.id"),
                nullable=True,
            ),
            sa.Column("subject", sa.String(length=150), nullable=False),
            sa.Column("category", sa.String(length=30), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column(
                "status", sa.String(length=20), nullable=True
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )

    def create_notification_preferences():
        op.create_table(
            "notification_preferences",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "society_id",
                sa.Integer(),
                sa.ForeignKey("societies.id"),
                nullable=False,
            ),
            sa.Column(
                "user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False
            ),
            sa.Column(
                "resident_id",
                sa.Integer(),
                sa.ForeignKey("residents.id"),
                nullable=True,
            ),
            sa.Column(
                "maintenance_reminders",
                sa.Boolean(), nullable=False
            ),
            sa.Column(
                "payment_reminders",
                sa.Boolean(), nullable=False
            ),
            sa.Column(
                "payment_confirmations",
                sa.Boolean(), nullable=False
            ),
            sa.Column(
                "announcements", sa.Boolean(), nullable=False
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "user_id", name="uq_notification_preferences_user_id"
            ),
        )

    _ensure_table(inspector, "support_requests", create_support_requests)
    inspector = sa.inspect(op.get_bind())
    _ensure_table(
        inspector, "notification_preferences", create_notification_preferences
    )

    # Preserve the model's one-preference-per-user invariant, including when
    # adopting a pre-existing table that lacked the unique object.
    inspector = sa.inspect(op.get_bind())
    unique_user = any(
        tuple(item.get("column_names") or ()) == ("user_id",)
        for item in inspector.get_unique_constraints("notification_preferences")
    ) or any(
        item.get("unique")
        and tuple(item.get("column_names") or ()) == ("user_id",)
        for item in inspector.get_indexes("notification_preferences")
    )
    if not unique_user:
        duplicate_count = op.get_bind().execute(sa.text("""
            SELECT COUNT(*) FROM (
                SELECT user_id FROM notification_preferences
                GROUP BY user_id HAVING COUNT(*) > 1
            ) AS duplicates
        """)).scalar_one()
        if duplicate_count:
            raise RuntimeError(
                f"Found {duplicate_count} duplicate notification preference "
                "user groups. Resolve them manually before adding uniqueness. "
                "No preference records were changed."
            )
        op.create_unique_constraint(
            "uq_notification_preferences_user_id",
            "notification_preferences",
            ["user_id"],
        )


def downgrade():
    # These tables may predate Alembic adoption and may contain user data.
    pass
