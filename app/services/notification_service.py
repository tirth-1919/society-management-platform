<<<<<<< HEAD
from app.utils import utcnow
from datetime import datetime, timedelta

from app.config import Config
from app.models import (
    db,
    NotificationLog,
    MaintenanceBill,
    MaintenanceConfig,
    Resident,
    NotificationPreference,
)
=======
﻿from app.utils import utcnow
from datetime import datetime, timedelta

from app.config import Config
from app.models import db, NotificationLog, MaintenanceBill, MaintenanceConfig, Resident
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class NotificationService:
    @staticmethod
    def send_notification(
<<<<<<< HEAD
        recipient,
        message,
        channel="In-App",
        subject=None,
        society_id=None,
        user_id=None,
        category="General",
    ):
        """Unified notification sender with delivery status logging and preference respect."""
        if user_id:
            pref = NotificationPreference.query.filter_by(user_id=user_id).first()
            if pref:
                if category == "Announcement" and not pref.announcements:
                    return None
                if category == "Reminder" and not pref.payment_reminders:
                    return None

        log = NotificationLog(
            society_id=society_id,
            user_id=user_id,
=======
        recipient, message, channel="In-App", subject=None, society_id=None
    ):
        """Unified notification sender with delivery status logging."""
        log = NotificationLog(
            society_id=society_id,
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            recipient_mobile_or_email=recipient,
            channel=channel,
            subject=subject,
            message=message,
            status="Sent",
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
<<<<<<< HEAD
    def check_reminder_cooldown(user_id, billing_month, notification_type, cooldown_hours=24):
        """
        Checks if a notification of notification_type was sent to user_id for billing_month
        within the last cooldown_hours. Returns True if on cooldown (suppress send), False if allowed.
        """
        if not user_id:
            return False
        cutoff = utcnow() - timedelta(hours=cooldown_hours)
        recent = NotificationLog.query.filter(
            NotificationLog.user_id == user_id,
            NotificationLog.billing_month == billing_month,
            NotificationLog.notification_type == notification_type,
            NotificationLog.sent_at >= cutoff,
        ).first()
        return recent is not None

    @staticmethod
    def send_billing_notification(
        user, billing_month, notification_type, message, subject=None, cooldown_hours=24
    ):
        """Log one resident-scoped notification for a billing event, respecting preferences and cooldowns."""
        # Check user notification preferences
        pref = NotificationPreference.query.filter_by(user_id=user.id).first()
        if pref:
            if (
                notification_type in ("DUE_REMINDER", "OVERDUE_REMINDER", "LATE_FEE_NOTICE", "ESCALATION_NOTICE")
                and not pref.maintenance_reminders
                and not pref.payment_reminders
            ):
                return None
            if (
                notification_type == "ANNOUNCEMENT"
                and not pref.announcements
            ):
                return None

        # Cooldown enforcement
        if NotificationService.check_reminder_cooldown(user.id, billing_month, notification_type, cooldown_hours=cooldown_hours):
            return None

        log = NotificationLog(
            society_id=user.society_id,
            user_id=user.id,
            recipient_mobile_or_email=user.mobile or user.email or "N/A",
=======
    def send_billing_notification(
        user, billing_month, notification_type, message, subject=None
    ):
        """Log one resident-scoped notification for a billing event."""
        existing = NotificationLog.query.filter_by(
            user_id=user.id,
            billing_month=billing_month,
            notification_type=notification_type,
        ).first()
        if existing:
            return existing
        log = NotificationLog(
            society_id=user.society_id,
            user_id=user.id,
            recipient_mobile_or_email=user.mobile,
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            channel="SMS",
            notification_type=notification_type,
            billing_month=billing_month,
            subject=subject,
            message=message,
            status="Sent",
        )
        db.session.add(log)
        db.session.commit()
        return log

    @staticmethod
<<<<<<< HEAD
    def retry_failed_notifications(society_id=None):
        """Retries failed notification logs up to 3 times."""
        q = NotificationLog.query.filter_by(status="Failed").filter(NotificationLog.retry_count < 3)
        if society_id:
            q = q.filter_by(society_id=society_id)
        failed_logs = q.all()
        retried = []
        for log in failed_logs:
            log.retry_count += 1
            log.status = "Sent"
            log.sent_at = utcnow()
            retried.append(log)
        db.session.commit()
        return retried

    @staticmethod
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    def send_maintenance_reminders(as_of=None, society_id=None):
        """Send one upcoming or overdue SMS per unpaid billing month."""
        as_of = as_of or utcnow().date()
        query = MaintenanceBill.query.filter(
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
        )
        if society_id is not None:
            query = query.filter_by(society_id=society_id)

        sent = []
        for bill in query.order_by(MaintenanceBill.billing_month.asc()).all():
            if bill.status == "Paid" or not bill.due_date:
                continue
            resident = Resident.query.filter_by(
                id=bill.resident_id, is_primary=True
            ).first()
            if not resident or not resident.user:
                continue
            if (
                resident.user.maintenance_start_month
                and bill.billing_month < resident.user.maintenance_start_month
            ):
                continue
            config = MaintenanceConfig.query.filter_by(
                society_id=bill.society_id
            ).first()
            reminder_days = Config.MAINTENANCE_REMINDER_DAYS
            if config and config.grace_period_days is not None:
                reminder_days = max(0, config.grace_period_days)

            month_label = datetime.strptime(bill.billing_month, "%Y-%m").strftime(
                "%B %Y"
            )
            if bill.due_date > as_of >= bill.due_date - timedelta(days=reminder_days):
                notification_type = "DUE_REMINDER"
                message = (
                    f"Reminder: Your society maintenance of "
                    f"₹{bill.base_amount:,.0f} for {month_label} is due on "
                    f"{bill.due_date.strftime('%d %B %Y')}."
                )
            elif bill.billing_month < as_of.strftime("%Y-%m") and as_of > bill.due_date:
                notification_type = "OVERDUE_REMINDER"
                late_fee = (
                    config.late_fee_per_month if config else Config.LATE_FEE_PER_MONTH
                )
                message = (
                    f"Your society maintenance for {month_label} is overdue. "
                    f"Maintenance: ₹{bill.base_amount:,.0f}. "
                    f"Late fee: ₹{late_fee:,.0f}. "
                    f"Total due: ₹{bill.base_amount + late_fee:,.0f}."
                )
            else:
                continue

            log = NotificationService.send_billing_notification(
                resident.user, bill.billing_month, notification_type, message
            )
            sent.append(log)
            if notification_type == "OVERDUE_REMINDER":
                late_fee_log = NotificationService.send_billing_notification(
                    resident.user,
                    bill.billing_month,
                    "LATE_FEE_NOTICE",
                    f"Late fee notice for {month_label}: ₹{late_fee:,.0f} has been applied.",
                )
                sent.append(late_fee_log)
        return sent


