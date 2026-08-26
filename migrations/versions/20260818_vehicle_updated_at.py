"""Add updated_at to vehicles table."""

from alembic import op
import sqlalchemy as sa


revision = "20260818_vehicle_updated_at"
down_revision = "20260817_event_media_controls"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())

    if "vehicles" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("vehicles")}

    if "updated_at" not in columns:
        op.add_column(
            "vehicles",
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=True,
            ),
        )


def downgrade():
    inspector = sa.inspect(op.get_bind())

    if "vehicles" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("vehicles")}

    if "updated_at" in columns:
        op.drop_column("vehicles", "updated_at")
