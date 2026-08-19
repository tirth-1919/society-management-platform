<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class SupportRequest(db.Model):
    __tablename__ = "support_requests"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=True, index=True
    )
    subject = db.Column(db.String(150), nullable=False)
    category = db.Column(
        db.String(30), nullable=False
    )  # Billing, Payment, Receipt, Account, Technical, Other
    message = db.Column(db.Text, nullable=False)
    status = db.Column(
        db.String(20), default="OPEN", index=True
    )  # OPEN, IN_PROGRESS, RESOLVED, CLOSED
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

    user = db.relationship("User", backref="support_requests", lazy=True)

<<<<<<< HEAD
    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


