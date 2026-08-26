"Add event media featured, cover, and download controls."""
from alembic import op
import sqlalchemy as sa
revision = "20260817_event_media_controls"
down_revision = "20260816_event_media_type"
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    tables = inspector.get_table_names()
    if "events" in tables:
        columns = {c["name"] for c in inspector.get_columns("events")}
        if "cover_media_id" not in columns:
            op.add_column("events", sa.Column("cover_media_id", sa.Integer(), nullable=True))
        if "allow_resident_downloads" not in columns:
            op.add_column("events", sa.Column("allow_resident_downloads", sa.Boolean(), nullable=False, server_default=sa.false()))
    if "event_photos" in tables:
        columns = {c["name"] for c in inspector.get_columns("event_photos")}
        if "featured_by_user_id" not in columns:
            op.add_column("event_photos", sa.Column("featured_by_user_id", sa.Integer(), nullable=True))
        if "featured_at" not in columns:
            op.add_column("event_photos", sa.Column("featured_at", sa.DateTime(), nullable=True))
        indexes = {i["name"] for i in sa.inspect(op.get_bind()).get_indexes("event_photos")}
        if "ix_event_photos_featured" not in indexes:
            op.create_index("ix_event_photos_featured", "event_photos", ["event_id", "is_featured", "status"])

def downgrade():
    pass
