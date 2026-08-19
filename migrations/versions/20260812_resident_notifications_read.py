"""Add resident notification read state and merge current heads."""

from alembic import op
import sqlalchemy as sa

revision = "20260812_resident_notifications_read"
down_revision = "20260811_bill_resident_month_uniqueness"
branch_labels = None
depends_on = None


def upgrade():
    # Existing SQLite installations may have received this additive column via
    # the temporary compatibility patch during application startup.  Preserve
    # all rows and make this revision idempotent in that case.
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("notification_logs")}
    if "read_at" not in columns:
        with op.batch_alter_table("notification_logs", schema=None) as batch_op:
            batch_op.add_column(sa.Column("read_at", sa.DateTime(), nullable=True))


def downgrade():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("notification_logs")}
    if "read_at" in columns:
        with op.batch_alter_table("notification_logs", schema=None) as batch_op:
            batch_op.drop_column("read_at")
