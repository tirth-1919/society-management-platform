from app.models.tenant import db
from app.utils import utcnow


class Facility(db.Model):
    __tablename__ = "facilities"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    name = db.Column(
        db.String(100), nullable=False
    )  # Clubhouse, Swimming Pool, Tennis Court, Community Hall
    description = db.Column(db.Text, nullable=True)
    capacity = db.Column(db.Integer, default=50)
    hourly_rate = db.Column(db.Float, default=0.0)  # 0 for free amenities
    requires_approval = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)


class FacilityBooking(db.Model):
    __tablename__ = "facility_bookings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    facility_id = db.Column(
        db.Integer, db.ForeignKey("facilities.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)

    booking_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.String(10), nullable=False)  # e.g. "10:00"
    end_time = db.Column(db.String(10), nullable=False)  # e.g. "12:00"
    total_cost = db.Column(db.Float, default=0.0)
    purpose = db.Column(db.String(150), nullable=True)
    notes = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(20), default="Confirmed", index=True
    )  # Pending, Confirmed, Cancelled, Rejected
    created_at = db.Column(db.DateTime, default=utcnow)

    facility = db.relationship("Facility", backref="bookings", lazy=True)



