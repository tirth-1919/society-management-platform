from app.utils import utcnow
from datetime import datetime, timedelta

from app.config import Config
from app.models import db, NotificationLog, MaintenanceBill, MaintenanceConfig, Resident


class NotificationService:
    @staticmethod
    def send_notification(
        recipient, message, channel="In-App", subject=None, society_id=None
    ):
        """Unified notification sender with delivery status logging."""
        log = NotificationLog(
            society_id=society_id,
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


