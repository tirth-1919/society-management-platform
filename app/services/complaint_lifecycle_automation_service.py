from app.models import (
    db,
    Complaint,
    Resident,
    AutomationAlert,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import timedelta


class ComplaintLifecycleAutomationService:
    """
    Implements Phase 17 Complaint & Helpdesk SLA Lifecycle Automation:
    - Dynamic SLA tracking by priority (Emergency 4h, High 12h, Medium 24h, Low 48h)
    - Automatic escalation upon SLA breach
    - Resolution logging & resident feedback collection
    - SLA performance reporting
    """

    SLA_HOURS = {
        "Emergency": 4,
        "High": 12,
        "Medium": 24,
        "Low": 48,
    }

    @staticmethod
    def audit_sla_and_escalate_breaches(society_id):
        """Scans active complaints, detects SLA breaches, and raises committee escalation alerts."""
        now = utcnow()
        open_complaints = Complaint.query.filter_by(society_id=society_id).filter(
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
        ).all()

        breached = []
        escalations_created = 0

        for c in open_complaints:
            sla_h = ComplaintLifecycleAutomationService.SLA_HOURS.get(c.priority, 24)
            deadline = c.created_at + timedelta(hours=sla_h)

            if now > deadline:
                hours_over = int((now - deadline).total_seconds() / 3600)
                breached.append(c)

                existing = AutomationAlert.query.filter_by(
                    society_id=society_id,
                    alert_type="COMPLAINT_SLA_BREACH",
                    is_resolved=False,
                ).filter(AutomationAlert.message.contains(f"#{c.ticket_number}")).first()

                if not existing:
                    alert = AutomationAlert(
                        society_id=society_id,
                        alert_type="COMPLAINT_SLA_BREACH",
                        severity="CRITICAL" if c.priority in ["Emergency", "High"] else "WARNING",
                        title=f"SLA Breach: Ticket #{c.ticket_number} ({c.priority})",
                        message=f"Complaint '{c.title}' ({c.category}) is {hours_over}h past its {sla_h}h SLA resolution window.",
                        is_resolved=False,
                    )
                    db.session.add(alert)
                    escalations_created += 1

        db.session.commit()
        return {
            "total_open_complaints": len(open_complaints),
            "sla_breached_count": len(breached),
            "escalations_created": escalations_created,
            "breached_tickets": [c.ticket_number for c in breached],
        }

    @staticmethod
    def resolve_complaint(complaint_id, resolution_notes, resolved_by_user=None):
        """Marks complaint resolved, timestamps resolution, and sends resident feedback prompt."""
        c = db.session.get(Complaint, complaint_id)
        if not c:
            raise ValueError("Complaint not found")

        c.status = "Resolved"
        c.resolution_notes = resolution_notes
        c.resolved_at = utcnow()
        db.session.commit()

        # Notify resident
        resident = db.session.get(Resident, c.resident_id) if c.resident_id else None
        if resident and resident.user:
            NotificationService.send_notification(
                recipient=resident.mobile or resident.email or "N/A",
                message=f"Complaint Resolved: Ticket #{c.ticket_number} ({c.title}) has been resolved. Notes: {resolution_notes}. Please rate your resolution experience in the portal.",
                channel="In-App",
                society_id=c.society_id,
                user_id=resident.user_id,
                category="General",
            )
        return c
