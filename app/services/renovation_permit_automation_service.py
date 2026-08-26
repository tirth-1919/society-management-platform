from app.models import (
    db,
    Flat,
    WorkOrder,
)
from app.utils import utcnow
from datetime import date, timedelta
import secrets


class RenovationPermitAutomationService:
    """
    Implements Phase 36 Renovation & Interior Work Permit Automation:
    - Renovation work permit approval and security gate clearance
    - Permissible noise hours enforcement (9 AM – 6 PM Mon–Sat)
    - Debris deposit clearance inspection task
    """

    @staticmethod
    def issue_renovation_permit(society_id, flat_id, contractor_name, start_date, end_date, scope_of_work=""):
        """Issues an official renovation work permit with standard society noise rules."""
        flat = db.session.get(Flat, flat_id)
        flat_str = flat.flat_number if flat else str(flat_id)
        permit_number = f"PERMIT-REN-{society_id}-{secrets.token_hex(2).upper()}"

        # Create inspection task for security/facility manager
        wo = WorkOrder(
            work_order_number=f"WO-REN-{society_id}-{secrets.token_hex(2).upper()}",
            society_id=society_id,
            title=f"Renovation Permit Issued: Flat {flat_str}",
            description=f"Permit #{permit_number}: Contractor {contractor_name} authorized for renovation from {start_date} to {end_date}. Enforce 9 AM - 6 PM working hours only.",
            category="Security",
            priority="Medium",
            status="Assigned",
            due_date=end_date if isinstance(end_date, date) else utcnow().date() + timedelta(days=14),
        )
        db.session.add(wo)
        db.session.commit()

        return {
            "permit_number": permit_number,
            "flat_id": flat_id,
            "flat_number": flat_str,
            "contractor_name": contractor_name,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "work_hours": "09:00 AM – 06:00 PM (Monday to Saturday only, no noisy work on Sundays/Holidays)",
            "work_order_id": wo.id,
        }
