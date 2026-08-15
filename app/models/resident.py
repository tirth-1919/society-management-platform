from datetime import datetime
from app.models.tenant import db


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
    move_in_date = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    emergency_contacts = db.relationship(
        "EmergencyContact", backref="resident", lazy=True, cascade="all, delete-orphan"
    )
    dependents = db.relationship(
        "Dependent", backref="resident", lazy=True, cascade="all, delete-orphan"
    )


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



