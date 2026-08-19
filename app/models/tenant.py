<<<<<<< HEAD
from flask_sqlalchemy import SQLAlchemy
from app.utils import utcnow
=======
﻿from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

db = SQLAlchemy()


def patch_sqlite_schema(app=None):
    """
<<<<<<< HEAD
    Safely patches existing SQLite database tables if missing new columns like flats.block_id,
    residents.advance_balance, complaints resolution fields, etc.
=======
    Safely patches existing SQLite database tables if missing new columns like flats.block_id.
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    """
    try:
        from sqlalchemy import inspect, text

<<<<<<< HEAD
        # Ensure any newly added tables are created
        db.create_all()

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        with db.engine.connect() as conn:
            inspector = inspect(db.engine)
            if "flats" in inspector.get_table_names():
                cols = [c["name"] for c in inspector.get_columns("flats")]
                if "block_id" not in cols:
                    conn.execute(
                        text(
                            "ALTER TABLE flats ADD COLUMN block_id INTEGER REFERENCES blocks(id)"
                        )
                    )
                    conn.commit()
            if "registration_requests" in inspector.get_table_names():
                cols_rr = [
                    c["name"] for c in inspector.get_columns("registration_requests")
                ]
                if "block_id" not in cols_rr:
                    conn.execute(
                        text(
                            "ALTER TABLE registration_requests ADD COLUMN block_id INTEGER REFERENCES blocks(id)"
                        )
                    )
                    conn.commit()
            if "users" in inspector.get_table_names():
                cols_users = [c["name"] for c in inspector.get_columns("users")]
                if "maintenance_start_month" not in cols_users:
                    conn.execute(
                        text(
                            "ALTER TABLE users ADD COLUMN maintenance_start_month VARCHAR(7)"
                        )
                    )
                    conn.commit()
<<<<<<< HEAD
            if "residents" in inspector.get_table_names():
                cols_residents = [c["name"] for c in inspector.get_columns("residents")]
                if "advance_balance" not in cols_residents:
                    conn.execute(
                        text(
                            "ALTER TABLE residents ADD COLUMN advance_balance FLOAT DEFAULT 0.0"
                        )
                    )
                    conn.commit()
            if "complaints" in inspector.get_table_names():
                cols_complaints = [c["name"] for c in inspector.get_columns("complaints")]
                if "resolution_notes" not in cols_complaints:
                    conn.execute(
                        text(
                            "ALTER TABLE complaints ADD COLUMN resolution_notes TEXT"
                        )
                    )
                    conn.commit()
                if "resolved_at" not in cols_complaints:
                    conn.execute(
                        text(
                            "ALTER TABLE complaints ADD COLUMN resolved_at DATETIME"
                        )
                    )
                    conn.commit()
                if "assigned_staff_id" not in cols_complaints:
                    conn.execute(
                        text(
                            "ALTER TABLE complaints ADD COLUMN assigned_staff_id INTEGER REFERENCES users(id)"
                        )
                    )
                    conn.commit()
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            if "notification_logs" in inspector.get_table_names():
                cols_notifications = [
                    c["name"] for c in inspector.get_columns("notification_logs")
                ]
                if "read_at" not in cols_notifications:
                    conn.execute(
                        text(
                            "ALTER TABLE notification_logs ADD COLUMN read_at DATETIME"
                        )
                    )
                    conn.commit()
<<<<<<< HEAD
            # Razorpay payment fields added in v2 payment system
            if "payments" in inspector.get_table_names():
                cols_payments = [c["name"] for c in inspector.get_columns("payments")]
                razorpay_columns = [
                    ("failure_reason", "TEXT"),
                    ("webhook_verified", "BOOLEAN DEFAULT 0"),
                    ("verified_at", "DATETIME"),
                    ("refund_status", "VARCHAR(30)"),
                    ("refund_id", "VARCHAR(100)"),
                    ("refund_amount", "FLOAT DEFAULT 0.0"),
                ]
                for col_name, col_def in razorpay_columns:
                    if col_name not in cols_payments:
                        conn.execute(
                            text(
                                f"ALTER TABLE payments ADD COLUMN {col_name} {col_def}"
                            )
                        )
                        conn.commit()
                # Ensure status column can hold new state values (no-op on SQLite)

            # ── Flat uniqueness index (Phase 3: property identity enforcement) ──
            # We add a unique index on (society_id, building_id, flat_number) rather
            # than a constraint so it works safely on both SQLite and MySQL for
            # existing databases that already contain data.
            if "flats" in inspector.get_table_names():
                existing_indexes = {idx["name"] for idx in inspector.get_indexes("flats")}
                if "uq_flat_society_building_number" not in existing_indexes:
                    try:
                        conn.execute(
                            text(
                                "CREATE UNIQUE INDEX uq_flat_society_building_number "
                                "ON flats (society_id, building_id, flat_number)"
                            )
                        )
                        conn.commit()
                        print("[DB PATCH] Created unique index on flats(society_id, building_id, flat_number)")
                    except Exception as idx_err:
                        print(f"[DB PATCH NOTE] Flat unique index skipped (may already exist or duplicate data): {idx_err}")
                        conn.rollback()

            # ── residents: add move_out_date and move_out_reason columns ──
            if "residents" in inspector.get_table_names():
                cols_residents2 = [c["name"] for c in inspector.get_columns("residents")]
                extra_resident_cols = [
                    ("move_out_date", "DATE"),
                    ("move_out_reason", "VARCHAR(255)"),
                    ("moved_out_approved_by", "INTEGER"),
                ]
                for col_name, col_def in extra_resident_cols:
                    if col_name not in cols_residents2:
                        conn.execute(
                            text(f"ALTER TABLE residents ADD COLUMN {col_name} {col_def}")
                        )
                        conn.commit()

            if "facility_bookings" in inspector.get_table_names():
                cols_fb = [c["name"] for c in inspector.get_columns("facility_bookings")]
                if "notes" not in cols_fb:
                    conn.execute(
                        text("ALTER TABLE facility_bookings ADD COLUMN notes TEXT")
                    )
                    conn.commit()

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    except Exception as e:
        print(f"[DB PATCH NOTE] Schema patch skipped or already applied: {e}")


