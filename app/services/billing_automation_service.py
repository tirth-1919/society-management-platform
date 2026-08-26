from app.models import (
    db,
    Flat,
    Resident,
    MaintenanceBill,
    MaintenanceConfig,
    Payment,
    DefaulterFollowUp,
)
from app.services.billing_service import BillingService
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import datetime, timedelta
from app.config import Config


class BillingAutomationService:
    """
    Implements Phase 3 Billing Automation (Features 21–40):
    21. Automatic monthly bill generation
    22. Missing-bill detection
    23. Duplicate-bill detection
    24. Incorrect billing-month detection
    25. Missing-maintenance-amount detection
    26. Abnormal-bill-amount detection
    27. Pending-month calculation assistant
    28. Billing aging buckets
    29. Automatic bill notification
    30. Automatic bill reminder
    31. Automatic overdue reminder
    32. Automatic final overdue warning
    33. Chronic-defaulter escalation
    34. Automatic defaulter report
    35. Monthly collection report
    36. Unpaid-bill report
    37. Billing reconciliation report
    38. Payment-without-bill detection
    39. Bill-without-payment detection
    40. Partial-payment detection
    """

    @staticmethod
    def generate_monthly_bills_automation(society_id, billing_month=None):
        """Feature 21: Auto monthly bill generation with notification dispatch."""
        bills = BillingService.generate_monthly_bills(society_id=society_id, billing_month=billing_month)
        return {
            "created": len(bills),
            "billing_month": billing_month or utcnow().strftime("%Y-%m"),
            "bills": [b.bill_number for b in bills],
        }

    @staticmethod
    def detect_missing_bills(society_id, billing_month=None):
        """Feature 22: Identifies active occupied flats lacking a bill for billing_month."""
        billing_month = billing_month or utcnow().strftime("%Y-%m")
        flats = Flat.query.filter_by(society_id=society_id, occupancy_status="Occupied").all()
        missing = []

        for f in flats:
            resident = Resident.query.filter_by(flat_id=f.id, society_id=society_id, is_primary=True).first()
            if not resident or not resident.user or resident.user.account_status != "ACTIVE":
                continue
            start_m = resident.user.maintenance_start_month or Config.MAINTENANCE_DEFAULT_START_MONTH
            if billing_month < start_m:
                continue

            bill = MaintenanceBill.query.filter_by(
                society_id=society_id,
                flat_id=f.id,
                billing_month=billing_month,
            ).first()
            if not bill:
                missing.append({
                    "flat_id": f.id,
                    "flat_number": f.flat_number,
                    "resident_id": resident.id,
                    "resident_name": resident.full_name,
                    "billing_month": billing_month,
                })
        return missing

    @staticmethod
    def detect_duplicate_bills(society_id, billing_month=None):
        """Feature 23: Identifies flats with duplicate bills for the same month."""
        from sqlalchemy import func
        q = db.session.query(
            MaintenanceBill.flat_id,
            MaintenanceBill.billing_month,
            func.count(MaintenanceBill.id).label("bill_count")
        ).filter(MaintenanceBill.society_id == society_id)
        if billing_month:
            q = q.filter(MaintenanceBill.billing_month == billing_month)
        duplicates = q.group_by(MaintenanceBill.flat_id, MaintenanceBill.billing_month).having(func.count(MaintenanceBill.id) > 1).all()

        return [
            {"flat_id": d.flat_id, "billing_month": d.billing_month, "duplicate_count": d.bill_count}
            for d in duplicates
        ]

    @staticmethod
    def detect_incorrect_billing_months(society_id):
        """Feature 24: Identifies bills with invalid format or before resident start month."""
        bills = MaintenanceBill.query.filter_by(society_id=society_id).all()
        incorrect = []
        for b in bills:
            # Check format YYYY-MM
            try:
                datetime.strptime(b.billing_month, "%Y-%m")
            except (ValueError, TypeError):
                incorrect.append({"bill_id": b.id, "bill_number": b.bill_number, "reason": "Invalid YYYY-MM month format"})
                continue

            # Check start month violation
            if b.resident and b.resident.user and b.resident.user.maintenance_start_month:
                if b.billing_month < b.resident.user.maintenance_start_month:
                    incorrect.append({
                        "bill_id": b.id,
                        "bill_number": b.bill_number,
                        "billing_month": b.billing_month,
                        "start_month": b.resident.user.maintenance_start_month,
                        "reason": "Bill month is before resident start month",
                    })
        return incorrect

    @staticmethod
    def detect_missing_maintenance_amounts(society_id):
        """Feature 25: Identifies bills where base_amount or total_amount is 0.0."""
        bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            (MaintenanceBill.base_amount <= 0) | (MaintenanceBill.total_amount <= 0)
        ).all()
        return [
            {"bill_id": b.id, "bill_number": b.bill_number, "base_amount": b.base_amount, "total_amount": b.total_amount}
            for b in bills
        ]

    @staticmethod
    def detect_abnormal_bill_amounts(society_id):
        """Feature 26: Identifies bills deviating significantly from configured standard rate."""
        config = MaintenanceConfig.query.filter_by(society_id=society_id).first()
        base_rate = config.fixed_monthly_rate if config else Config.MONTHLY_MAINTENANCE

        bills = MaintenanceBill.query.filter_by(society_id=society_id).all()
        abnormal = []
        for b in bills:
            if b.base_amount > base_rate * 2.5 or b.base_amount < base_rate * 0.4:
                abnormal.append({
                    "bill_id": b.id,
                    "bill_number": b.bill_number,
                    "base_amount": b.base_amount,
                    "standard_rate": base_rate,
                    "deviation_ratio": round(b.base_amount / base_rate, 2),
                })
        return abnormal


    @staticmethod
    def calculate_pending_months_assistant(flat_id=None, resident_id=None, society_id=None, as_of=None):
        """Feature 27: Detailed pending-month calculation assistant for administrative review."""
        from app.services.registration_service import MaintenanceSummaryService
        if resident_id:
            res = db.session.get(Resident, resident_id)
            return MaintenanceSummaryService.calculate_dues(flat_id=res.flat_id if res else None, user_id=res.user_id if res else None, as_of=as_of)
        return MaintenanceSummaryService.calculate_dues(flat_id=flat_id, as_of=as_of)

    @staticmethod
    def get_billing_aging_buckets(society_id, as_of=None):
        """Feature 28: 5-tier billing aging buckets summary."""
        return BillingService.get_aging_buckets_summary(society_id=society_id, as_of=as_of)

    @staticmethod
    def dispatch_billing_reminders_and_escalations(society_id, as_of=None):
        """
        Features 29, 30, 31, 32, 33:
        Automated reminder & escalation pipeline:
        - Upcoming bill due reminders (Feature 30)
        - Overdue reminders (Feature 31)
        - Final warnings for > 30d overdue (Feature 32)
        - Chronic defaulter escalation (Feature 33)
        """
        as_of = as_of or utcnow().date()
        unpaid = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
            MaintenanceBill.remaining_amount > 0,
        ).all()

        reminders_sent = 0
        escalations_created = 0

        for b in unpaid:
            if not b.resident or not b.resident.user:
                continue

            days_overdue = (as_of - b.due_date).days if (b.due_date and as_of > b.due_date) else 0

            # Feature 32: Final overdue warning (> 30 days overdue)
            if days_overdue > 30:
                NotificationService.send_billing_notification(
                    b.resident.user,
                    b.billing_month,
                    "FINAL_OVERDUE_WARNING",
                    f"FINAL NOTICE: Maintenance bill for {b.billing_month} (₹{b.remaining_amount:,.0f}) is {days_overdue} days overdue. Immediate settlement required to prevent administrative escalation.",
                    cooldown_hours=72,
                )
                reminders_sent += 1
            elif days_overdue > 0:
                # Feature 31: Overdue reminder
                NotificationService.send_billing_notification(
                    b.resident.user,
                    b.billing_month,
                    "OVERDUE_REMINDER",
                    f"Reminder: Your maintenance bill for {b.billing_month} (₹{b.remaining_amount:,.0f}) is overdue. Please pay at your earliest convenience.",
                    cooldown_hours=48,
                )
                reminders_sent += 1

        # Feature 33: Chronic Defaulter Escalation
        defaulters = BillingService.get_defaulters_list(society_id=society_id)
        for d in defaulters:
            if d["risk_level"] in ["HIGH", "CRITICAL"]:
                has_open = DefaulterFollowUp.query.filter_by(
                    society_id=society_id, resident_id=d["resident_id"], status="OPEN"
                ).first()
                if not has_open:
                    followup = DefaulterFollowUp(
                        society_id=society_id,
                        resident_id=d["resident_id"],
                        flat_id=d["flat_id"],
                        reason=f"Automated Escalation: {d['risk_level']} Risk ({d['days_overdue']}d overdue, ₹{d['total_outstanding']:,.0f})",
                        due_date=utcnow().date() + timedelta(days=3),
                        priority="Critical" if d["risk_level"] == "CRITICAL" else "High",
                        status="OPEN",
                        notes=f"Chronic defaulter engine flagged resident with {d['pending_months_count']} unpaid month(s).",
                    )
                    db.session.add(followup)
                    escalations_created += 1

        db.session.commit()
        return {
            "reminders_sent": reminders_sent,
            "escalations_created": escalations_created,
            "defaulters_analyzed": len(defaulters),
        }

    @staticmethod
    def generate_defaulter_report(society_id):
        """Feature 34: Structured defaulters report."""
        return BillingService.get_defaulters_list(society_id=society_id)

    @staticmethod
    def generate_monthly_collection_report(society_id, billing_month=None):
        """Feature 35: Monthly collection efficiency and revenue report."""
        billing_month = billing_month or utcnow().strftime("%Y-%m")
        bills = MaintenanceBill.query.filter_by(society_id=society_id, billing_month=billing_month).all()

        total_billed = sum(b.total_amount for b in bills)
        total_collected = sum(b.amount_paid for b in bills)
        total_outstanding = sum(b.remaining_amount for b in bills)
        efficiency = round((total_collected / total_billed * 100), 1) if total_billed > 0 else 0.0

        return {
            "society_id": society_id,
            "billing_month": billing_month,
            "total_flats_billed": len(bills),
            "total_billed": total_billed,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
            "collection_efficiency": efficiency,
            "paid_bills_count": sum(1 for b in bills if b.status == "Paid"),
            "unpaid_bills_count": sum(1 for b in bills if b.status != "Paid"),
        }

    @staticmethod
    def generate_unpaid_bills_report(society_id):
        """Feature 36: Itemized unpaid bill report grouped by flat."""
        unpaid = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
            MaintenanceBill.remaining_amount > 0,
        ).order_by(MaintenanceBill.billing_month.asc()).all()

        return [
            {
                "bill_id": b.id,
                "bill_number": b.bill_number,
                "flat_number": b.flat.flat_number if b.flat else "-",
                "resident_name": b.resident.full_name if b.resident else "-",
                "billing_month": b.billing_month,
                "total_amount": b.total_amount,
                "amount_paid": b.amount_paid,
                "remaining_amount": b.remaining_amount,
                "due_date": b.due_date.strftime("%Y-%m-%d") if b.due_date else "-",
                "status": b.status,
            }
            for b in unpaid
        ]

    @staticmethod
    def generate_billing_reconciliation_report(society_id):
        """Feature 37: Audits total billing vs payments allocated vs outstanding balances."""
        bills = MaintenanceBill.query.filter_by(society_id=society_id).all()
        total_billed = sum(b.total_amount for b in bills)
        total_paid = sum(b.amount_paid for b in bills)
        total_remaining = sum(b.remaining_amount for b in bills)

        discrepancies = []
        for b in bills:
            expected_rem = round(b.total_amount - b.amount_paid, 2)
            if abs(b.remaining_amount - expected_rem) > 0.05:
                discrepancies.append({
                    "bill_id": b.id,
                    "bill_number": b.bill_number,
                    "total": b.total_amount,
                    "paid": b.amount_paid,
                    "stored_remaining": b.remaining_amount,
                    "expected_remaining": expected_rem,
                })

        return {
            "total_bills_count": len(bills),
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "total_remaining": round(total_remaining, 2),
            "discrepancies_count": len(discrepancies),
            "discrepancies": discrepancies,
        }

    @staticmethod
    def detect_payments_without_bills(society_id):
        """Feature 38: Identifies payments without a valid linked bill or where payment > bill total."""
        payments = Payment.query.filter_by(society_id=society_id).all()
        anomalies = []
        for p in payments:
            if not p.bill_id:
                anomalies.append({"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "reason": "No bill_id linked"})
            else:
                bill = db.session.get(MaintenanceBill, p.bill_id)
                if not bill:
                    anomalies.append({"payment_id": p.id, "transaction_id": p.transaction_id, "amount": p.amount_paid, "reason": "Linked bill not found in DB"})
        return anomalies

    @staticmethod
    def detect_bills_without_payments(society_id):
        """Feature 39: Overdue bills with zero payments recorded."""
        now = utcnow().date()
        bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.due_date < now,
            MaintenanceBill.amount_paid == 0,
        ).all()
        return [
            {"bill_id": b.id, "bill_number": b.bill_number, "billing_month": b.billing_month, "due_date": str(b.due_date), "amount": b.total_amount}
            for b in bills
        ]

    @staticmethod
    def detect_partial_payments(society_id):
        """Feature 40: Identifies bills with partial payment status."""
        bills = MaintenanceBill.query.filter_by(society_id=society_id, status="Partially Paid").all()
        return [
            {
                "bill_id": b.id,
                "bill_number": b.bill_number,
                "billing_month": b.billing_month,
                "total_amount": b.total_amount,
                "amount_paid": b.amount_paid,
                "remaining_amount": b.remaining_amount,
            }
            for b in bills
        ]
