<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class RegistrationRequest(db.Model):
    __tablename__ = "registration_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    building_id = db.Column(
        db.Integer, db.ForeignKey("buildings.id"), nullable=False, index=True
    )  # Wing
    block_id = db.Column(
        db.Integer, db.ForeignKey("blocks.id"), nullable=True, index=True
    )  # Block (optional for legacy)
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )

    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    occupancy_type = db.Column(
        db.String(30), nullable=False, default="OWNER"
    )  # OWNER, TENANT, FAMILY_MEMBER
    status = db.Column(
        db.String(30), nullable=False, default="PENDING_APPROVAL"
    )  # PENDING_APPROVAL, APPROVED, REJECTED

    rejection_reason = db.Column(db.Text, nullable=True)
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejected_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)

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

    society = db.relationship("Society", foreign_keys=[society_id], lazy=True)
    building = db.relationship("Building", foreign_keys=[building_id], lazy=True)
    block = db.relationship("Block", foreign_keys=[block_id], lazy=True)
    flat = db.relationship("Flat", foreign_keys=[flat_id], lazy=True)
    approved_by = db.relationship("User", foreign_keys=[approved_by_id], lazy=True)
    rejected_by = db.relationship("User", foreign_keys=[rejected_by_id], lazy=True)

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


