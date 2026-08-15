from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def patch_sqlite_schema(app=None):
    """
    Safely patches existing SQLite database tables if missing new columns like flats.block_id.
    """
    try:
        from sqlalchemy import inspect, text

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    buildings = db.relationship(
        "Building", backref="society", lazy=True, cascade="all, delete-orphan"
    )
    flats = db.relationship(
        "Flat", backref="society", lazy=True, cascade="all, delete-orphan"
    )


class Building(db.Model):
    """
    Represents a Wing in the hierarchy: Society â†’ Wing (Building) â†’ Block â†’ Flat.
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    flats = db.relationship(
        "Flat", backref="building", lazy=True, cascade="all, delete-orphan"
    )
    blocks = db.relationship(
        "Block", backref="wing", lazy=True, cascade="all, delete-orphan"
    )


class Block(db.Model):
    """
    Represents a Block within a Wing.
    Hierarchy: Society â†’ Wing (Building) â†’ Block â†’ Flat
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    flats = db.relationship("Flat", backref="block", lazy=True)


class Flat(db.Model):
    __tablename__ = "flats"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.id"), nullable=False, index=True
    )
    block_id = db.Column(
        db.Integer, db.ForeignKey("blocks.id"), nullable=True, index=True
    )  # Wingâ†’Blockâ†’Flat
    flat_number = db.Column(db.String(50), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False, default=1)
    area_sqft = db.Column(db.Float, nullable=False, default=1000.0)
    flat_type = db.Column(db.String(50), default="2BHK")  # 1BHK, 2BHK, 3BHK, Penthouse
    occupancy_status = db.Column(
        db.String(30), default="Occupied"
    )  # Occupied, Vacant, Under Maintenance
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    residents = db.relationship("Resident", backref="flat", lazy=True)
    bills = db.relationship("MaintenanceBill", backref="flat", lazy=True)
    vehicles = db.relationship("Vehicle", backref="flat", lazy=True)



