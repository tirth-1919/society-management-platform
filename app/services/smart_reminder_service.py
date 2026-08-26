"""
SmartReminderService
====================
Deduplication-aware, preference-respecting reminder engine for residents.

RULES:
- Only sends reminders that are NOT already in NotificationLog for the
  same (user_id, billing_month, notification_type) within the cooldown
  window.  This relies on the existing unique constraint.
- Respects NotificationPreference: maintenance_reminders and
  payment_reminders flags gate all reminder types.
- Does NOT change billing amounts, payment status, or any financial record.
- Does NOT bypass the existing NotificationService cooldown logic.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import List

from app.models import (
    MaintenanceBill,
    NotificationLog,
    NotificationPreference,
    Resident,
    User,
    db,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class SmartReminderService:
    """Intelligent reminder dispatch — deduplication + preference-aware."""

    # ── Core dedup check ──────────────────────────────────────────────────

    @staticmethod
    def _already_sent(
        user_id: int,
        billing_month: str,
        notification_type: str,
        cooldown_hours: int = 24,
    ) -> bool:
        """
        Returns True if a notification of this type was already sent for
        this billing_month within the last cooldown_hours.
        """
        return NotificationService.check_reminder_cooldown(
            user_id, billing_month, notification_type, cooldown_hours=cooldown_hours
        )

    # ── Preference gate ───────────────────────────────────────────────────

    @staticmethod
    def _pref_allows(user_id: int, reminder_type: str) -> bool:
        """
        Return True if the resident's NotificationPreference permits this
        reminder type.  Defaults to True if no preference row exists yet.
        """
        pref = NotificationPreference.query.filter_by(user_id=user_id).first()
        if not pref:
            return True  # default-on
        if reminder_type in ("DUE_REMINDER", "OVERDUE_REMINDER", "LATE_FEE_NOTICE",
                              "ESCALATION_NOTICE"):
            return pref.maintenance_reminders and pref.payment_reminders
        if reminder_type in ("PAYMENT_FAILED", "PAYMENT_PENDING", "CASH_VERIFICATION"):
            return pref.payment_reminders
        if reminder_type == "ANNOUNCEMENT":
            return pref.announcements
        return True  # unknown types: allow

    # ── Public: send one resident's reminders ────────────────────────────

    @classmethod
    def send_resident_reminders(cls, resident: Resident) -> List[NotificationLog]:
        """
        Evaluate and dispatch all outstanding smart reminders for one
        resident.  Called from the automation engine or a CLI command.
        Returns the list of NotificationLog rows actually created.
        """
        if not resident or not resident.user_id:
            return []

        user = db.session.get(User, resident.user_id)
        if not user or user.account_status != "ACTIVE":
            return []

        sent: List[NotificationLog] = []
        now = utcnow()
        today = now.date()

        # ── Overdue / due-soon bills ──────────────────────────────────────
        unpaid_bills = (
            MaintenanceBill.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
            )
            .filter(MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]))
            .order_by(MaintenanceBill.due_date.asc())
            .all()
        )

        for bill in unpaid_bills:
            # Skip if the bill predates the resident's maintenance_start_month
            if (
                user.maintenance_start_month
                and bill.billing_month < user.maintenance_start_month
            ):
                continue

            if not bill.due_date:
                continue

            days_to_due = (bill.due_date - today).days

            # Overdue
            if bill.status == "Overdue" or (bill.due_date < today):
                ntype = "OVERDUE_REMINDER"
                if not cls._pref_allows(user.id, ntype):
                    continue
                if cls._already_sent(user.id, bill.billing_month, ntype, cooldown_hours=48):
                    continue
                msg = (
                    f"Your maintenance bill for {bill.billing_month} is overdue. "
                    f"Balance due: ₹{bill.remaining_amount:,.2f}. "
                    f"Please pay immediately to avoid additional late fees."
                )
                log = NotificationService.send_billing_notification(
                    user, bill.billing_month, ntype, msg,
                    subject=f"Overdue Maintenance — {bill.billing_month}",
                    cooldown_hours=48,
                )
                if log:
                    sent.append(log)

            # Due in 3 days or less (upcoming reminder)
            elif 0 <= days_to_due <= 3:
                ntype = "DUE_REMINDER"
                if not cls._pref_allows(user.id, ntype):
                    continue
                if cls._already_sent(user.id, bill.billing_month, ntype, cooldown_hours=24):
                    continue
                msg = (
                    f"Your maintenance of ₹{bill.remaining_amount:,.2f} "
                    f"for {bill.billing_month} is due on "
                    f"{bill.due_date.strftime('%d %b %Y')} "
                    f"({days_to_due} day(s) remaining)."
                )
                log = NotificationService.send_billing_notification(
                    user, bill.billing_month, ntype, msg,
                    subject=f"Maintenance Due Soon — {bill.billing_month}",
                    cooldown_hours=24,
                )
                if log:
                    sent.append(log)

        # ── Failed payments ───────────────────────────────────────────────
        from app.models import Payment
        recently_failed = (
            Payment.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
                status="failed",
            )
            .filter(Payment.payment_date >= now - timedelta(hours=24))
            .all()
        )
        for p in recently_failed:
            billing_month = p.bill.billing_month if p.bill else "unknown"
            ntype = "PAYMENT_FAILED"
            if not cls._pref_allows(user.id, ntype):
                continue
            if cls._already_sent(user.id, billing_month, ntype, cooldown_hours=12):
                continue
            msg = (
                f"Your payment of ₹{p.amount_paid:,.2f} on "
                f"{p.payment_date.strftime('%d %b %Y, %I:%M %p') if p.payment_date else 'unknown date'} "
                f"was unsuccessful."
                + (f" Reason: {p.failure_reason}." if p.failure_reason else "")
                + " Please try again."
            )
            log = NotificationService.send_billing_notification(
                user, billing_month, ntype, msg,
                subject="Payment Failed — Action Required",
                cooldown_hours=12,
            )
            if log:
                sent.append(log)

        # ── Pending cash verification ─────────────────────────────────────
        pending_cash = (
            Payment.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
                payment_method="Cash",
                status="pending",
            )
            .filter(Payment.payment_date >= now - timedelta(hours=72))
            .all()
        )
        for p in pending_cash:
            billing_month = p.bill.billing_month if p.bill else "unknown"
            ntype = "CASH_VERIFICATION"
            if not cls._pref_allows(user.id, ntype):
                continue
            if cls._already_sent(user.id, billing_month, ntype, cooldown_hours=24):
                continue
            msg = (
                f"Your cash payment of ₹{p.amount_paid:,.2f} submitted on "
                f"{p.payment_date.strftime('%d %b %Y') if p.payment_date else 'unknown date'} "
                f"is awaiting Admin verification. No further action needed from your side."
            )
            log = NotificationService.send_billing_notification(
                user, billing_month, ntype, msg,
                subject="Cash Payment Awaiting Verification",
                cooldown_hours=24,
            )
            if log:
                sent.append(log)

        return sent

    # ── Batch: run for all active residents in a society ─────────────────

    @classmethod
    def run_society_reminders(cls, society_id: int) -> int:
        """
        Dispatch smart reminders for all active residents in a society.
        Returns total count of notifications sent.
        """
        residents = Resident.query.filter_by(
            society_id=society_id,
            occupancy_status="Active",
            is_primary=True,
        ).all()

        total = 0
        for r in residents:
            try:
                sent = cls.send_resident_reminders(r)
                total += len(sent)
            except Exception as exc:
                logger.error(
                    "SmartReminderService: error for resident %s: %s", r.id, exc
                )
        return total
