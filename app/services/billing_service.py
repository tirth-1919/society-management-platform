from app.utils import utcnow
from datetime import datetime, date
from sqlalchemy.exc import IntegrityError
from app.config import Config
from app.models import (
    db,
    Flat,
    MaintenanceConfig,
    MaintenanceBill,
    BillLineItem,
    Resident,
)


class BillingService:
    @staticmethod
    def resident_dashboard_summary(resident_id, society_id, as_of=None):
        """Read-only dashboard values derived exclusively from persisted bills."""
        as_of = as_of or utcnow().date()
        unpaid = (
            MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident_id,
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
            )
            .order_by(
                MaintenanceBill.due_date.asc(), MaintenanceBill.billing_month.asc()
            )
            .all()
        )
        current_month = as_of.strftime("%Y-%m")
        current_bill = next(
            (bill for bill in unpaid if bill.billing_month == current_month), None
        )
        total_due = sum(max(bill.remaining_amount, 0.0) for bill in unpaid)
        return {
            "current_month_maintenance": current_bill.base_amount
            if current_bill
            else 0.0,
            "pending_months": len(unpaid),
            "maintenance_due": sum(bill.base_amount for bill in unpaid),
            "late_fee": sum(bill.late_fee for bill in unpaid),
            "total_due": total_due,
            "unpaid_bills": unpaid,
            "next_due_date": unpaid[0].due_date if unpaid else None,
            "next_payable_bill": unpaid[0] if unpaid else None,
            "overall_status": "Paid"
            if not unpaid
            else (
                "Partially Paid"
                if any(bill.amount_paid > 0 for bill in unpaid)
                else (
                    "Overdue"
                    if any(bill.status == "Overdue" for bill in unpaid)
                    else "Pending"
                )
            ),
            "overdue_bills": [
                bill for bill in unpaid if bill.due_date and bill.due_date < as_of
            ],
        }

    @staticmethod
    def _is_on_or_after_start_month(billing_month, start_month):
        return not start_month or billing_month >= start_month

    @staticmethod
    def ensure_bill_for_flat(society_id, flat_id, resident_id=None, billing_month=None):
        billing_month = billing_month or utcnow().strftime("%Y-%m")
        resident = (
            Resident.query.filter_by(id=resident_id, flat_id=flat_id).first()
            if resident_id
            else None
        )
        if resident and resident.user and resident.user.maintenance_start_month:
            if billing_month < resident.user.maintenance_start_month:
                raise ValueError(
                    "Cannot create a bill before the resident maintenance start month"
                )
        existing = MaintenanceBill.query.filter_by(
            society_id=society_id, resident_id=resident_id, billing_month=billing_month
        ).first()
        if existing:
            return existing
        config = MaintenanceConfig.query.filter_by(society_id=society_id).first()
        if not config:
            config = MaintenanceConfig(
                society_id=society_id,
                fixed_monthly_rate=Config.MONTHLY_MAINTENANCE,
                due_day_of_month=Config.MAINTENANCE_DUE_DAY,
                late_fee_per_month=Config.LATE_FEE_PER_MONTH,
            )
            db.session.add(config)
            db.session.flush()
        year, month = map(int, billing_month.split("-"))
        due_date = date(year, month, min(config.due_day_of_month, 28))
        flat = Flat.query.filter_by(id=flat_id, society_id=society_id).first()
        if not flat:
            raise ValueError("Flat does not belong to society")
        amount = config.fixed_monthly_rate
        bill = MaintenanceBill(
            bill_number=f"BILL-{society_id}-{flat_id}-{resident_id or 'flat'}-{billing_month}",
            society_id=society_id,
            flat_id=flat_id,
            resident_id=resident_id,
            billing_month=billing_month,
            base_amount=amount,
            total_amount=amount,
            remaining_amount=amount,
            due_date=due_date,
            status="Pending",
        )
        try:
            db.session.add(bill)
            db.session.flush()
            db.session.add(
                BillLineItem(
                    bill_id=bill.id,
                    description="Monthly Society Maintenance",
                    amount=amount,
                )
            )
            db.session.commit()
        except IntegrityError:
            # A concurrent worker won the unique resident/month insert.  The
            # existing row is the canonical bill; never create another one.
            db.session.rollback()
            existing = MaintenanceBill.query.filter_by(
                society_id=society_id,
                resident_id=resident_id,
                billing_month=billing_month,
            ).first()
            if existing:
                return existing
            raise
        if resident_id:
            from app.services.notification_service import NotificationService

            resident = db.session.get(Resident, resident_id)
            if resident and resident.user:
                month_label = datetime.strptime(billing_month, "%Y-%m").strftime(
                    "%B %Y"
                )
                NotificationService.send_billing_notification(
                    resident.user,
                    billing_month,
                    "BILL_GENERATED",
                    f"Your society maintenance of ₹{amount:,.0f} for {month_label} is due.",
                )
        return bill

    @staticmethod
    def apply_due_late_fees(society_id=None, as_of=None):
        """Assess one fee on each overdue bill, without carrying it forward."""
        as_of = as_of or utcnow().date()
        query = MaintenanceBill.query.filter(
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
            MaintenanceBill.due_date < as_of,
        )
        if society_id is not None:
            query = query.filter_by(society_id=society_id)

        changed = []
        for bill in query.all():
            if bill.late_fee > 0:
                if bill.status == "Pending":
                    bill.status = "Overdue"
                continue
            config = MaintenanceConfig.query.filter_by(
                society_id=bill.society_id
            ).first()
            fee = config.late_fee_per_month if config else Config.LATE_FEE_PER_MONTH
            bill.late_fee = fee
            bill.total_amount = (
                bill.base_amount + bill.additional_charges + fee - bill.discount
            )
            bill.remaining_amount = max(bill.total_amount - bill.amount_paid, 0.0)
            bill.status = (
                "Paid"
                if bill.remaining_amount <= 0
                else ("Partially Paid" if bill.amount_paid else "Overdue")
            )
            changed.append(bill)
        if changed:
            db.session.commit()
        return changed

    @staticmethod
    def calculate_flat_pending_summary(flat_id):
        """
        Calculates all pending maintenance bills, late fees, and total dues for a flat.
        Server-side calculation engine.
        """
        bills = (
            MaintenanceBill.query.filter_by(flat_id=flat_id)
            .filter(
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
            )
            .order_by(MaintenanceBill.billing_month.asc())
            .all()
        )

        total_base = sum(b.base_amount for b in bills)
        total_late_fees = sum(b.late_fee for b in bills)
        total_paid_so_far = sum(b.amount_paid for b in bills)
        total_remaining = sum(b.remaining_amount for b in bills)
        pending_months_count = len(bills)

        return {
            "pending_bills_count": pending_months_count,
            "total_base_amount": total_base,
            "total_late_fees": total_late_fees,
            "total_paid_so_far": total_paid_so_far,
            "total_remaining_due": total_remaining,
            "bills": bills,
        }

    @staticmethod
    def generate_monthly_bills(society_id, billing_month=None, as_of=None):
        """
        Automated monthly billing job.
        Generates maintenance bills for all active flats in a society for a given month (YYYY-MM).
        Ensures idempotency & prevents duplicate bill creation.
        """
        as_of = as_of or utcnow().date()
        current_month = as_of.strftime("%Y-%m")
        if not billing_month:
            billing_month = current_month
        if billing_month > current_month:
            raise ValueError("Future billing months cannot be generated")

        config = MaintenanceConfig.query.filter_by(society_id=society_id).first()
        if not config:
            # Create default config if missing
            config = MaintenanceConfig(
                society_id=society_id,
                fixed_monthly_rate=Config.MONTHLY_MAINTENANCE,
                due_day_of_month=Config.MAINTENANCE_DUE_DAY,
                late_fee_per_month=Config.LATE_FEE_PER_MONTH,
            )
            db.session.add(config)
            db.session.commit()

        flats = Flat.query.filter_by(society_id=society_id).all()
        generated_bills = []

        # Calculate due date: e.g. 10th of the billing month or next month
        year, month = map(int, billing_month.split("-"))
        date(year, month, min(config.due_day_of_month, 28))

        for flat in flats:
            # A billing cycle is the only place that creates a new monthly bill.
            # It never carries an earlier bill's balance or fee into a new month.
            # Bill only active residents and respect their persisted start month.
            resident = Resident.query.filter_by(
                flat_id=flat.id, is_primary=True
            ).first()
            if (
                not resident
                or not resident.user
                or resident.user.account_status != "ACTIVE"
            ):
                continue

            existing = MaintenanceBill.query.filter_by(
                society_id=society_id,
                resident_id=resident.id,
                billing_month=billing_month,
            ).first()
            if existing:
                continue  # Skip paid, pending, or overdue bills for the same resident/month.

            has_history = (
                MaintenanceBill.query.filter_by(resident_id=resident.id).first()
                is not None
            )
            start_month = resident.user.maintenance_start_month
            if not start_month and not has_history:
                start_month = Config.MAINTENANCE_DEFAULT_START_MONTH
            if not BillingService._is_on_or_after_start_month(
                billing_month, start_month
            ):
                continue

            generated_bills.append(
                BillingService.ensure_bill_for_flat(
                    society_id, flat.id, resident.id, billing_month
                )
            )

        BillingService.apply_due_late_fees(society_id=society_id, as_of=as_of)
        return generated_bills

    @staticmethod
    def apply_partial_payment(bill_id, payment_amount):
        """
        Updates bill balance transactionally after payment.
        Supports partial payment logic and state transition to Paid or Partially Paid.
        """
        bill = MaintenanceBill.query.filter_by(id=bill_id).with_for_update().first()
        if not bill:
            raise ValueError("Bill not found")

        if payment_amount <= 0:
            raise ValueError("Payment amount must be greater than 0")

        if payment_amount > bill.remaining_amount + 0.01:  # Margin for float precision
            raise ValueError(
                f"Payment amount ({payment_amount}) exceeds remaining balance ({bill.remaining_amount})"
            )

        bill.amount_paid += payment_amount
        bill.remaining_amount = max(0.0, bill.total_amount - bill.amount_paid)

        if bill.remaining_amount == 0.0:
            bill.status = "Paid"
        else:
            bill.status = "Partially Paid"

        return bill




