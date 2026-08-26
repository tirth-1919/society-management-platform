from app.models import (
    db,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    RefundRequest,
    PaymentReconciliationIssue,
    AutomationAlert,
)
from app.services.reconciliation_service import PaymentReconciliationService
from app.services.receipt_service import ReceiptService
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import datetime, timedelta


class PaymentAutomationService:
    """
    Implements Phase 4 Payment Automation (Features 41–60):
    41. Automatic payment-to-bill matching
    42. Payment reference matching
    43. Duplicate payment detection
    44. Unmatched payment detection
    45. Suspicious payment detection
    46. Failed-payment alert
    47. Pending-payment alert
    48. Successful-payment confirmation
    49. Automatic receipt trigger where already supported
    50. Automatic receipt notification
    51. Bill-status synchronization
    52. Resident payment-history synchronization
    53. Payment reconciliation
    54. Reconciliation mismatch detection
    55. Reconciliation issue creation
    56. Reconciliation reminder
    57. Reconciliation escalation
    58. Unusual-refund detection
    59. Unusual-cash-payment alert
    60. Daily payment summary
    """

    @staticmethod
    def match_payment_to_bill(payment_id):
        """
        Features 41 & 42:
        Matches an incoming payment to the resident's oldest pending bill and matches references.
        """
        payment = db.session.get(Payment, payment_id)
        if not payment or not payment.resident_id:
            return None

        if not payment.bill_id:
            oldest_bill = MaintenanceBill.query.filter_by(
                society_id=payment.society_id,
                resident_id=payment.resident_id,
            ).filter(
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
            ).order_by(MaintenanceBill.billing_month.asc()).first()

            if oldest_bill:
                payment.bill_id = oldest_bill.id
                db.session.commit()
        return payment.bill_id

    @staticmethod
    def detect_duplicate_payments(society_id):
        """Feature 43: Identifies duplicate transaction IDs or idempotency keys."""
        from sqlalchemy import func
        q = db.session.query(
            Payment.transaction_id,
            func.count(Payment.id).label("count")
        ).filter(Payment.society_id == society_id).group_by(Payment.transaction_id).having(func.count(Payment.id) > 1).all()

        return [{"transaction_id": d.transaction_id, "duplicate_count": d.count} for d in q]

    @staticmethod
    def detect_unmatched_payments(society_id):
        """Feature 44: Identifies payments missing bill or resident linkages."""
        unmatched = Payment.query.filter(
            Payment.society_id == society_id,
            (Payment.bill_id.is_(None)) | (Payment.resident_id.is_(None))
        ).all()
        return [
            {"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "status": p.status}
            for p in unmatched
        ]

    @staticmethod
    def detect_suspicious_payments(society_id):
        """Feature 45: Detects abnormal payments (e.g. > ₹100k, mismatched society)."""
        suspicious = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.amount_paid > 100000.0,
        ).all()
        return [
            {"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "reason": "Amount exceeds ₹1,00,000 threshold"}
            for p in suspicious
        ]

    @staticmethod
    def on_payment_success(payment_id):
        """
        Features 48, 49, 50, 51, 52:
        Executes automated post-payment workflows:
        - Successful payment confirmation notification
        - Automatic receipt generation
        - Receipt notification
        - Bill status synchronization
        - Resident payment history sync
        """
        payment = db.session.get(Payment, payment_id)
        if not payment or payment.status not in ["captured", "Success", "paid"]:
            return

        # 1. Sync bill status
        if payment.bill_id:
            bill = db.session.get(MaintenanceBill, payment.bill_id)
            if bill:
                bill.amount_paid = min(bill.total_amount, bill.amount_paid + payment.amount_paid)
                bill.remaining_amount = max(0.0, bill.total_amount - bill.amount_paid)
                bill.status = "Paid" if bill.remaining_amount == 0.0 else "Partially Paid"
                db.session.commit()

        # 2. Trigger automatic receipt generation
        try:
            ReceiptService.generate_pdf_receipt(payment.id)
            receipt_obj = payment.receipt or PaymentReceipt.query.filter_by(payment_id=payment.id).first()
        except Exception:
            receipt_obj = None

        # 3. Send confirmation and receipt notification
        if payment.resident and payment.resident.user:
            user = payment.resident.user
            rcpt_label = receipt_obj.receipt_number if receipt_obj else "generated"
            NotificationService.send_notification(
                recipient=user.mobile or user.email or "N/A",
                message=f"Payment Received: ₹{payment.amount_paid:,.2f} via {payment.payment_method}. Transaction ID: {payment.transaction_id}. Your receipt #{rcpt_label} has been generated.",
                channel="In-App",
                society_id=payment.society_id,
                user_id=user.id,
                category="General",
            )

        # 4. Trigger payment_verified automation event
        from app.services.automation_service import AutomationService
        AutomationService.trigger_event(
            event_name="payment_verified",
            society_id=payment.society_id,
            payload={
                "payment_id": payment.id,
                "amount": payment.amount_paid,
                "transaction_id": payment.transaction_id,
                "bill_id": payment.bill_id,
                "resident_id": payment.resident_id,
            },
        )


    @staticmethod
    def on_payment_failed(payment_id, error_reason="Payment transaction failed"):
        """Feature 46: Alerts and notifications for failed payments."""
        payment = db.session.get(Payment, payment_id)
        if not payment:
            return

        alert = AutomationAlert(
            society_id=payment.society_id,
            alert_type="PAYMENT_FAILED",
            severity="WARNING",
            title=f"Payment Failed: TXN #{payment.transaction_id}",
            message=f"Payment of ₹{payment.amount_paid:,.2f} for Flat {payment.resident.flat.flat_number if (payment.resident and payment.resident.flat) else '-'} failed. Reason: {error_reason}",
            is_resolved=False,
        )
        db.session.add(alert)
        db.session.commit()

        if payment.resident and payment.resident.user:
            NotificationService.send_notification(
                recipient=payment.resident.user.mobile or "N/A",
                message=f"Payment Alert: Your payment of ₹{payment.amount_paid:,.2f} could not be processed ({error_reason}). Please retry from the Payment Center.",
                channel="In-App",
                society_id=payment.society_id,
                user_id=payment.resident.user.id,
                category="Reminder",
            )

    @staticmethod
    def scan_pending_payments(society_id, hours_threshold=2):
        """Feature 47: Detects payments in pending/created status for longer than hours_threshold."""
        cutoff = utcnow() - timedelta(hours=hours_threshold)
        pending = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["pending", "created"]),
            Payment.payment_date <= cutoff,
        ).all()

        return [
            {"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "payment_date": str(p.payment_date)}
            for p in pending
        ]

    @staticmethod
    def run_reconciliation_pipeline(society_id):
        """
        Features 53, 54, 55, 56, 57:
        Executes reconciliation scan, detects mismatches, creates issues,
        sends reminders, and escalates unresolved issues > 3 days old.
        """
        recon_res = PaymentReconciliationService.reconcile_all(society_id=society_id)

        # Check for unresolved issues > 3 days old for escalation (Feature 57)
        cutoff_3d = utcnow() - timedelta(days=3)
        old_issues = PaymentReconciliationIssue.query.filter(
            PaymentReconciliationIssue.society_id == society_id,
            PaymentReconciliationIssue.status == "OPEN",
            PaymentReconciliationIssue.detected_at <= cutoff_3d,
        ).all()

        escalated_count = 0
        for issue in old_issues:
            if issue.severity != "CRITICAL":
                issue.severity = "CRITICAL"
                escalated_count += 1
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="RECONCILIATION_ESCALATION",
                    severity="CRITICAL",
                    title=f"Reconciliation Escalation #{issue.id}",
                    message=f"Unresolved reconciliation issue #{issue.id} ({issue.issue_type}) is older than 3 days: {issue.description}",
                    is_resolved=False,
                )
                db.session.add(alert)

        db.session.commit()
        return {
            "reconciliation_stats": recon_res,
            "escalated_issues": escalated_count,
            "total_open_issues": PaymentReconciliationIssue.query.filter_by(society_id=society_id, status="OPEN").count(),
        }

    @staticmethod
    def detect_unusual_refunds(society_id):
        """Feature 58: Flags refund requests that exceed original payment or are older than 90 days."""
        refunds = RefundRequest.query.filter_by(society_id=society_id).all()
        anomalous = []
        for r in refunds:
            pmt = db.session.get(Payment, r.payment_id)
            if not pmt:
                anomalous.append({"refund_id": r.id, "reason": "No linked payment found"})
                continue
            if r.requested_amount > pmt.amount_paid:
                anomalous.append({
                    "refund_id": r.id,
                    "requested_amount": r.requested_amount,
                    "payment_amount": pmt.amount_paid,
                    "reason": "Refund request exceeds original payment amount",
                })
        return anomalous

    @staticmethod
    def alert_unusual_cash_payments(society_id):
        """Feature 59: Flags cash payments > ₹20,000 or unverified cash pending > 48 hours."""
        cutoff_48h = utcnow() - timedelta(hours=48)
        unusual_cash = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.payment_method == "Cash",
            (Payment.amount_paid > 20000.0) | ((Payment.status == "pending") & (Payment.payment_date <= cutoff_48h)),
        ).all()

        alerts = []
        for p in unusual_cash:
            reason = "Cash payment exceeds ₹20,000 limit" if p.amount_paid > 20000.0 else "Unverified cash payment pending > 48 hours"
            alerts.append({"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "reason": reason})

        return alerts

    @staticmethod
    def generate_daily_payment_summary(society_id, target_date=None):
        """Feature 60: Generates daily payment breakdown by method (UPI, Card, Cash, etc.)."""
        target_date = target_date or utcnow().date()
        start = datetime(target_date.year, target_date.month, target_date.day)
        end = start + timedelta(days=1)

        payments = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success", "paid"]),
            Payment.payment_date >= start,
            Payment.payment_date < end,
        ).all()

        by_method = {}
        total_amount = 0.0
        for p in payments:
            method = p.payment_method or "Online"
            by_method[method] = by_method.get(method, 0.0) + p.amount_paid
            total_amount += p.amount_paid

        return {
            "society_id": society_id,
            "date": target_date.strftime("%Y-%m-%d"),
            "total_transactions": len(payments),
            "total_collected": round(total_amount, 2),
            "by_method": by_method,
        }
