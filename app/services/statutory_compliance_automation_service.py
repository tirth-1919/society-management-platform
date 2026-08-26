from app.models import (
    Resident,
    SocietyMeeting,
)
from app.utils import utcnow


class StatutoryComplianceAutomationService:
    """
    Implements Phase 27 Audit & Statutory Compliance Automation:
    - Member Register (Form I/J) statutory data compilation
    - AGM compliance deadline tracker
    - Society registration & bye-law audit status
    """

    @staticmethod
    def get_statutory_member_register(society_id):
        """Compiles statutory Form I/J Member Register data for society auditing."""
        residents = Resident.query.filter_by(society_id=society_id).order_by(Resident.created_at.asc()).all()
        register = []

        for idx, r in enumerate(residents, 1):
            register.append({
                "sr_no": idx,
                "member_name": r.full_name,
                "flat_number": r.flat.flat_number if r.flat else "-",
                "membership_type": r.resident_type,
                "admission_date": str(r.move_in_date or r.created_at.date() if r.created_at else "-"),
                "status": r.occupancy_status,
                "mobile": r.mobile,
            })

        return {
            "society_id": society_id,
            "total_registered_members": len(residents),
            "members": register,
            "generated_on": utcnow().strftime("%Y-%m-%d"),
        }

    @staticmethod
    def get_agm_compliance_status(society_id):
        """Checks if the society has conducted an Annual General Meeting within the mandated financial year."""
        current_year = utcnow().year
        agms = SocietyMeeting.query.filter_by(society_id=society_id).filter(
            (SocietyMeeting.title.ilike("%AGM%")) | (SocietyMeeting.title.ilike("%Annual General%"))
        ).all()

        has_conducted_this_year = any(m.meeting_date.year == current_year for m in agms)

        return {
            "society_id": society_id,
            "current_year": current_year,
            "agm_conducted": has_conducted_this_year,
            "compliance_status": "COMPLIANT" if has_conducted_this_year else "PENDING_AGM_MEETING",
            "past_agms_count": len(agms),
        }
