<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class Resident(db.Model):
    __tablename__ = "residents"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )

    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    email = db.Column(db.String(120), nullable=True)
    profile_photo = db.Column(db.String(255), nullable=True)
    resident_type = db.Column(
        db.String(20), nullable=False, default="Owner"
    )  # Owner, Tenant
    occupancy_status = db.Column(
        db.String(20), default="Active"
    )  # Active, Inactive, Moved Out
    is_primary = db.Column(db.Boolean, default=True)
<<<<<<< HEAD
    advance_balance = db.Column(db.Float, default=0.0)
    move_in_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
=======
    move_in_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    )

    emergency_contacts = db.relationship(
        "EmergencyContact", backref="resident", lazy=True, cascade="all, delete-orphan"
    )
    dependents = db.relationship(
        "Dependent", backref="resident", lazy=True, cascade="all, delete-orphan"
    )

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

class EmergencyContact(db.Model):
    __tablename__ = "emergency_contacts"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)
    name = db.Column(db.String(100), nullable=False)
    relation = db.Column(
        db.String(50), nullable=False
    )  # Spouse, Parent, Doctor, Security Supervisor, Police
    phone = db.Column(db.String(20), nullable=False)
    is_global = db.Column(
        db.Boolean, default=False
    )  # True if society emergency directory item


class Dependent(db.Model):
    __tablename__ = "dependents"

    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=False, index=True
    )
    name = db.Column(db.String(100), nullable=False)
    relation = db.Column(db.String(50), nullable=False)
    age = db.Column(db.Integer, nullable=True)



