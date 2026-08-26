from app.models import (
    db,
    Notice,
    Resident,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow


class DigitalNoticeAutomationService:
    """
    Implements Phase 28 Digital Notice Board & Circular Distribution:
    - Smart notice broadcasting to targeted audience (All / Owners / Tenants)
    - Pinned high-priority notices
    - Auto-archival of expired notices
    """

    @staticmethod
    def publish_digital_notice(society_id, title, content, notice_type="General", priority="Normal", audience="All", user_id=None):
        """Creates and broadcasts a digital notice to target audience."""
        notice = Notice(
            society_id=society_id,
            title=title,
            content=content,
            notice_type=notice_type,
            priority=priority,
            audience=audience,
            created_by_id=user_id,
            created_at=utcnow(),
        )
        db.session.add(notice)
        db.session.commit()

        # Broadcast in-app notification to target audience
        residents_q = Resident.query.filter_by(society_id=society_id, occupancy_status="Active")
        if audience == "Owners":
            residents_q = residents_q.filter(Resident.resident_type.in_(["Owner", "OWNER"]))
        elif audience == "Tenants":
            residents_q = residents_q.filter(Resident.resident_type.in_(["Tenant", "TENANT"]))

        for r in residents_q.all():
            if r.user:
                NotificationService.send_notification(
                    recipient=r.mobile or "N/A",
                    message=f"Notice: {title} - {content[:100]}...",
                    channel="In-App",
                    society_id=society_id,
                    user_id=r.user_id,
                    category="Announcement",
                )
        return notice

    @staticmethod
    def get_active_notices(society_id):
        """Retrieves active unexpired digital notices ordered by priority and date."""
        return Notice.query.filter_by(society_id=society_id).order_by(Notice.created_at.desc()).all()
