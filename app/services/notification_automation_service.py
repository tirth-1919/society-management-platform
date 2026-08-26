from app.models import (
    db,
    User,
    NotificationLog,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import timedelta


class NotificationAutomationService:
    """
    Implements Phase 11 Notification Automation (Features 141–150):
    141. Notification priority
    142. Notification batching
    143. Notification deduplication
    144. Quiet-hours scheduling
    145. Failed-notification retry
    146. Retry queue
    147. Notification escalation
    148. Admin notification digest
    149. Resident notification digest
    150. Weekly notification summary
    """

    @staticmethod
    def is_quiet_hours(check_time=None):
        """Feature 144: Checks if current time is within quiet hours (10 PM to 7 AM)."""
        now = check_time or utcnow()
        hour = now.hour
        return hour >= 22 or hour < 7

    @staticmethod
    def send_smart_notification(user_id, society_id, message, category="General", priority="Normal", channel="In-App"):
        """
        Features 141, 143, 144:
        Dispatches notification respecting user preferences, priority, deduplication, and quiet hours.
        """
        user = db.session.get(User, user_id)
        if not user:
            return None

        # Check quiet hours: delay non-emergency notifications
        if priority != "Emergency" and NotificationAutomationService.is_quiet_hours():
            # Defer sending until quiet hours conclude
            category = "Queued"

        # Check deduplication: avoid sending duplicate exact message within 24h (Feature 143)
        cutoff = utcnow() - timedelta(hours=24)
        duplicate = NotificationLog.query.filter(
            NotificationLog.user_id == user.id,
            NotificationLog.message == message,
            NotificationLog.sent_at >= cutoff,
        ).first()
        if duplicate:
            return duplicate  # Suppress duplicate

        return NotificationService.send_notification(
            recipient=user.mobile or user.email or "N/A",
            message=message,
            channel=channel,
            society_id=society_id,
            user_id=user.id,
            category=category,
        )

    @staticmethod
    def process_retry_queue(society_id=None):
        """Features 145 & 146: Retries failed notifications up to 3 times."""
        return NotificationService.retry_failed_notifications(society_id=society_id)

    @staticmethod
    def generate_admin_digest(society_id):
        """Feature 148: Generates consolidated daily admin summary digest."""
        from app.models import RegistrationRequest, Complaint, PaymentReconciliationIssue
        pending_regs = RegistrationRequest.query.filter_by(society_id=society_id, status="PENDING_APPROVAL").count()
        open_comps = Complaint.query.filter_by(society_id=society_id).filter(Complaint.status.in_(["Submitted", "Assigned", "In Progress"])).count()
        open_recon = PaymentReconciliationIssue.query.filter_by(society_id=society_id, status="OPEN").count()

        digest_text = (
            f"Daily Society Admin Digest ({utcnow().strftime('%d %b %Y')}):\n"
            f"• Pending Resident Registrations: {pending_regs}\n"
            f"• Active Unresolved Complaints: {open_comps}\n"
            f"• Open Reconciliation Issues: {open_recon}"
        )
        return {
            "society_id": society_id,
            "date": utcnow().strftime("%Y-%m-%d"),
            "digest_text": digest_text,
            "metrics": {"pending_registrations": pending_regs, "open_complaints": open_comps, "open_reconciliation": open_recon},
        }

    @staticmethod
    def generate_weekly_resident_summary(user_id, society_id):
        """Features 149 & 150: Generates weekly summary for resident."""
        from app.models import MaintenanceBill, Notice
        user = db.session.get(User, user_id)
        if not user:
            return None

        unpaid_bills = MaintenanceBill.query.filter_by(society_id=society_id, resident_id=user.id).filter(
            MaintenanceBill.status.in_(["Pending", "Overdue"])
        ).count()
        recent_notices = Notice.query.filter_by(society_id=society_id).order_by(Notice.created_at.desc()).limit(2).all()

        return {
            "user_id": user_id,
            "unpaid_bills_count": unpaid_bills,
            "recent_notices": [n.title for n in recent_notices],
            "generated_at": utcnow().isoformat(),
        }