class Society(db.Model):
    __tablename__ = "societies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    registration_number = db.Column(db.String(100), unique=True, nullable=False)
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    logo_url = db.Column(db.String(255), nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    )

    buildings = db.relationship(
        "Building", backref="society", lazy=True, cascade="all, delete-orphan"
    )
    flats = db.relationship(
        "Flat", backref="society", lazy=True, cascade="all, delete-orphan"
    )

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Building(db.Model):
    """
    Represents a Wing in the hierarchy: Society → Wing (Building) → Block → Flat.
=======

class Building(db.Model):
    """
    Represents a Wing in the hierarchy: Society â†’ Wing (Building) â†’ Block â†’ Flat.
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    Kept as 'buildings' table for backward compatibility with existing data and tests.
    In the UI this is presented as 'Wing'.
    """

    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)  # e.g. "Wing A", "Wing B"
    floors_count = db.Column(db.Integer, default=1)
    total_flats = db.Column(db.Integer, default=0)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    flats = db.relationship(
        "Flat", backref="building", lazy=True, cascade="all, delete-orphan"
    )
    blocks = db.relationship(
        "Block", backref="wing", lazy=True, cascade="all, delete-orphan"
    )

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

class Block(db.Model):
    """
    Represents a Block within a Wing.
<<<<<<< HEAD
    Hierarchy: Society → Wing (Building) → Block → Flat
=======
    Hierarchy: Society â†’ Wing (Building) â†’ Block â†’ Flat
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    """

    __tablename__ = "blocks"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)  # e.g. "Block 1", "Block A"
    floors_count = db.Column(db.Integer, default=1)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)

    flats = db.relationship("Flat", backref="block", lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Flat(db.Model):
    __tablename__ = "flats"
    __table_args__ = (
        # ── CRITICAL: one flat number per wing per society ────────────────────
        # This is the database-level enforcement of the BLOCK+FLAT uniqueness rule.
        # The ORM-level constraint mirrors the unique index created by patch_sqlite_schema.
        # On a fresh database creation, SQLAlchemy will create this constraint directly.
        db.UniqueConstraint(
            "society_id", "building_id", "flat_number",
            name="uq_flat_society_building_number",
        ),
    )
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    flats = db.relationship("Flat", backref="block", lazy=True)


class Flat(db.Model):
    __tablename__ = "flats"
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.id"), nullable=False, index=True
    )
    block_id = db.Column(
        db.Integer, db.ForeignKey("blocks.id"), nullable=True, index=True
<<<<<<< HEAD
    )  # Wing→Block→Flat
=======
    )  # Wingâ†’Blockâ†’Flat
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    flat_number = db.Column(db.String(50), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False, default=1)
    area_sqft = db.Column(db.Float, nullable=False, default=1000.0)
    flat_type = db.Column(db.String(50), default="2BHK")  # 1BHK, 2BHK, 3BHK, Penthouse
    occupancy_status = db.Column(
<<<<<<< HEAD
        db.String(30), default="Vacant"
    )  # Occupied, Vacant, Under Maintenance, Available
    created_at = db.Column(db.DateTime, default=utcnow)
=======
        db.String(30), default="Occupied"
    )  # Occupied, Vacant, Under Maintenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    residents = db.relationship("Resident", backref="flat", lazy=True)
    bills = db.relationship("MaintenanceBill", backref="flat", lazy=True)
    vehicles = db.relationship("Vehicle", backref="flat", lazy=True)

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def property_key(self):
        """
        Human-readable property identifier derived from wing/block name + flat number.
        This is the authoritative display format: e.g. 'WING A-202' or 'B-202'.
        Never store this in the DB — always compute it on-the-fly.
        """
        flat_num = str(self.flat_number).strip().upper()
        if self.block and self.block.name:
            prefix = str(self.block.name).strip().upper()
        elif self.building and self.building.name:
            prefix = str(self.building.name).strip().upper()
        else:
            return flat_num
        return f"{prefix}-{flat_num}" if prefix else flat_num

    @property
    def active_resident(self):
        """Returns the current active primary resident, or None."""
        return next(
            (r for r in self.residents if r.is_primary and r.occupancy_status == "Active"),
            None,
        )


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


