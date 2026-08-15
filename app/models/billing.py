from datetime import datetime
from app.models.tenant import db


class MaintenanceConfig(db.Model):
    __tablename__ = "maintenance_configs"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, unique=True
    )
    base_rate_per_sqft = db.Column(
        db.Float, default=1.5
    )  # e.g. 1.5 INR / sqft or fixed
    fixed_monthly_rate = db.Column(db.Float, default=1500.0)  # Base monthly charge
    due_day_of_month = db.Column(db.Integer, default=10)  # 10th of every month
    grace_period_days = db.Column(db.Integer, default=5)
    late_fee_per_month = db.Column(db.Float, default=500.0)  # ₹500 per overdue month
    billing_cycle = db.Column(db.String(20), default="Monthly")  # Monthly, Quarterly
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class MaintenanceBill(db.Model):
    __tablename__ = "maintenance_bills"
    __table_args__ = (
        db.UniqueConstraint(
            "resident_id", "billing_month", name="uq_maintenance_bill_resident_month"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    bill_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    flat_id = db.Column(
        db.Integer, db.ForeignKey("flats.id"), nullable=False, index=True
    )
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=True)

    billing_month = db.Column(
        db.String(7), nullable=False, index=True
    )  # Format YYYY-MM e.g. 2026-03
    base_amount = db.Column(db.Float, nullable=False)
    previous_balance = db.Column(db.Float, default=0.0)
    late_fee = db.Column(db.Float, default=0.0)
    additional_charges = db.Column(db.Float, default=0.0)
    discount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0.0)
    remaining_amount = db.Column(db.Float, nullable=False)

    due_date = db.Column(db.Date, nullable=False)
    status = db.Column(
        db.String(30), default="Pending", index=True
    )  # Pending, Partially Paid, Paid, Overdue, Cancelled

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    line_items = db.relationship(
        "BillLineItem", backref="bill", lazy=True, cascade="all, delete-orphan"
    )
    payments = db.relationship("Payment", backref="bill", lazy=True)


class BillLineItem(db.Model):
    __tablename__ = "bill_line_items"

    id = db.Column(db.Integer, primary_key=True)
    bill_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_bills.id"), nullable=False, index=True
    )
    description = db.Column(db.String(150), nullable=False)
    amount = db.Column(db.Float, nullable=False)




