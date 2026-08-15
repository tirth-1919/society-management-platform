"""Make monthly maintenance idempotent per resident occupancy.

Revision ID: 20260811_bill_resident_month_uniqueness
Revises: 20260811_restore_monthly_maintenance_to_1500
"""

from alembic import op


revision = "20260811_bill_resident_month_uniqueness"
down_revision = "20260811_restore_monthly_maintenance_to_1500"
branch_labels = None
depends_on = None


def upgrade():
    # A flat can receive a new resident. The bill must belong to that resident's
    # occupancy so the replacement resident does not inherit the old account.
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.drop_constraint("uq_maintenance_bill_flat_month", type_="unique")
        batch_op.create_unique_constraint(
            "uq_maintenance_bill_resident_month", ["resident_id", "billing_month"]
        )


def downgrade():
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.drop_constraint("uq_maintenance_bill_resident_month", type_="unique")
        batch_op.create_unique_constraint(
            "uq_maintenance_bill_flat_month", ["flat_id", "billing_month"]
        )
