from app.models.tenant import db
from app.utils import utcnow


class PaymentReconciliationIssue(db.Model):
    __tablename__ = "payment_reconciliation_issues"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    payment_id = db.Column(
        db.Integer, db.ForeignKey("payments.id"), nullable=True, index=True
    )
    bill_id = db.Column(
        db.Integer, db.ForeignKey("maintenance_bills.id"), nullable=True, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=True, index=True
    )

    # Issue Types:
    # 1. UNPAID_BILL_WITH_PAYMENT
    # 2. ORPHAN_PAYMENT_NO_RESIDENT
    # 3. ORPHAN_PAYMENT_NO_BILL
    # 4. MISSING_RECEIPT
    # 5. RECEIPT_WITHOUT_PAYMENT
    # 6. DUPLICATE_PAYMENT
    # 7. AMOUNT_MISMATCH
    # 8. WRONG_MONTH_ALLOCATION
    # 9. COLLECTION_MISMATCH
    # 10. LEDGER_MISMATCH
    # 11. WEBHOOK_MISMATCH
    # 12. REFUND_MISMATCH
    issue_type = db.Column(db.String(60), nullable=False, index=True)
    severity = db.Column(
        db.String(20), default="WARNING", index=True
    )  # CRITICAL, WARNING, INFO
    description = db.Column(db.Text, nullable=False)
    detected_at = db.Column(db.DateTime, default=utcnow)

    # Status: OPEN, UNDER_REVIEW, RESOLVED, DISMISSED
    status = db.Column(db.String(30), default="OPEN", index=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)

    payment = db.relationship("Payment", foreign_keys=[payment_id], lazy=True)
    bill = db.relationship("MaintenanceBill", foreign_keys=[bill_id], lazy=True)
    resident = db.relationship("Resident", foreign_keys=[resident_id], lazy=True)
    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
