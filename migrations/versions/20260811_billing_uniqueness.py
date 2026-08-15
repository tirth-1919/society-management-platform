"""Add idempotent maintenance billing constraint."""

from alembic import op


revision = "20260811_billing_uniqueness"
down_revision = "c32a0ce0c443"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_maintenance_bill_flat_month", ["flat_id", "billing_month"]
        )


def downgrade():
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.drop_constraint("uq_maintenance_bill_flat_month", type_="unique")
