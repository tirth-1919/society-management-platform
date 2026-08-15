"""Add support_requests and notification_preferences tables.

Revision ID: 20260813_support_requests_and_notification_preferences
Revises: 20260812_resident_notifications_read
Create Date: 2026-08-13

NOTE: this migration was written and syntax-checked in a sandbox without
network access to install Flask-Migrate/Alembic, so it has NOT been run
against a live database. Run and verify it (e.g. `flask db upgrade` against
a copy of the database first) before applying to production.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260813_support_requests_and_notification_preferences"
down_revision = "20260812_resident_notifications_read"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())

    if "support_requests" not in existing_tables:
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
                "status", sa.String(length=20), nullable=False, server_default="OPEN"
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        with op.batch_alter_table("support_requests", schema=None) as batch_op:
            batch_op.create_index("ix_support_requests_society_id", ["society_id"])
            batch_op.create_index("ix_support_requests_user_id", ["user_id"])
            batch_op.create_index("ix_support_requests_resident_id", ["resident_id"])
            batch_op.create_index("ix_support_requests_status", ["status"])

    if "notification_preferences" not in existing_tables:
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
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "payment_reminders",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "payment_confirmations",
                sa.Boolean(),
                nullable=False,
                server_default=sa.true(),
            ),
            sa.Column(
                "announcements", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        with op.batch_alter_table("notification_preferences", schema=None) as batch_op:
            batch_op.create_index(
                "ix_notification_preferences_society_id", ["society_id"]
            )
            batch_op.create_unique_constraint(
                "uq_notification_preferences_user_id", ["user_id"]
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    existing_tables = set(inspector.get_table_names())
    if "notification_preferences" in existing_tables:
        op.drop_table("notification_preferences")
    if "support_requests" in existing_tables:
        op.drop_table("support_requests")
