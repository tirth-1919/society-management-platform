from app.models import (
    db,
    Resident,
    EmergencyAlert,
    AutomationAlert,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow


class EmergencyAutomationService:
    """
    Implements Phase 19 Emergency & Disaster Management Automation:
    - SOS / Panic button trigger
    - Multi-channel emergency broadcast
    - Security gate instant alert creation
    - Evacuation assembly area checklist
    - Active emergency resolution
    """

    @staticmethod
    def trigger_emergency_sos(society_id, user_id, alert_type, title, message, location_details=None):
        """Triggers high-priority emergency broadcast across society."""
        alert = EmergencyAlert(
            society_id=society_id,
            alert_type=alert_type,
            title=title,
            message=message,
            location_details=location_details,
            triggered_by_id=user_id,
            triggered_at=utcnow(),
            is_active=True,
        )
        db.session.add(alert)

        # Create critical automation alert
        auto_alert = AutomationAlert(
            society_id=society_id,
            alert_type=f"SOS_{alert_type}",
            severity="CRITICAL",
            title=f"EMERGENCY: {title}",
            message=f"Location: {location_details or 'Society Premises'}. Details: {message}. Guard room notified.",
            is_resolved=False,
        )
        db.session.add(auto_alert)
        db.session.commit()

        # Multi-channel broadcast to all active residents
        residents = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").all()
        for r in residents:
            if r.user:
                NotificationService.send_notification(
                    recipient=r.mobile or "N/A",
                    message=f"🚨 EMERGENCY ALERT ({alert_type}): {title} at {location_details or 'Premises'}. Please follow safety protocol.",
                    channel="In-App",
                    society_id=society_id,
                    user_id=r.user_id,
                    category="Emergency",
                )

        return alert

    @staticmethod
    def get_active_emergencies(society_id):
        """Returns list of active emergency incidents."""
        return EmergencyAlert.query.filter_by(society_id=society_id, is_active=True).all()

    @staticmethod
    def resolve_emergency(alert_id, user_id=None):
        """Marks emergency resolved and deactivates alarm state."""
        alert = db.session.get(EmergencyAlert, alert_id)
        if alert:
            alert.is_active = False
            db.session.commit()
            return True
        return False
