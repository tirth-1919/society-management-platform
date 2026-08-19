<<<<<<< HEAD
from app.utils import utcnow
=======
﻿from app.utils import utcnow
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
        if not society_id:
            raise ValueError("Society ID is required to generate bill")
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
        # Check if resident has advance credit to automatically apply
        if resident and hasattr(resident, "advance_balance") and resident.advance_balance and resident.advance_balance > 0:
            advance_to_use = min(bill.remaining_amount, resident.advance_balance)
            bill.amount_paid = advance_to_use
            bill.remaining_amount = max(0.0, bill.total_amount - bill.amount_paid)
            bill.status = "Paid" if bill.remaining_amount == 0.0 else "Partially Paid"
            resident.advance_balance = round(resident.advance_balance - advance_to_use, 2)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
        if not society_id:
            raise ValueError("Society ID is required to generate monthly bills")

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
    def generate_missing_bills_summary(society_id=None, month=None):
        """
        Wrapper used by automation engine to generate missing bills across one or all societies.
        """
        from app.models import Society
        societies = [db.session.get(Society, society_id)] if society_id else Society.query.all()
        created_count = 0
        scanned_count = 0
        for soc in societies:
            if not soc:
                continue
            flats = Flat.query.filter_by(society_id=soc.id).all()
            scanned_count += len(flats)
            bills = BillingService.generate_monthly_bills(society_id=soc.id, billing_month=month)
            created_count += len(bills)
        return {
            "records_scanned": scanned_count,
            "records_created": created_count,
            "records_updated": 0,
            "records_skipped": max(0, scanned_count - created_count),
        }

    @staticmethod
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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

