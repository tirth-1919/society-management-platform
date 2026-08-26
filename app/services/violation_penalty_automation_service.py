from app.models import (
    db,
    Flat,
    WorkOrder,
    AutomationAlert,
)
from app.utils import utcnow
import secrets


class ViolationPenaltyAutomationService:
    """
    Implements Phase 26 Violation & Penalty Automation:
    - Noise, pet, parking, and construction violation tracking
    - Graduated warning notices (1st warning, 2nd notice, escalated penalty)
    - Security task dispatch
    """

    @staticmethod
    def log_violation(society_id, flat_id, violation_type, description, severity="Warning"):
        """Logs a society rule violation and creates an automated security inspection task."""
        flat = db.session.get(Flat, flat_id)
        flat_str = flat.flat_number if flat else str(flat_id)

        alert = AutomationAlert(
            society_id=society_id,
            alert_type="RULE_VIOLATION",
            severity="WARNING" if severity == "Warning" else "CRITICAL",
            title=f"Rule Violation: Flat {flat_str} ({violation_type})",
            message=f"Violation reported for Flat {flat_str}: {description}. Severity: {severity}.",
            is_resolved=False,
        )
        db.session.add(alert)

        # Create security inspection task
        wo = WorkOrder(
            work_order_number=f"WO-VIOL-{society_id}-{secrets.token_hex(2).upper()}",
            society_id=society_id,
            title=f"Inspect Rule Violation: Flat {flat_str}",
            description=f"Inspect and address {violation_type} violation at Flat {flat_str}: {description}",
            category="Security",
            priority="High" if severity != "Warning" else "Medium",
            status="Assigned",
            due_date=utcnow().date(),
        )
        db.session.add(wo)
        db.session.commit()
        return {"alert_id": alert.id, "work_order_id": wo.id, "flat_number": flat_str}
