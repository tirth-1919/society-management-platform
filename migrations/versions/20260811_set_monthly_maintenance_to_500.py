"""Preserve configured maintenance rates.

Revision ID: 20260811_set_monthly_maintenance_to_500
Revises: 20260811_correct_legacy_maintenance_defaults
"""

revision = "20260811_set_monthly_maintenance_to_500"
down_revision = "20260811_correct_legacy_maintenance_defaults"
branch_labels = None
depends_on = None


def upgrade():
    # Do not rewrite existing society configuration based on its numeric value.
    pass


def downgrade():
    # No data was changed by upgrade; there is nothing to reverse.
    pass

