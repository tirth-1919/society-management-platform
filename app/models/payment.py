from datetime import datetime
from app.models.tenant import db


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
    notes = db.Column(db.Text, nullable=True)

    receipt = db.relationship(
        "PaymentReceipt", backref="payment", uselist=False, lazy=True
    )


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
    generated_at = db.Column(db.DateTime, default=datetime.utcnow)


class WebhookLog(db.Model):
    __tablename__ = "webhook_logs"

    id = db.Column(db.Integer, primary_key=True)
    provider = db.Column(db.String(50), nullable=False)
    event_type = db.Column(db.String(100), nullable=False)
    payload_hash = db.Column(
        db.String(64), unique=True, nullable=False, index=True
    )  # Hash for deduplication
    payload_json = db.Column(db.Text, nullable=False)
    processed_at = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default="Processed")



