from app.models.tenant import db
from app.utils import utcnow


class PropertyOccupancyHistory(db.Model):
    __tablename__ = "property_occupancy_histories"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )

    resident_type = db.Column(db.String(30), default="Owner")  # Owner, Tenant, Family
    occupancy_status = db.Column(
        db.String(30), default="Active", index=True
    )  # Active, Moved Out, Transferred

    move_in_date = db.Column(db.Date, nullable=False)
    move_out_date = db.Column(db.Date, nullable=True)
    move_out_reason = db.Column(db.String(255), nullable=True)

    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    flat = db.relationship("Flat", foreign_keys=[flat_id], lazy=True)
    resident = db.relationship("Resident", foreign_keys=[resident_id], lazy=True)
    user = db.relationship("User", foreign_keys=[user_id], lazy=True)
    approved_by = db.relationship("User", foreign_keys=[approved_by_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
