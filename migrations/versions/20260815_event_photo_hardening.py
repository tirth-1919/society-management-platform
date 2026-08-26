"""Harden event photo quotas, history, replacements, and reports."""
from alembic import op
import sqlalchemy as sa

revision = "20260815_event_photo_hardening"
down_revision = "20260814_event_photos"
branch_labels = None
depends_on = None


def _has_column(inspector, table, column):
    return table in inspector.get_table_names() and column in {c["name"] for c in inspector.get_columns(table)}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "events" in inspector.get_table_names() and not _has_column(inspector, "events", "photo_upload_deadline"):
        op.add_column("events", sa.Column("photo_upload_deadline", sa.DateTime(), nullable=True))
    if "event_photos" in inspector.get_table_names():
        for name, column in (
            ("replacement_for_id", sa.Column("replacement_for_id", sa.Integer(), sa.ForeignKey("event_photos.id"), nullable=True)),
            ("archived_by_user_id", sa.Column("archived_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True)),
            ("archived_at", sa.Column("archived_at", sa.DateTime(), nullable=True)),
            ("archive_reason", sa.Column("archive_reason", sa.String(255), nullable=True)),
        ):
            if not _has_column(inspector, "event_photos", name):
                op.add_column("event_photos", column)
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("event_photos")}
        if "ix_event_photos_replacement_for_id" not in indexes:
            op.create_index("ix_event_photos_replacement_for_id", "event_photos", ["replacement_for_id"])
    if "event_photo_storage_usage" not in inspector.get_table_names():
        op.create_table("event_photo_storage_usage", sa.Column("society_id", sa.Integer(), sa.ForeignKey("societies.id"), primary_key=True), sa.Column("used_bytes", sa.BigInteger(), nullable=False, server_default="0"), sa.Column("updated_at", sa.DateTime(), nullable=False))
    if "event_photo_moderation_history" not in inspector.get_table_names():
        op.create_table("event_photo_moderation_history", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("society_id", sa.Integer(), sa.ForeignKey("societies.id"), nullable=False), sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False), sa.Column("photo_id", sa.Integer(), sa.ForeignKey("event_photos.id"), nullable=False), sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("action", sa.String(20), nullable=False), sa.Column("previous_status", sa.String(20)), sa.Column("new_status", sa.String(20)), sa.Column("reason", sa.String(255)), sa.Column("created_at", sa.DateTime(), nullable=False))
        op.create_index("ix_event_photo_history_photo_created", "event_photo_moderation_history", ["photo_id", "created_at"])
    if "event_photo_reports" not in inspector.get_table_names():
        op.create_table("event_photo_reports", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("society_id", sa.Integer(), sa.ForeignKey("societies.id"), nullable=False), sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False), sa.Column("photo_id", sa.Integer(), sa.ForeignKey("event_photos.id"), nullable=False), sa.Column("reported_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False), sa.Column("reason", sa.String(40), nullable=False), sa.Column("description", sa.String(1000)), sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"), sa.Column("reviewed_by_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("reviewed_at", sa.DateTime()), sa.Column("admin_action", sa.String(20)), sa.Column("created_at", sa.DateTime(), nullable=False), sa.Column("updated_at", sa.DateTime(), nullable=False), sa.UniqueConstraint("photo_id", "reported_by_user_id", "reason", "status", name="uq_event_photo_active_report"))
        op.create_index("ix_event_photo_reports_society_status", "event_photo_reports", ["society_id", "status"])


def downgrade():
    # Historical gallery data is intentionally retained; downgrade is non-destructive.
    pass
