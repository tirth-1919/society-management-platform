from app.models import (
    db,
    Visitor,
    PreApprovedPass,
    Resident,
    AutomationAlert,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import timedelta


class VisitorSecurityAutomationService:
    """
    Implements Phase 15 Visitor & Security Gate Automation:
    - Pre-approved pass QR validation
    - Visitor entry/exit checkout
    - Overstay detection (> 6h on premises)
    - Security gate activity digest
    """

    @staticmethod
    def validate_pre_approved_pass(pass_code, society_id):
        """Validates a pre-approved pass code presented at the security gate."""
        p = PreApprovedPass.query.filter_by(pass_code=pass_code, society_id=society_id).first()
        if not p:
            return {"valid": False, "reason": "Invalid pass code"}
        if p.is_used:
            return {"valid": False, "reason": "Pass has already been used"}
        if p.expected_date < utcnow().date():
            return {"valid": False, "reason": "Pass has expired"}

        return {
            "valid": True,
            "pass_id": p.id,
            "visitor_name": p.visitor_name,
            "mobile": p.mobile,
            "flat_number": p.flat.flat_number if p.flat else "-",
            "purpose": p.purpose,
        }

    @staticmethod
    def process_pass_entry(pass_code, society_id):
        """Logs gate entry for a pre-approved visitor."""
        val = VisitorSecurityAutomationService.validate_pre_approved_pass(pass_code, society_id)
        if not val["valid"]:
            raise ValueError(val["reason"])

        p = PreApprovedPass.query.filter_by(pass_code=pass_code, society_id=society_id).first()
        p.is_used = True

        visitor = Visitor(
            society_id=society_id,
            flat_id=p.flat_id,
            resident_id=p.resident_id,
            visitor_name=p.visitor_name,
            mobile=p.mobile,
            purpose=p.purpose or "Guest",
            pass_code=pass_code,
            approval_status="Approved",
            entry_time=utcnow(),
        )
        db.session.add(visitor)
        db.session.commit()

        # Notify resident
        resident = db.session.get(Resident, p.resident_id)
        if resident and resident.user:
            NotificationService.send_notification(
                recipient=resident.mobile or resident.email or "N/A",
                message=f"Visitor Check-In: {visitor.visitor_name} has arrived at the security gate for Flat {p.flat.flat_number if p.flat else '-'}.",
                channel="In-App",
                society_id=society_id,
                user_id=resident.user_id,
                category="General",
            )
        return visitor

    @staticmethod
    def detect_overstaying_visitors(society_id, hours_threshold=6):
        """Detects active visitors who entered > hours_threshold ago without logged exit."""
        cutoff = utcnow() - timedelta(hours=hours_threshold)
        overstaying = Visitor.query.filter(
            Visitor.society_id == society_id,
            Visitor.exit_time.is_(None),
            Visitor.entry_time <= cutoff,
        ).all()

        alerts_created = 0
        for v in overstaying:
            alert = AutomationAlert(
                society_id=society_id,
                alert_type="VISITOR_OVERSTAY",
                severity="WARNING",
                title=f"Visitor Overstay: {v.visitor_name}",
                message=f"Visitor '{v.visitor_name}' (Mobile: {v.mobile}) entered at {v.entry_time.strftime('%H:%M')} for Flat {v.flat.flat_number if v.flat else '-'} and has exceeded {hours_threshold}h stay.",
                is_resolved=False,
            )
            db.session.add(alert)
            alerts_created += 1

        db.session.commit()
        return {
            "overstaying_count": len(overstaying),
            "alerts_created": alerts_created,
            "visitors": [{"id": v.id, "name": v.visitor_name, "entry_time": str(v.entry_time)} for v in overstaying],
        }

    @staticmethod
    def get_security_gate_digest(society_id):
        """Generates gate activity digest for security administrators."""
        today_start = utcnow().replace(hour=0, minute=0, second=0)
        today_entries = Visitor.query.filter(
            Visitor.society_id == society_id,
            Visitor.entry_time >= today_start,
        ).count()
        currently_inside = Visitor.query.filter(
            Visitor.society_id == society_id,
            Visitor.exit_time.is_(None),
        ).count()

        return {
            "society_id": society_id,
            "date": utcnow().strftime("%Y-%m-%d"),
            "today_entries_count": today_entries,
            "currently_inside_count": currently_inside,
        }
