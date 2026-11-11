"""Add vehicle details and automation fields.

Revision ID: 20260818_vehicles_and_automation_schema
Revises: 20260818_vehicle_updated_at
Create Date: 2026-11-11
"""

from alembic import op
import sqlalchemy as sa


revision = "20260818_vehicles_and_automation_schema"
down_revision = "20260818_vehicle_updated_at"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    # 1. VEHICLES TABLE
    if "vehicles" in tables:
        vehicle_cols = {c["name"] for c in inspector.get_columns("vehicles")}

        if "owner_user_id" not in vehicle_cols:
            op.add_column(
                "vehicles",
                sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            )
            try:
                op.create_index("ix_vehicles_owner_user_id", "vehicles", ["owner_user_id"])
            except Exception:
                pass

        if "normalized_number_plate" not in vehicle_cols:
            op.add_column(
                "vehicles",
                sa.Column("normalized_number_plate", sa.String(50), nullable=True),
            )
            try:
                op.create_index("ix_vehicles_normalized_number_plate", "vehicles", ["normalized_number_plate"])
            except Exception:
                pass

        if "make" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("make", sa.String(100), nullable=True))

        if "model" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("model", sa.String(100), nullable=True))

        if "parking_slot_number" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("parking_slot_number", sa.String(50), nullable=True))

        if "secondary_mobile" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("secondary_mobile", sa.String(20), nullable=True))

        if "email" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("email", sa.String(120), nullable=True))

        if "status" not in vehicle_cols:
            op.add_column(
                "vehicles",
                sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=True),
            )
            try:
                op.create_index("ix_vehicles_status", "vehicles", ["status"])
            except Exception:
                pass

        if "notes" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("notes", sa.Text(), nullable=True))

        if "vehicle_photo" not in vehicle_cols:
            op.add_column("vehicles", sa.Column("vehicle_photo", sa.String(255), nullable=True))

        if "updated_at" not in vehicle_cols:
            op.add_column(
                "vehicles",
                sa.Column("updated_at", sa.DateTime(), server_default=sa.func.now(), nullable=True),
            )

    # 2. AUTOMATION RULES TABLE
    if "automation_rules" in tables:
        rule_cols = {c["name"] for c in inspector.get_columns("automation_rules")}
        if "event_name" not in rule_cols:
            op.add_column("automation_rules", sa.Column("event_name", sa.String(100), nullable=True))
        if "priority" not in rule_cols:
            op.add_column("automation_rules", sa.Column("priority", sa.Integer(), server_default="1", nullable=True))

    # 3. AUTOMATION EXECUTIONS TABLE
    if "automation_executions" in tables:
        exec_cols = {c["name"] for c in inspector.get_columns("automation_executions")}
        if "retry_count" not in exec_cols:
            op.add_column("automation_executions", sa.Column("retry_count", sa.Integer(), server_default="0", nullable=True))


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = inspector.get_table_names()

    if "vehicles" in tables:
        vehicle_cols = {c["name"] for c in inspector.get_columns("vehicles")}
        for col in [
            "vehicle_photo", "notes", "status", "email", "secondary_mobile",
            "parking_slot_number", "model", "make", "normalized_number_plate", "owner_user_id"
        ]:
            if col in vehicle_cols:
                op.drop_column("vehicles", col)

    if "automation_rules" in tables:
        rule_cols = {c["name"] for c in inspector.get_columns("automation_rules")}
        if "priority" in rule_cols:
            op.drop_column("automation_rules", "priority")
        if "event_name" in rule_cols:
            op.drop_column("automation_rules", "event_name")

    if "automation_executions" in tables:
        exec_cols = {c["name"] for c in inspector.get_columns("automation_executions")}
        if "retry_count" in exec_cols:
            op.drop_column("automation_executions", "retry_count")

