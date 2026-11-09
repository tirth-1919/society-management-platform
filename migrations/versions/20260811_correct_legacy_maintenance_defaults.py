"""Retain legacy maintenance configurations without rewriting data.

Revision ID: 20260811_correct_legacy_maintenance_defaults
Revises: 20260811_maintenance_start_and_notification_idempotency
"""

revision = "20260811_correct_legacy_maintenance_defaults"
down_revision = "20260811_maintenance_start_and_notification_idempotency"
branch_labels = None
depends_on = None


def upgrade():
    # Historical configuration values may have been chosen intentionally.
    # Schema migrations must not infer intent from matching numeric values.
    pass


def downgrade():
    # No data was changed by upgrade; there is nothing to reverse.
    pass
