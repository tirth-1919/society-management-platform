from app.models.tenant import db
from app.utils import utcnow


class DefaulterFollowUp(db.Model):
    __tablename__ = "defaulter_follow_ups"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)

    reason = db.Column(db.String(255), nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    priority = db.Column(
        db.String(20), default="Medium"
    )  # Low, Medium, High, Critical
    assigned_admin_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )
    notes = db.Column(db.Text, nullable=True)

    # Status: OPEN, IN_PROGRESS, RESOLVED, CLOSED
    status = db.Column(db.String(20), default="OPEN", index=True)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    resident = db.relationship("Resident", backref="follow_ups", lazy=True)
    flat = db.relationship("Flat", backref="follow_ups", lazy=True)
    assigned_admin = db.relationship("User", backref="assigned_follow_ups", lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class DefaulterStateTransition(db.Model):
    __tablename__ = 'defaulter_state_transitions'
    id = db.Column(db.Integer, primary_key=True)
    resident_id = db.Column(db.Integer, db.ForeignKey('residents.id'), nullable=False, index=True)
    bill_id = db.Column(db.Integer, db.ForeignKey('maintenance_bills.id'), nullable=True, index=True)
    old_state = db.Column(db.String(50), nullable=False)
    new_state = db.Column(db.String(50), nullable=False)
    timestamp = db.Column(db.DateTime, default=utcnow)
    reason = db.Column(db.String(255), nullable=True)
    actor_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    automation_id = db.Column(db.String(100), nullable=True)

    resident = db.relationship('Resident', backref='defaulter_transitions')
    bill = db.relationship('MaintenanceBill', backref='defaulter_transitions')
    actor = db.relationship('User', backref='defaulter_transitions')


class PaymentDispute(db.Model):
    """
    Resident-submitted dispute claiming a payment was made but bill remains outstanding.
    Never alters payment status without administrative verification.
    """

    __tablename__ = "payment_disputes"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=False, index=True
    )
    bill_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_bills.id"), nullable=True
    )
    payment_id = db.Column(
        db.Integer, db.ForeignKey("payments.id"), nullable=True
    )

    transaction_id = db.Column(db.String(100), nullable=True)
    claimed_amount = db.Column(db.Float, nullable=False)
    claimed_date = db.Column(db.Date, nullable=True)
    evidence_notes = db.Column(db.Text, nullable=True)

    # Workflow: OPEN, UNDER_REVIEW, VERIFIED, RESOLVED, REJECTED
    status = db.Column(db.String(20), default="OPEN", index=True)
    admin_notes = db.Column(db.Text, nullable=True)
    resolved_by_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True
    )

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    resident = db.relationship("Resident", backref="payment_disputes", lazy=True)
    bill = db.relationship("MaintenanceBill", backref="disputes", lazy=True)
    payment = db.relationship("Payment", backref="disputes", lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
