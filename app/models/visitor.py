<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class Visitor(db.Model):
    __tablename__ = "visitors"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)

    visitor_name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    purpose = db.Column(
        db.String(100), default="Guest"
    )  # Guest, Delivery, Service, Vendor
    photo_url = db.Column(db.String(255), nullable=True)
    vehicle_number = db.Column(db.String(30), nullable=True)

    pass_code = db.Column(db.String(10), nullable=True, index=True)
    approval_status = db.Column(
        db.String(20), default="Approved"
    )  # Approved, Pending, Rejected, Expired
<<<<<<< HEAD
    entry_time = db.Column(db.DateTime, default=utcnow)
    exit_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
=======
    entry_time = db.Column(db.DateTime, default=datetime.utcnow)
    exit_time = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class PreApprovedPass(db.Model):
    __tablename__ = "pre_approved_passes"

    id = db.Column(db.Integer, primary_key=True)
    pass_code = db.Column(db.String(10), unique=True, nullable=False, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)

    visitor_name = db.Column(db.String(100), nullable=False)
    mobile = db.Column(db.String(20), nullable=False)
    expected_date = db.Column(db.Date, nullable=False)
    expected_time = db.Column(db.String(20), nullable=True)
    purpose = db.Column(db.String(100), default="Guest")
    is_used = db.Column(db.Boolean, default=False)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32



