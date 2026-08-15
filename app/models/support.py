from datetime import datetime
from app.models.tenant import db


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", backref="support_requests", lazy=True)



