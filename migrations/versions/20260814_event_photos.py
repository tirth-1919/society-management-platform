"Create tenant-scoped event photo gallery table."""
from alembic import op
import sqlalchemy as sa
revision = "20260814_event_photos"
down_revision = "20260813_support_requests_and_notification_preferences"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "events" not in inspector.get_table_names():
        op.create_table("events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("society_id", sa.Integer(), sa.ForeignKey("societies.id"), nullable=False),
            sa.Column("title", sa.String(150), nullable=False), sa.Column("description", sa.Text()),
            sa.Column("cover_photo_url", sa.String(255)), sa.Column("start_date", sa.DateTime()),
            sa.Column("end_date", sa.DateTime()), sa.Column("location", sa.String(150)),
            sa.Column("status", sa.String(30), nullable=False, server_default="ACTIVE"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id")),
            sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
        op.create_index("ix_events_society_id", "events", ["society_id"])
        op.create_index("ix_events_status", "events", ["status"])
    if "event_photos" in inspector.get_table_names():
        return
    op.create_table("event_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("society_id", sa.Integer(), sa.ForeignKey("societies.id"), nullable=False),
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("file_path", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("original_filename", sa.String(255)), sa.Column("caption", sa.String(255)),
        sa.Column("file_size", sa.Integer()), sa.Column("content_type", sa.String(50)),
        sa.Column("content_hash", sa.String(64)), sa.Column("width", sa.Integer()), sa.Column("height", sa.Integer()),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING"),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("approved_by_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("approved_at", sa.DateTime()),
        sa.Column("rejected_by_user_id", sa.Integer(), sa.ForeignKey("users.id")), sa.Column("rejected_at", sa.DateTime()),
        sa.Column("rejection_reason", sa.String(255)), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    for name, columns in (("event_status", ["event_id", "status"]), ("society_status", ["society_id", "status"]), ("uploader_status", ["uploaded_by_user_id", "status"]), ("event_hash", ["event_id", "content_hash"]), ("created", ["created_at"])):
        op.create_index("ix_event_photos_" + name, "event_photos", columns)

def downgrade():
    if "event_photos" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("event_photos")
