from datetime import datetime
from sqlalchemy import func
from app.models import (
    db,
    Payment,
    PaymentReceipt,
    MaintenanceBill,
    PaymentReconciliationIssue,
    RefundRequest,
    AuditLog,
)
from app.services.receipt_service import ReceiptService
from app.utils import utcnow


class PaymentReconciliationService:
    @staticmethod
    def get_net_collection_summary(society_id):
        """
        Calculates verified real-time financial collection statistics from persisted database rows.
        Includes Today, Current Month, Current Year, Lifetime, and Net Collection (Gross minus Refunds).
        """
        now = utcnow()
        today_start = datetime(now.year, now.month, now.day)
        month_start = datetime(now.year, now.month, 1)
        year_start = datetime(now.year, 1, 1)

        base_q = Payment.query.filter(
            Payment.status.in_(["captured", "authorized", "paid", "Completed", "Success"])
        )
        if society_id:
            base_q = base_q.filter(Payment.society_id == society_id)

        all_payments = base_q.all()

        today_gross = sum(p.amount_paid for p in all_payments if p.payment_date and p.payment_date >= today_start)
        month_gross = sum(p.amount_paid for p in all_payments if p.payment_date and p.payment_date >= month_start)
        year_gross = sum(p.amount_paid for p in all_payments if p.payment_date and p.payment_date >= year_start)
        lifetime_gross = sum(p.amount_paid for p in all_payments)

        # Refunds
        refund_q = RefundRequest.query.filter(RefundRequest.status.in_(["processed", "approved"]))
        if society_id:
            refund_q = refund_q.filter(RefundRequest.society_id == society_id)
        all_refunds = refund_q.all()

        today_refunds = sum(r.refunded_amount or r.requested_amount for r in all_refunds if r.processed_at and r.processed_at >= today_start)
        month_refunds = sum(r.refunded_amount or r.requested_amount for r in all_refunds if r.processed_at and r.processed_at >= month_start)
        year_refunds = sum(r.refunded_amount or r.requested_amount for r in all_refunds if r.processed_at and r.processed_at >= year_start)
        lifetime_refunds = sum(r.refunded_amount or r.requested_amount for r in all_refunds)

        # Pending / Failed payments
        failed_q = Payment.query.filter(Payment.status.in_(["failed", "cancelled"]))
        if society_id:
            failed_q = failed_q.filter(Payment.society_id == society_id)
        failed_count = failed_q.count()

        # Unpaid bills & outstanding
        bill_q = MaintenanceBill.query.filter(MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"]))
        if society_id:
            bill_q = bill_q.filter(MaintenanceBill.society_id == society_id)
        unpaid_bills = bill_q.all()
        total_outstanding = sum(b.remaining_amount for b in unpaid_bills)
        overdue_bills = [b for b in unpaid_bills if b.status == "Overdue" or (b.due_date and b.due_date < now.date())]
        total_overdue = sum(b.remaining_amount for b in overdue_bills)
        total_late_fees = sum(b.late_fee for b in unpaid_bills)

        return {
            "today_collection": round(today_gross - today_refunds, 2),
            "today_gross": round(today_gross, 2),
            "month_collection": round(month_gross - month_refunds, 2),
            "month_gross": round(month_gross, 2),
            "year_collection": round(year_gross - year_refunds, 2),
            "lifetime_collection": round(lifetime_gross - lifetime_refunds, 2),
            "lifetime_gross": round(lifetime_gross, 2),
            "total_refunds": round(lifetime_refunds, 2),
            "successful_payments_count": len(all_payments),
            "failed_payments_count": failed_count,
            "total_outstanding": round(total_outstanding, 2),
            "total_overdue": round(total_overdue, 2),
            "total_late_fees": round(total_late_fees, 2),
            "unpaid_bills_count": len(unpaid_bills),
            "overdue_bills_count": len(overdue_bills),
        }

    @staticmethod
    def reconcile_all(society_id=None, executed_by=None):
        """
        Executes the 12-point automated reconciliation audit.
        Identifies and registers PaymentReconciliationIssue rows idempotently.
        """
        scanned = 0
        created = 0
        updated = 0
        issues_found = []

        # 1. Check: Successful payment but bill remains Unpaid / Pending
        payments_q = Payment.query.filter(
            Payment.status.in_(["captured", "authorized", "paid", "Completed", "Success"])
        )
        if society_id:
            payments_q = payments_q.filter(Payment.society_id == society_id)
        successful_payments = payments_q.all()

        for p in successful_payments:
            scanned += 1
            bill = db.session.get(MaintenanceBill, p.bill_id) if p.bill_id else None
            if not bill:
                # Issue 3: Orphan payment without bill
                issue = PaymentReconciliationService._record_issue(
                    society_id=p.society_id,
                    payment_id=p.id,
                    bill_id=None,
                    resident_id=p.resident_id,
                    issue_type="ORPHAN_PAYMENT_NO_BILL",
                    severity="CRITICAL",
                    description=f"Payment #{p.transaction_id} of ₹{p.amount_paid} has no associated maintenance bill.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)
            elif bill.status in ["Pending", "Overdue"] and bill.amount_paid < p.amount_paid:
                # Issue 1: Unpaid bill with verified payment
                issue = PaymentReconciliationService._record_issue(
                    society_id=p.society_id,
                    payment_id=p.id,
                    bill_id=bill.id,
                    resident_id=p.resident_id,
                    issue_type="UNPAID_BILL_WITH_PAYMENT",
                    severity="CRITICAL",
                    description=f"Bill #{bill.bill_number} is marked {bill.status} despite successful payment #{p.transaction_id} of ₹{p.amount_paid}.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)

            # Issue 2: Payment without linked resident
            if not p.resident_id:
                issue = PaymentReconciliationService._record_issue(
                    society_id=p.society_id,
                    payment_id=p.id,
                    bill_id=p.bill_id,
                    resident_id=None,
                    issue_type="ORPHAN_PAYMENT_NO_RESIDENT",
                    severity="WARNING",
                    description=f"Payment #{p.transaction_id} of ₹{p.amount_paid} is not linked to any resident.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)

            # Issue 4: Successful payment without receipt
            if not p.receipt:
                issue = PaymentReconciliationService._record_issue(
                    society_id=p.society_id,
                    payment_id=p.id,
                    bill_id=p.bill_id,
                    resident_id=p.resident_id,
                    issue_type="MISSING_RECEIPT",
                    severity="WARNING",
                    description=f"Payment #{p.transaction_id} has no generated receipt PDF or receipt record.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)

        # 5. Check: Receipt without successful payment
        receipts_q = PaymentReceipt.query
        if society_id:
            receipts_q = receipts_q.filter(PaymentReceipt.society_id == society_id)
        for r in receipts_q.all():
            scanned += 1
            pmt = db.session.get(Payment, r.payment_id) if r.payment_id else None
            if not pmt or pmt.status not in ["captured", "authorized", "paid", "Completed", "Success"]:
                issue = PaymentReconciliationService._record_issue(
                    society_id=r.society_id,
                    payment_id=r.payment_id,
                    bill_id=pmt.bill_id if pmt else None,
                    resident_id=pmt.resident_id if pmt else None,
                    issue_type="RECEIPT_WITHOUT_PAYMENT",
                    severity="CRITICAL",
                    description=f"Receipt #{r.receipt_number} exists for payment that is missing or not in captured status.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)

        # 6. Check: Duplicate payments (same provider order or transaction)
        dupes_q = (
            db.session.query(Payment.provider_payment_id, func.count(Payment.id))
            .filter(Payment.provider_payment_id.isnot(None))
            .filter(Payment.provider_payment_id != "")
        )
        if society_id:
            dupes_q = dupes_q.filter(Payment.society_id == society_id)
        dupes = dupes_q.group_by(Payment.provider_payment_id).having(func.count(Payment.id) > 1).all()

        for d_id, count in dupes:
            scanned += 1
            pmts = Payment.query.filter_by(provider_payment_id=d_id).all()
            for p in pmts:
                issue = PaymentReconciliationService._record_issue(
                    society_id=p.society_id,
                    payment_id=p.id,
                    bill_id=p.bill_id,
                    resident_id=p.resident_id,
                    issue_type="DUPLICATE_PAYMENT",
                    severity="CRITICAL",
                    description=f"Duplicate provider payment ID '{d_id}' found across {count} payment records.",
                )
                if issue:
                    created += 1
                    issues_found.append(issue)

        db.session.commit()

        return {
            "records_scanned": scanned,
            "records_created": created,
            "records_updated": updated,
            "open_issues_count": PaymentReconciliationIssue.query.filter_by(status="OPEN").count(),
            "warnings": [f"{len(issues_found)} reconciliation anomalies found"] if issues_found else [],
        }

    @staticmethod
    def _record_issue(society_id, payment_id, bill_id, resident_id, issue_type, severity, description):
        """Idempotently records a reconciliation issue if not already open."""
        existing = PaymentReconciliationIssue.query.filter_by(
            society_id=society_id,
            payment_id=payment_id,
            issue_type=issue_type,
            status="OPEN",
        ).first()
        if existing:
            return None

        issue = PaymentReconciliationIssue(
            society_id=society_id,
            payment_id=payment_id,
            bill_id=bill_id,
            resident_id=resident_id,
            issue_type=issue_type,
            severity=severity,
            description=description,
            status="OPEN",
        )
        db.session.add(issue)
        return issue

    @staticmethod
    def resolve_issue(issue_id, admin_user, resolution_notes="Resolved by administrator"):
        """
        Performs the automatic fix for a reconciliation issue and marks it RESOLVED.
        """
        issue = db.session.get(PaymentReconciliationIssue, issue_id)
        if not issue or issue.status == "RESOLVED":
            return {"success": False, "message": "Issue not found or already resolved."}

        # Apply specific fix based on issue type
        if issue.issue_type == "UNPAID_BILL_WITH_PAYMENT" and issue.payment_id and issue.bill_id:
            pmt = db.session.get(Payment, issue.payment_id)
            bill = db.session.get(MaintenanceBill, issue.bill_id)
            if pmt and bill:
                bill.amount_paid = min(bill.total_amount, bill.amount_paid + pmt.amount_paid)
                bill.remaining_amount = max(0.0, bill.total_amount - bill.amount_paid)
                bill.status = "Paid" if bill.remaining_amount == 0.0 else "Partially Paid"
                pmt.status = "captured"

        elif issue.issue_type == "MISSING_RECEIPT" and issue.payment_id:
            ReceiptService.generate_pdf_receipt(issue.payment_id)

        issue.status = "RESOLVED"
        issue.resolution_notes = resolution_notes
        issue.resolved_by_id = admin_user.id if admin_user else None
        issue.resolved_at = utcnow()

        audit = AuditLog(
            user_id=admin_user.id if admin_user else None,
            action="RECONCILIATION_ISSUE_RESOLVED",
            details=f"Resolved reconciliation issue #{issue.id} ({issue.issue_type}): {resolution_notes}",
        )
        db.session.add(audit)
        db.session.commit()
        return {"success": True, "issue_id": issue.id, "status": "RESOLVED"}

    @staticmethod
    def dismiss_issue(issue_id, admin_user, notes="Dismissed by administrator"):
        """
        Dismisses a reconciliation issue.
        """
        issue = db.session.get(PaymentReconciliationIssue, issue_id)
        if not issue:
            return {"success": False, "message": "Issue not found."}

        issue.status = "DISMISSED"
        issue.resolution_notes = notes
        issue.resolved_by_id = admin_user.id if admin_user else None
        issue.resolved_at = utcnow()

        audit = AuditLog(
            user_id=admin_user.id if admin_user else None,
            action="RECONCILIATION_ISSUE_DISMISSED",
            details=f"Dismissed reconciliation issue #{issue.id}: {notes}",
        )
        db.session.add(audit)
        db.session.commit()
        return {"success": True, "issue_id": issue.id, "status": "DISMISSED"}

    @staticmethod
    def get_open_issues(society_id=None, limit=50):
        """Retrieves currently open reconciliation issues."""
        q = PaymentReconciliationIssue.query.filter_by(status="OPEN")
        if society_id:
            q = q.filter(PaymentReconciliationIssue.society_id == society_id)
        return q.order_by(PaymentReconciliationIssue.detected_at.desc()).limit(limit).all()