<<<<<<< HEAD
    @staticmethod
    def allocate_multi_month_payment(resident_id, society_id, payment_amount):
        """
        Deterministically allocates a lump sum payment across unpaid bills in FIFO order
        (earliest due date / billing month first).
        Handles overpayment safely by crediting the remaining amount to resident.advance_balance.
        Returns a dict of allocations and remaining unallocated balance (if any).
        """
        if payment_amount <= 0:
            raise ValueError("Payment amount must be greater than 0")

        resident = db.session.get(Resident, resident_id) if resident_id else None

        unpaid_bills = (
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

        remaining_pool = float(payment_amount)
        allocations = []

        for bill in unpaid_bills:
            if remaining_pool <= 0.001:
                break
            due = float(bill.remaining_amount)
            if due <= 0.001:
                continue
            to_apply = min(due, remaining_pool)
            BillingService.apply_partial_payment(bill.id, to_apply)
            remaining_pool = round(remaining_pool - to_apply, 2)
            allocations.append(
                {
                    "bill_id": bill.id,
                    "billing_month": bill.billing_month,
                    "allocated_amount": to_apply,
                    "remaining_on_bill": bill.remaining_amount,
                    "status": bill.status,
                }
            )

        # Handle overpayment: store remaining pool as resident advance credit
        if remaining_pool > 0.001 and resident:
            resident.advance_balance = round((resident.advance_balance or 0.0) + remaining_pool, 2)
            db.session.commit()

        return {
            "total_paid": payment_amount,
            "total_allocated": round(payment_amount - remaining_pool, 2),
            "unallocated_balance": round(remaining_pool, 2),
            "advance_credited": round(remaining_pool, 2),
            "allocations": allocations,
        }

    @staticmethod
    def get_resident_ledger(resident_id, society_id):
        """
        Generates a clear financial statement / general ledger for a resident.
        Columns: DATE, DESCRIPTION, DEBIT, CREDIT, BALANCE.
        Debits: Monthly maintenance charges, late fees, additional charges.
        Credits: Payment receipts, advance credits applied.
        """
        from app.models import Payment

        resident = Resident.query.filter_by(
            id=resident_id, society_id=society_id
        ).first()
        if not resident:
            raise ValueError("Resident not found")

        bills = (
            MaintenanceBill.query.filter_by(
                resident_id=resident_id, society_id=society_id
            )
            .order_by(MaintenanceBill.billing_month.asc())
            .all()
        )

        payments = (
            Payment.query.filter_by(
                resident_id=resident_id,
                society_id=society_id,
            )
            .filter(Payment.status.in_(["captured", "Success"]))
            .order_by(Payment.payment_date.asc())
            .all()
        )

        raw_entries = []

        # Process each bill
        for b in bills:
            year, month = map(int, b.billing_month.split("-"))
            bill_date = date(year, month, 1)
            # Maintenance debit
            raw_entries.append(
                {
                    "date": bill_date,
                    "description": f"Monthly Maintenance Charge ({b.billing_month}) - Bill #{b.bill_number}",
                    "debit": float(b.base_amount),
                    "credit": 0.0,
                    "type": "MAINTENANCE",
                    "ref": b.bill_number,
                }
            )
            # Late fee debit if assessed
            if b.late_fee > 0:
                raw_entries.append(
                    {
                        "date": b.due_date or bill_date,
                        "description": f"Late Fee Assessment ({b.billing_month}) - Bill #{b.bill_number}",
                        "debit": float(b.late_fee),
                        "credit": 0.0,
                        "type": "LATE_FEE",
                        "ref": b.bill_number,
                    }
                )
            # Additional charges debit
            if b.additional_charges > 0:
                raw_entries.append(
                    {
                        "date": bill_date,
                        "description": f"Additional Utility/Service Charge ({b.billing_month})",
                        "debit": float(b.additional_charges),
                        "credit": 0.0,
                        "type": "ADDITIONAL",
                        "ref": b.bill_number,
                    }
                )
            # Discount credit
            if b.discount > 0:
                raw_entries.append(
                    {
                        "date": bill_date,
                        "description": f"Discount Applied ({b.billing_month})",
                        "debit": 0.0,
                        "credit": float(b.discount),
                        "type": "DISCOUNT",
                        "ref": b.bill_number,
                    }
                )

        # Process each payment
        for p in payments:
            p_date = p.payment_date.date() if p.payment_date else utcnow().date()
            raw_entries.append(
                {
                    "date": p_date,
                    "description": f"Payment Received ({p.payment_method}) - Ref: {p.transaction_id}",
                    "debit": 0.0,
                    "credit": float(p.amount_paid),
                    "type": "PAYMENT",
                    "ref": p.transaction_id,
                }
            )

        # Sort all entries chronologically
        raw_entries.sort(key=lambda x: (x["date"], 0 if x["debit"] > 0 else 1))

        # Compute running balance
        running_balance = 0.0
        ledger_rows = []
        total_debits = 0.0
        total_credits = 0.0

        for item in raw_entries:
            total_debits += item["debit"]
            total_credits += item["credit"]
            running_balance += item["debit"] - item["credit"]
            ledger_rows.append(
                {
                    "date": item["date"].strftime("%Y-%m-%d"),
                    "description": item["description"],
                    "debit": round(item["debit"], 2),
                    "credit": round(item["credit"], 2),
                    "balance": round(running_balance, 2),
                    "type": item["type"],
                    "ref": item["ref"],
                }
            )

        advance_bal = getattr(resident, "advance_balance", 0.0) or 0.0

        return {
            "resident": {
                "id": resident.id,
                "full_name": resident.full_name,
                "mobile": resident.mobile,
                "flat_number": resident.flat.flat_number if resident.flat else "N/A",
                "advance_balance": advance_bal,
            },
            "entries": ledger_rows,
            "total_debits": round(total_debits, 2),
            "total_credits": round(total_credits, 2),
            "closing_balance": round(running_balance, 2),
            "advance_balance": round(advance_bal, 2),
            "status": "Clear" if abs(running_balance) < 0.01 else ("Outstanding" if running_balance > 0 else "Credit"),
        }

    @staticmethod
    def get_defaulters_list(
        society_id,
        building_id=None,
        block_id=None,
        min_amount=None,
        min_months=None,
        as_of=None,
    ):
        """
        Defaulter query engine for society admin.
        Finds all residents/flats in the society with overdue/unpaid maintenance bills.
        Calculates risk levels (LOW, MEDIUM, HIGH, CRITICAL), lifecycle stage, and reminder history.
        """
        from app.models import Payment, NotificationLog, DefaulterFollowUp

        as_of = as_of or utcnow().date()

        # Get all flats in this society
        flat_query = Flat.query.filter_by(society_id=society_id)
        if building_id:
            flat_query = flat_query.filter_by(building_id=building_id)
        if block_id:
            flat_query = flat_query.filter_by(block_id=block_id)
        flats = flat_query.all()

        defaulters = []

        for flat in flats:
            resident = Resident.query.filter_by(
                flat_id=flat.id, society_id=society_id, is_primary=True
            ).first()
            if not resident:
                continue

            unpaid = (
                MaintenanceBill.query.filter_by(
                    flat_id=flat.id,
                    society_id=society_id,
                )
                .filter(
                    MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
                    MaintenanceBill.remaining_amount > 0,
                    MaintenanceBill.due_date < as_of,
                )
                .order_by(MaintenanceBill.billing_month.asc())
                .all()
            )

            if not unpaid:
                continue

            pending_months_count = len(unpaid)
            if min_months and pending_months_count < int(min_months):
                continue

            total_maintenance = sum(b.base_amount for b in unpaid)
            total_late_fees = sum(b.late_fee for b in unpaid)
            total_outstanding = sum(b.remaining_amount for b in unpaid)

            if min_amount and total_outstanding < float(min_amount):
                continue

            # Earliest overdue date
            earliest_due = unpaid[0].due_date
            days_overdue = max(0, (as_of - earliest_due).days) if earliest_due else 0

            # Last payment
            last_p = (
                Payment.query.filter_by(
                    society_id=society_id,
                    resident_id=resident.id,
                )
                .filter(Payment.status.in_(["captured", "Success", "paid"]))
                .order_by(Payment.payment_date.desc())
                .first()
            )

            # Reminder history from NotificationLog
            reminders = (
                NotificationLog.query.filter(
                    NotificationLog.society_id == society_id,
                    NotificationLog.user_id == resident.user_id if resident.user_id else False,
                    NotificationLog.notification_type.in_(["OVERDUE_REMINDER", "UPCOMING_REMINDER", "ESCALATION_NOTICE"]),
                )
                .order_by(NotificationLog.created_at.desc())
                .all()
            )
            reminder_count = len(reminders)
            last_reminder_date = (
                reminders[0].created_at.strftime("%Y-%m-%d")
                if reminders and reminders[0].created_at
                else "Never"
            )

            # Follow-ups
            open_followup = DefaulterFollowUp.query.filter_by(
                society_id=society_id, resident_id=resident.id, status="OPEN"
            ).first()

            # Risk scoring algorithm (deterministic)
            if days_overdue > 90 or pending_months_count >= 4 or total_outstanding > 15000:
                risk_level = "CRITICAL"
                stage = "CRITICAL"
                next_action = "Initiate Admin Review & Legal Notice"
            elif days_overdue > 60 or pending_months_count >= 3:
                risk_level = "HIGH"
                stage = "ESCALATED"
                next_action = "Send Final Escalation & Call Resident"
            elif days_overdue > 30 or pending_months_count >= 2:
                risk_level = "MEDIUM"
                stage = "REMINDER_2"
                next_action = "Send Strong Second Reminder"
            else:
                risk_level = "LOW"
                stage = "REMINDER_1"
                next_action = "Send Friendly Reminder"

            if open_followup:
                stage = "ADMIN_REVIEW"
                next_action = f"Follow-up due: {open_followup.due_date or 'Pending'}"

            defaulters.append(
                {
                    "resident_id": resident.id,
                    "user_id": resident.user_id,
                    "resident_name": resident.full_name,
                    "mobile": resident.mobile,
                    "email": resident.email or "-",
                    "flat_id": flat.id,
                    "flat_number": flat.flat_number,
                    "property_key": flat.property_key,
                    "building_name": flat.building.name if flat.building else "-",
                    "block_name": flat.block.name if flat.block else "-",
                    "pending_months_count": pending_months_count,
                    "pending_months": [b.billing_month for b in unpaid],
                    "maintenance_due": total_maintenance,
                    "late_fees_due": total_late_fees,
                    "total_outstanding": total_outstanding,
                    "earliest_due_date": earliest_due.strftime("%Y-%m-%d") if earliest_due else "-",
                    "days_overdue": days_overdue,
                    "last_payment_date": last_p.payment_date.strftime("%Y-%m-%d") if last_p and last_p.payment_date else "Never",
                    "last_payment_amount": last_p.amount_paid if last_p else 0.0,
                    "reminder_count": reminder_count,
                    "last_reminder_date": last_reminder_date,
                    "risk_level": risk_level,
                    "stage": stage,
                    "next_action": next_action,
                    "has_open_followup": open_followup is not None,
                }
            )

        # Sort defaulters by total outstanding descending
        defaulters.sort(key=lambda x: x["total_outstanding"], reverse=True)
        return defaulters

    @staticmethod
    def get_aging_buckets_summary(society_id, as_of=None):
        """
        Calculates 5-tier aging breakdown (Current, 1-30, 31-60, 61-90, 90+ days)
        with resident counts, outstanding amounts, and percentages across all maintenance bills.
        """
        as_of = as_of or utcnow().date()

        # All pending/overdue bills with remaining amount > 0
        all_unpaid = (
            MaintenanceBill.query.filter_by(society_id=society_id)
            .filter(
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
                MaintenanceBill.remaining_amount > 0,
            )
            .all()
        )

        current_bills = [b for b in all_unpaid if b.due_date >= as_of]
        overdue_bills = [b for b in all_unpaid if b.due_date < as_of]

        total_overdue_amount = sum(b.remaining_amount for b in overdue_bills) or 1.0
        current_amount = sum(b.remaining_amount for b in current_bills)
        current_count = len(set(b.resident_id for b in current_bills if b.resident_id))

        b_1_30 = [b for b in overdue_bills if (as_of - b.due_date).days <= 30]
        b_31_60 = [b for b in overdue_bills if 30 < (as_of - b.due_date).days <= 60]
        b_61_90 = [b for b in overdue_bills if 60 < (as_of - b.due_date).days <= 90]
        b_90_plus = [b for b in overdue_bills if (as_of - b.due_date).days > 90]

        a_1_30 = sum(b.remaining_amount for b in b_1_30)
        a_31_60 = sum(b.remaining_amount for b in b_31_60)
        a_61_90 = sum(b.remaining_amount for b in b_61_90)
        a_90_plus = sum(b.remaining_amount for b in b_90_plus)

        c_1_30 = len(set(b.resident_id for b in b_1_30 if b.resident_id))
        c_31_60 = len(set(b.resident_id for b in b_31_60 if b.resident_id))
        c_61_90 = len(set(b.resident_id for b in b_61_90 if b.resident_id))
        c_90_plus = len(set(b.resident_id for b in b_90_plus if b.resident_id))

        defaulter_residents = len(set(b.resident_id for b in overdue_bills if b.resident_id))

        return {
            "current": {
                "label": "Current",
                "count": current_count,
                "amount": current_amount,
                "percentage": round((current_amount / (total_overdue_amount + current_amount)) * 100, 1),
            },
            "bucket_1_30": {
                "label": "1–30 Days",
                "count": c_1_30,
                "amount": a_1_30,
                "percentage": round((a_1_30 / total_overdue_amount) * 100, 1),
            },
            "bucket_31_60": {
                "label": "31–60 Days",
                "count": c_31_60,
                "amount": a_31_60,
                "percentage": round((a_31_60 / total_overdue_amount) * 100, 1),
            },
            "bucket_61_90": {
                "label": "61–90 Days",
                "count": c_61_90,
                "amount": a_61_90,
                "percentage": round((a_61_90 / total_overdue_amount) * 100, 1),
            },
            "bucket_90_plus": {
                "label": "90+ Days Severe",
                "count": c_90_plus,
                "amount": a_90_plus,
                "percentage": round((a_90_plus / total_overdue_amount) * 100, 1),
            },
            "total_defaulters_count": defaulter_residents,
            "total_outstanding_amount": total_overdue_amount,
        }

    @staticmethod
    def get_resident_financial_statement(resident_id, society_id, start_date=None, end_date=None):
        """
        Generates itemized financial ledger statement for a resident.
        Shows Opening Balance, Charges, Late Fees, Payments, Refunds, Advance, and Closing Balance.
        """
        from app.models import Payment, RefundRequest

        resident = db.session.get(Resident, resident_id)
        if not resident:
            return None

        bills = (
            MaintenanceBill.query.filter_by(society_id=society_id, resident_id=resident_id)
            .order_by(MaintenanceBill.created_at.asc())
            .all()
        )
        payments = (
            Payment.query.filter_by(society_id=society_id, resident_id=resident_id)
            .filter(Payment.status.in_(["captured", "Success", "paid"]))
            .order_by(Payment.payment_date.asc())
            .all()
        )

        statement_entries = []
        running_balance = 0.0

        for b in bills:
            # Charges
            running_balance += float(b.base_amount)
            statement_entries.append({
                "date": b.created_at.strftime("%Y-%m-%d") if b.created_at else "-",
                "type": "MAINTENANCE_BILL",
                "description": f"Maintenance Bill - {b.billing_month}",
                "debit": float(b.base_amount),
                "credit": 0.0,
                "balance": running_balance,
            })
            if b.late_fee > 0:
                running_balance += float(b.late_fee)
                statement_entries.append({
                    "date": b.created_at.strftime("%Y-%m-%d") if b.created_at else "-",
                    "type": "LATE_FEE",
                    "description": f"Late Fee Charge - {b.billing_month}",
                    "debit": float(b.late_fee),
                    "credit": 0.0,
                    "balance": running_balance,
                })

        for p in payments:
            running_balance -= float(p.amount_paid)
            statement_entries.append({
                "date": p.payment_date.strftime("%Y-%m-%d") if p.payment_date else "-",
                "type": "PAYMENT",
                "description": f"Payment ({p.payment_method}) - Tx #{p.transaction_id}",
                "debit": 0.0,
                "credit": float(p.amount_paid),
                "balance": running_balance,
            })

        # Sort all statement entries chronologically
        statement_entries.sort(key=lambda x: x["date"])

        total_billed = sum(b.total_amount for b in bills)
        total_paid = sum(p.amount_paid for p in payments)
        total_late_fees = sum(b.late_fee for b in bills)
        outstanding = max(0.0, total_billed - total_paid)

        return {
            "resident_name": resident.full_name,
            "property_key": resident.flat.property_key if resident.flat else "-",
            "advance_balance": resident.advance_balance or 0.0,
            "opening_balance": 0.0,
            "total_billed": total_billed,
            "total_paid": total_paid,
            "total_late_fees": total_late_fees,
            "closing_balance": outstanding,
            "entries": statement_entries,
        }


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32



