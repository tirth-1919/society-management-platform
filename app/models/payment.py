<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class Payment(db.Model):
    __tablename__ = "payments"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(100), unique=True, nullable=False, index=True)
    idempotency_key = db.Column(db.String(100), unique=True, nullable=True, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    bill_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_bills.id"), nullable=False, index=True
    )
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)

    amount_paid = db.Column(db.Float, nullable=False)
    payment_method = db.Column(
        db.String(50), default="UPI"
<<<<<<< HEAD
    )  # UPI, QR, Card, Online, Cash, Bank Transfer, Razorpay
    provider_name = db.Column(
        db.String(50), default="Mock"
    )  # Razorpay, Cashfree, PayU, Mock, Manual
    provider_order_id = db.Column(db.String(100), nullable=True, index=True)
    provider_payment_id = db.Column(db.String(100), nullable=True, index=True)
    provider_signature = db.Column(db.Text, nullable=True)

    # Payment state: created | pending | authorized | captured | failed | cancelled | refunded | partially_refunded
    status = db.Column(db.String(30), default="pending", index=True)

    # Failure tracking
    failure_reason = db.Column(db.Text, nullable=True)

    # Verification tracking
    webhook_verified = db.Column(db.Boolean, default=False)
    verified_at = db.Column(db.DateTime, nullable=True)

    # Refund tracking
    refund_status = db.Column(db.String(30), nullable=True)  # requested, partial, full, failed
    refund_id = db.Column(db.String(100), nullable=True)
    refund_amount = db.Column(db.Float, default=0.0)

    payment_date = db.Column(db.DateTime, default=utcnow)
=======
    )  # UPI, QR, Card, Online, Cash, Bank Transfer
    provider_name = db.Column(
        db.String(50), default="Mock"
    )  # Razorpay, Cashfree, PayU, Mock, Manual
    provider_order_id = db.Column(db.String(100), nullable=True)
    provider_payment_id = db.Column(db.String(100), nullable=True)
    provider_signature = db.Column(db.Text, nullable=True)

    status = db.Column(
        db.String(30), default="Success", index=True
    )  # Success, Failed, Pending, Refunded
    payment_date = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    notes = db.Column(db.Text, nullable=True)

    receipt = db.relationship(
        "PaymentReceipt", backref="payment", uselist=False, lazy=True
    )
<<<<<<< HEAD
    refund_requests = db.relationship(
        "RefundRequest", backref="payment", lazy=True
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class PaymentReceipt(db.Model):
    __tablename__ = "payment_receipts"

    id = db.Column(db.Integer, primary_key=True)
    receipt_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    payment_id = db.Column(
        db.Integer, db.ForeignKey("payments.id"), nullable=False, unique=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    file_path = db.Column(db.String(255), nullable=True)
<<<<<<< HEAD
    generated_at = db.Column(db.DateTime, default=utcnow)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class RefundRequest(db.Model):
    """Resident-submitted refund request; admin approves and triggers Razorpay refund API."""

    __tablename__ = "refund_requests"

    id = db.Column(db.Integer, primary_key=True)
    payment_id = db.Column(
        db.Integer, db.ForeignKey("payments.id"), nullable=False, index=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)

    # Amount resident is requesting back
    requested_amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text, nullable=False)

    # Admin workflow
    status = db.Column(
        db.String(30), default="pending", index=True
    )  # pending | approved | rejected | processed | failed
    admin_notes = db.Column(db.Text, nullable=True)
    processed_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    # Razorpay refund tracking
    razorpay_refund_id = db.Column(db.String(100), nullable=True)
    refunded_amount = db.Column(db.Float, default=0.0)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )
    processed_at = db.Column(db.DateTime, nullable=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
=======
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class WebhookLog(db.Model):
    __tablename__ = "webhook_logs"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    payload_hash = db.Column(
        db.String(64), unique=True, nullable=False, index=True
    )  # Hash for deduplication
    payload_json = db.Column(db.Text, nullable=False)
<<<<<<< HEAD
    signature_verified = db.Column(db.Boolean, default=False)
    processed_at = db.Column(db.DateTime, default=utcnow)
    status = db.Column(db.String(20), default="Processed")
=======
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Processed")



>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
