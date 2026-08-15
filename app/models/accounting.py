from datetime import datetime
from app.models.tenant import db


class ExpenseVoucher(db.Model):
    __tablename__ = "expense_vouchers"

    id = db.Column(db.Integer, primary_key=True)
    voucher_number = db.Column(db.String(50), unique=True, nullable=False, index=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    category = db.Column(
        db.String(50), nullable=False
    )  # Electricity, Water, Security, Cleaning, Lift, Repairs, Salary, Vendor
    amount = db.Column(db.Float, nullable=False)
    payee_name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=True)
    expense_date = db.Column(db.Date, nullable=False)

    status = db.Column(
        db.String(20), default="Approved"
    )  # Draft, Submitted, Approved, Paid, Rejected
    approved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AccountLedger(db.Model):
    __tablename__ = "account_ledgers"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    entry_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    account_head = db.Column(
        db.String(100), nullable=False
    )  # Maintenance Collection, Water Charges, Salary Expense, Repairs
    entry_type = db.Column(
        db.String(10), nullable=False
    )  # CREDIT (Income), DEBIT (Expense)
    amount = db.Column(db.Float, nullable=False)
    reference_type = db.Column(
        db.String(50), nullable=True
    )  # BILL_PAYMENT, EXPENSE_VOUCHER, VENDOR_PAYMENT
    reference_id = db.Column(db.Integer, nullable=True)
    narration = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class FinancialYear(db.Model):
    __tablename__ = "financial_years"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    year_label = db.Column(db.String(20), nullable=False)  # FY 2025-2026
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    is_closed = db.Column(db.Boolean, default=False)



