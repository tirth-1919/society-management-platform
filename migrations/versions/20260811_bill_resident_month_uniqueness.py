"""Make monthly maintenance idempotent per resident occupancy.

Revision ID: 20260811_bill_resident_month_uniqueness
Revises: 20260811_restore_monthly_maintenance_to_1500
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_bill_resident_month_uniqueness"
down_revision = "20260811_restore_monthly_maintenance_to_1500"
branch_labels = None
depends_on = None


EXPECTED_CONSTRAINT = "uq_maintenance_bill_resident_month"
EXPECTED_COLUMNS = ("resident_id", "billing_month")


def _columns(item):
    return tuple(item.get("column_names") or ())


def _uniqueness_objects(bind):
    inspector = sa.inspect(bind)
    constraints = inspector.get_unique_constraints("maintenance_bills")
    indexes = [
        index for index in inspector.get_indexes("maintenance_bills")
        if index.get("unique")
    ]
    return constraints, indexes

def _required_uniqueness_exists(bind):
    constraints, indexes = _uniqueness_objects(bind)
    named_object = next(
        (
            item for item in constraints + indexes
            if item.get("name") == EXPECTED_CONSTRAINT
        ),
        None,
    )
    for item in constraints + indexes:
        if _columns(item) == EXPECTED_COLUMNS:
            return True
    if named_object is not None:
        raise RuntimeError(
            f"{EXPECTED_CONSTRAINT} exists on maintenance_bills with columns "
            f"{_columns(named_object)}, expected {EXPECTED_COLUMNS}"
        )
    return False


def upgrade():
    # A flat can receive a new resident. The bill must belong to that resident's
    # occupancy so the replacement resident does not inherit the old account.
    bind = op.get_bind()
    new_exists = _required_uniqueness_exists(bind)

    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        # This migration is additive for production safety. The legacy
        # flat/month uniqueness protects a different invariant and must remain.
        if not new_exists:
            batch_op.create_unique_constraint(
                EXPECTED_CONSTRAINT, list(EXPECTED_COLUMNS)
            )


def downgrade():
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.drop_constraint("uq_maintenance_bill_resident_month", type_="unique")
        batch_op.create_unique_constraint(
            "uq_maintenance_bill_flat_month", ["flat_id", "billing_month"]
        )
