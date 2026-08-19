"""Set the standard monthly maintenance rate to ₹500.

Revision ID: 20260811_set_monthly_maintenance_to_500
Revises: 20260811_correct_legacy_maintenance_defaults
"""

from alembic import op


revision = "20260811_set_monthly_maintenance_to_500"
down_revision = "20260811_correct_legacy_maintenance_defaults"
branch_labels = None
depends_on = None


def upgrade():
    # Apply the new standard rate to societies still using the former default.
    # Existing bills are intentionally left unchanged as historical records.
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 500.0 "
        "WHERE fixed_monthly_rate = 1500.0"
    )


def downgrade():
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 1500.0 "
        "WHERE fixed_monthly_rate = 500.0"
    )

