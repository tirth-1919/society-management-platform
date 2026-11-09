
"""Retire the obsolete flat/month uniqueness revision."""

revision = "20260811_billing_uniqueness"
down_revision = "c32a0ce0c443"
branch_labels = None
depends_on = None


def upgrade():
    # The application bills per resident occupancy, as declared by
    # MaintenanceBill. The flat/month rule blocks replacement residents.
    # The following resident/month revision owns the current invariant.
    pass


def downgrade():
    # No schema change is made by this compatibility revision.
    pass
