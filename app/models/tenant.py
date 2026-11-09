
from flask_sqlalchemy import SQLAlchemy
from app.utils import utcnow

db = SQLAlchemy()


def patch_sqlite_schema(app=None):
    """
    Safely patches legacy SQLite databases.

    PostgreSQL schema changes must be handled through Alembic.
    Never run SQLite patches or db.create_all() on PostgreSQL.
    """
    try:
        from sqlalchemy import inspect, text

        # PostgreSQL and other databases must use Alembic.
        if db.engine.dialect.name != "sqlite":
            print(
                f"[DB PATCH] Skipped: database is "
                f"{db.engine.dialect.name}. Use Alembic migrations."
            )
            return

        # Create missing tables only for SQLite.
        db.create_all()

        with db.engine.connect() as conn:

            def get_columns(table_name):
                inspector = inspect(conn)

                if table_name not in inspector.get_table_names():
                    return set()

                return {
                    column["name"]
                    for column in inspector.get_columns(table_name)
                }

            def add_column(table_name, column_name, definition):
                if column_name not in get_columns(table_name):
                    conn.execute(
                        text(
                            f'ALTER TABLE "{table_name}" '
                            f'ADD COLUMN "{column_name}" {definition}'
                        )
                    )
                    conn.commit()

<<<<<<< Updated upstream
            if "automation_rules" in inspector.get_table_names():
                cols_ar = [c["name"] for c in inspector.get_columns("automation_rules")]
                if "event_name" not in cols_ar:
                    conn.execute(
                        text("ALTER TABLE automation_rules ADD COLUMN event_name VARCHAR(100)")
                    )
                    conn.commit()
                if "priority" not in cols_ar:
                    conn.execute(
                        text("ALTER TABLE automation_rules ADD COLUMN priority INTEGER DEFAULT 1")
                    )
                    conn.commit()

            if "automation_executions" in inspector.get_table_names():
                cols_ae = [c["name"] for c in inspector.get_columns("automation_executions")]
                if "retry_count" not in cols_ae:
                    conn.execute(
                        text("ALTER TABLE automation_executions ADD COLUMN retry_count INTEGER DEFAULT 0")
                    )
                    conn.commit()

            # Event photo hardening fields are additive so existing SQLite deployments
            # remain compatible before their Alembic migration is run.
            if "events" in inspector.get_table_names():
                cols_events = [c["name"] for c in inspector.get_columns("events")]
                if "photo_upload_deadline" not in cols_events:
                    conn.execute(text("ALTER TABLE events ADD COLUMN photo_upload_deadline DATETIME"))
                    conn.commit()
            # Vehicle directory fields are additive for existing SQLite databases
            if "vehicles" in inspector.get_table_names():
                cols_vehicles = [c["name"] for c in inspector.get_columns("vehicles")]
                vehicle_cols = [
                    ("owner_user_id", "INTEGER REFERENCES users(id)"),
                    ("normalized_number_plate", "VARCHAR(50)"),
                    ("make", "VARCHAR(100)"),
                    ("model", "VARCHAR(100)"),
                    ("parking_slot_number", "VARCHAR(50)"),
                    ("secondary_mobile", "VARCHAR(20)"),
                    ("email", "VARCHAR(120)"),
                    ("status", "VARCHAR(20) DEFAULT 'ACTIVE'"),
                    ("notes", "TEXT"),
                    ("vehicle_photo", "VARCHAR(255)"),
                    ("updated_at", "DATETIME"),
                ]
                for col_name, col_def in vehicle_cols:
                    if col_name not in cols_vehicles:
                        conn.execute(text(f"ALTER TABLE vehicles ADD COLUMN {col_name} {col_def}"))
                        conn.commit()

    except Exception as e:
        print(f"[DB PATCH NOTE] Schema patch skipped or already applied: {e}")
