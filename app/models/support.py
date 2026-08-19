from app.models.tenant import db
from app.utils import utcnow


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
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    user = db.relationship("User", backref="support_requests", lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)



