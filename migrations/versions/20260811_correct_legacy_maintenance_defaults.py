"""Correct legacy seeded maintenance defaults.

Revision ID: 20260811_correct_legacy_maintenance_defaults
Revises: 20260811_maintenance_start_and_notification_idempotency
"""

from alembic import op


revision = "20260811_correct_legacy_maintenance_defaults"
down_revision = "20260811_maintenance_start_and_notification_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    # Only replace the obsolete seed defaults; preserve intentional custom rates.
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 1500.0, late_fee_per_month = 500.0 "
        "WHERE fixed_monthly_rate = 500.0 AND late_fee_per_month = 100.0"
    )


def downgrade():
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 500.0, late_fee_per_month = 100.0 "
        "WHERE fixed_monthly_rate = 1500.0 AND late_fee_per_month = 500.0"
    )
