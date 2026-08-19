<<<<<<< HEAD
"""Restore the standard monthly maintenance rate to ₹1,500.
=======
﻿"""Restore the standard monthly maintenance rate to ₹1,500.
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

Revision ID: 20260811_restore_monthly_maintenance_to_1500
Revises: 20260811_set_monthly_maintenance_to_500
"""

from alembic import op


revision = "20260811_restore_monthly_maintenance_to_1500"
down_revision = "20260811_set_monthly_maintenance_to_500"
branch_labels = None
depends_on = None


def upgrade():
    # Correct only the former application default. Historical bill amounts stay intact.
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 1500.0 "
        "WHERE fixed_monthly_rate = 500.0"
    )


def downgrade():
    op.execute(
        "UPDATE maintenance_configs "
        "SET fixed_monthly_rate = 500.0 "
        "WHERE fixed_monthly_rate = 1500.0"
    )

