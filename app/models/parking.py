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


class Vehicle(db.Model):
    __tablename__ = "vehicles"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)

    vehicle_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    vehicle_type = db.Column(db.String(20), default="Car")  # Car, Bike, Scooter, Other
    brand_model = db.Column(db.String(100), nullable=True)  # Honda City, Activa
    color = db.Column(db.String(50), nullable=True)
    parking_slot_id = db.Column(
        db.Integer, db.ForeignKey("parking_slots.id"), nullable=True
    )
    rfid_tag = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)



