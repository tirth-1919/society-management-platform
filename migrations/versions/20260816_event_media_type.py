"""Add media type to the existing event photo/media records."""
from alembic import op
import sqlalchemy as sa

revision = "20260816_event_media_type"
down_revision = "20260815_event_photo_hardening"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if "event_photos" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("event_photos")}
        if "media_type" not in columns:
            op.add_column(
                "event_photos",
                sa.Column(
                    "media_type",
                    sa.String(10),
                    nullable=False,
                    server_default="PHOTO",
                ),
            )
        indexes = {i["name"] for i in inspector.get_indexes("event_photos")}
        if "ix_event_photos_media_type" not in indexes:
            op.create_index(
                "ix_event_photos_media_type",
                "event_photos",
                ["media_type"],
            )


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if "event_photos" in inspector.get_table_names():
        indexes = {i["name"] for i in inspector.get_indexes("event_photos")}
        if "ix_event_photos_media_type" in indexes:
            op.drop_index("ix_event_photos_media_type", table_name="event_photos")
        columns = {c["name"] for c in inspector.get_columns("event_photos")}
        if "media_type" in columns:
            with op.batch_alter_table("event_photos", schema=None) as batch_op:
                batch_op.drop_column("media_type")

