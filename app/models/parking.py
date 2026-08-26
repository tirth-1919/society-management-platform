import re
from app.models.tenant import db
from app.utils import utcnow


class ParkingSlot(db.Model):
    __tablename__ = "parking_slots"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    slot_number = db.Column(db.String(50), nullable=False)  # e.g. P1-A04
    location_block = db.Column(db.String(50), default="Basement 1")
    slot_type = db.Column(db.String(20), default="Car")  # Car, Bike, Visitor
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=True, unique=True
    )  # Unique allocation to flat
    status = db.Column(
        db.String(20), default="Allocated"
    )  # Available, Allocated, Reserved

    allocated_flat = db.relationship("Flat", backref="allocated_parking_slots", foreign_keys=[flat_id], lazy=True)


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    owner_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=True, index=True
    )
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )

    # Number plate representation
    vehicle_number = db.Column(db.String(50), nullable=False, index=True)
    normalized_number_plate = db.Column(db.String(50), nullable=True, index=True)

    # Vehicle details
    vehicle_type = db.Column(db.String(50), default="Car")  # Car, Bike, Scooter, Electric Car, Electric Bike, Cycle, Commercial Vehicle, Other
    make = db.Column(db.String(100), nullable=True)  # Hyundai, Honda, Tata
    model = db.Column(db.String(100), nullable=True)  # Creta, City, Activa
    brand_model = db.Column(db.String(200), nullable=True)  # Brand + Model string e.g. Hyundai Creta
    color = db.Column(db.String(50), nullable=True)

    # Parking slot info
    parking_slot_id = db.Column(
        db.Integer, db.ForeignKey("parking_slots.id"), nullable=True, index=True
    )
    parking_slot_number = db.Column(db.String(50), nullable=True)  # e.g. P-42

    # Contact & extra info
    rfid_tag = db.Column(db.String(50), nullable=True)
    secondary_mobile = db.Column(db.String(20), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    status = db.Column(db.String(20), default="ACTIVE", index=True)  # ACTIVE, INACTIVE, SOLD, TRANSFERRED
    notes = db.Column(db.Text, nullable=True)
    vehicle_photo = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    # Relationships
    owner = db.relationship("User", backref="owned_vehicles", foreign_keys=[owner_user_id], lazy=True)
    resident = db.relationship("Resident", backref="resident_vehicles", foreign_keys=[resident_id], lazy=True)
    parking_slot_rel = db.relationship("ParkingSlot", backref="parked_vehicles", foreign_keys=[parking_slot_id], lazy=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.vehicle_number and not self.normalized_number_plate:
            self.normalized_number_plate = self.normalize_plate(self.vehicle_number)
        if (self.make or self.model) and not self.brand_model:
            self.brand_model = f"{self.make or ''} {self.model or ''}".strip() or None

    @staticmethod
    def normalize_plate(plate):
        """Normalize number plate: removes whitespace, hyphens, special chars, uppercase."""
        if not plate:
            return ""
        return re.sub(r"[\s\-_.\/]+", "", str(plate)).upper()

    @property
    def number_plate(self):
        return self.vehicle_number

    @number_plate.setter
    def number_plate(self, value):
        self.vehicle_number = value
        self.normalized_number_plate = self.normalize_plate(value)

    @property
    def make_model(self):
        """Backward compatibility for search_service.py and existing code."""
        if self.brand_model:
            return self.brand_model
        return f"{self.make or ''} {self.model or ''}".strip() or "-"

    @property
    def parking_slot_display(self):
        if self.parking_slot_number:
            return self.parking_slot_number
        if self.parking_slot_rel:
            return self.parking_slot_rel.slot_number
        return "Unassigned"

    @property
    def is_active(self):
        return self.status == "ACTIVE"
