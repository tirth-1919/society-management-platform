from app.models import (
    Resident,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow


class IntercomRelayAutomationService:
    """
    Implements Phase 35 Intercom & Communication Relay Automation:
    - Digital intercom call relay (Gate to Flat)
    - Visitor authorization prompt dispatch
    - Gate security emergency intercom call
    """

    @staticmethod
    def dispatch_gate_visitor_call(flat_id, visitor_name, society_id):
        """Simulates gatekeeper intercom authorization call to resident's device."""
        resident = Resident.query.filter_by(flat_id=flat_id, society_id=society_id, is_primary=True).first()
        if not resident or not resident.user:
            return {"dispatched": False, "reason": "No active resident registered on flat"}

        NotificationService.send_notification(
            recipient=resident.mobile or "N/A",
            message=f"🔔 Gate Intercom: Visitor '{visitor_name}' is requesting entry for Flat {resident.flat.flat_number if resident.flat else '-'}.",
            channel="In-App",
            society_id=society_id,
            user_id=resident.user_id,
            category="General",
        )
        return {
            "dispatched": True,
            "resident_name": resident.full_name,
            "flat_id": flat_id,
            "visitor_name": visitor_name,
            "timestamp": utcnow().isoformat(),
        }
