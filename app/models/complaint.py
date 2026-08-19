<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class ComplaintCategory(db.Model):
    __tablename__ = "complaint_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(
        db.String(50), unique=True, nullable=False
    )  # Plumbing, Electrical, Water, Lift, Cleaning, Security, Parking, Common Area, Other


class Complaint(db.Model):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(
        db.String(20), default="Medium"
    )  # Low, Medium, High, Emergency
    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    status = db.Column(
        db.String(30), default="Submitted", index=True
    )  # Submitted, Assigned, In Progress, Resolved, Closed
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
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

    comments = db.relationship(
        "ComplaintComment", backref="complaint", lazy=True, cascade="all, delete-orphan"
    )


class ComplaintComment(db.Model):
    __tablename__ = "complaint_comments"

    id = db.Column(db.Integer, primary_key=True)
    complaint_id = db.Column(
        db.Integer, db.ForeignKey("complaints.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    comment = db.Column(db.Text, nullable=False)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    user = db.relationship("User", backref="complaint_comments", lazy=True)



