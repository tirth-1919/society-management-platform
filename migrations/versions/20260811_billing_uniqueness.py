"""Add idempotent maintenance billing constraint."""

from alembic import op
import sqlalchemy as sa


revision = "20260811_billing_uniqueness"
down_revision = "c32a0ce0c443"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # Remove duplicate maintenance bills before creating the
    # unique constraint on (flat_id, billing_month).
    #
    # Keep the oldest bill (lowest id) for each flat/month combination.
    bind.execute(
        sa.text(
            """
            DELETE FROM maintenance_bills
            WHERE id NOT IN (
                SELECT MIN(id)
                FROM maintenance_bills
                GROUP BY flat_id, billing_month
            )
            """
        )
    )

    # Now the unique constraint can be created safely.
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.create_unique_constraint(
            "uq_maintenance_bill_flat_month",
            ["flat_id", "billing_month"],
        )


def downgrade():
    with op.batch_alter_table("maintenance_bills", schema=None) as batch_op:
        batch_op.drop_constraint(
            "uq_maintenance_bill_flat_month",
            type_="unique",
        )