=======
                    print(
                        f"[DB PATCH] Added "
                        f"{table_name}.{column_name}"
                    )

            # FLATS
            add_column(
                "flats",
                "block_id",
                "INTEGER REFERENCES blocks(id)"
            )

            # REGISTRATION REQUESTS
            add_column(
                "registration_requests",
                "block_id",
                "INTEGER REFERENCES blocks(id)"
            )

            # USERS
            add_column(
                "users",
                "maintenance_start_month",
                "VARCHAR(7)"
            )

            # RESIDENTS
            add_column(
                "residents",
                "advance_balance",
                "FLOAT DEFAULT 0.0"
            )
            add_column(
                "residents",
                "move_out_date",
                "DATE"
            )
            add_column(
                "residents",
                "move_out_reason",
                "VARCHAR(255)"
            )
            add_column(
                "residents",
                "moved_out_approved_by",
                "INTEGER"
            )

            # COMPLAINTS
            add_column(
                "complaints",
                "resolution_notes",
                "TEXT"
            )
            add_column(
                "complaints",
                "resolved_at",
                "DATETIME"
            )
            add_column(
                "complaints",
                "assigned_staff_id",
                "INTEGER REFERENCES users(id)"
            )

            # NOTIFICATION LOGS
            add_column(
                "notification_logs",
                "read_at",
                "DATETIME"
            )

            # PAYMENTS
            payment_columns = [
                ("failure_reason", "TEXT"),
                ("webhook_verified", "BOOLEAN DEFAULT 0"),
                ("verified_at", "DATETIME"),
                ("refund_status", "VARCHAR(30)"),
                ("refund_id", "VARCHAR(100)"),
                ("refund_amount", "FLOAT DEFAULT 0.0"),
            ]

            for column_name, definition in payment_columns:
                add_column(
                    "payments",
                    column_name,
                    definition
                )

            # FLATS UNIQUE INDEX
            if "flats" in inspect(conn).get_table_names():
                inspector = inspect(conn)

                unique_objects = (
                    inspector.get_unique_constraints("flats")
                    + inspector.get_indexes("flats")
                )

                expected_columns = {
                    "society_id",
                    "building_id",
                    "flat_number",
                }

                already_exists = any(
                    item.get("unique", False)
                    and set(item.get("column_names") or [])
                    == expected_columns
                    for item in unique_objects
                )

                if not already_exists:
                    conn.execute(
                        text(
                            "CREATE UNIQUE INDEX "
                            "uq_flat_society_building_number "
                            "ON flats "
                            "(society_id, building_id, flat_number)"
                        )
                    )
                    conn.commit()

                    print(
                        "[DB PATCH] Flat unique index created."
                    )

            # FACILITY BOOKINGS
            add_column(
                "facility_bookings",
                "notes",
                "TEXT"
            )

        print("[DB PATCH] SQLite schema check completed.")

    except Exception as error:
        print(
            f"[DB PATCH ERROR] SQLite schema patch failed: {error}"
        )
        raise
>>>>>>> Stashed changes


class Society(db.Model):
    __tablename__ = "societies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    registration_number = db.Column(
        db.String(100), unique=True, nullable=False
    )
    address = db.Column(db.Text, nullable=False)
    city = db.Column(db.String(100), nullable=False)
    state = db.Column(db.String(100), nullable=False)
    pincode = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    logo_url = db.Column(db.String(255), nullable=True)
    emergency_contact = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    buildings = db.relationship(
        "Building",
        backref="society",
        lazy=True,
        cascade="all, delete-orphan"
    )

    flats = db.relationship(
        "Flat",
        backref="society",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Building(db.Model):
    """
    Represents a Wing in the hierarchy:
    Society → Wing (Building) → Block → Flat.

    Kept as 'buildings' table for backward compatibility.
    """

    __tablename__ = "buildings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(100), nullable=False)
    floors_count = db.Column(db.Integer, default=1)
    total_flats = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=utcnow)

    flats = db.relationship(
        "Flat",
        backref="building",
        lazy=True,
        cascade="all, delete-orphan"
    )

    blocks = db.relationship(
        "Block",
        backref="wing",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Block(db.Model):
    """
    Represents a Block within a Wing.
    Hierarchy: Society → Wing → Block → Flat.
    """

    __tablename__ = "blocks"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True
    )
    building_id = db.Column(
        db.Integer,
        db.ForeignKey("buildings.id"),
        nullable=False,
        index=True
    )
    name = db.Column(db.String(100), nullable=False)
    floors_count = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=utcnow)

    flats = db.relationship(
        "Flat",
        backref="block",
        lazy=True
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class Flat(db.Model):
    __tablename__ = "flats"

    __table_args__ = (
        db.UniqueConstraint(
            "society_id",
            "building_id",
            "flat_number",
            name="uq_flat_society_building_number",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)

    society_id = db.Column(
        db.Integer,
        db.ForeignKey("societies.id"),
        nullable=False,
        index=True
    )

    building_id = db.Column(
        db.Integer,
        db.ForeignKey("buildings.id"),
        nullable=False,
        index=True
    )

    block_id = db.Column(
        db.Integer,
        db.ForeignKey("blocks.id"),
        nullable=True,
        index=True
    )

    flat_number = db.Column(db.String(50), nullable=False)
    floor_number = db.Column(db.Integer, nullable=False, default=1)
    area_sqft = db.Column(db.Float, nullable=False, default=1000.0)
    flat_type = db.Column(db.String(50), default="2BHK")
    occupancy_status = db.Column(
        db.String(30),
        default="Vacant"
    )
    created_at = db.Column(db.DateTime, default=utcnow)

    residents = db.relationship(
        "Resident",
        backref="flat",
        lazy=True
    )

    bills = db.relationship(
        "MaintenanceBill",
        backref="flat",
        lazy=True
    )

    vehicles = db.relationship(
        "Vehicle",
        backref="flat",
        lazy=True
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    @property
    def property_key(self):
        """
        Human-readable property identifier.
        Example: WING A-202 or BLOCK A-202.
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
            (
                resident
                for resident in self.residents
                if resident.is_primary
                and resident.occupancy_status == "Active"
            ),
            None,
        )
<<<<<<< Updated upstream


=======
>>>>>>> Stashed changes
