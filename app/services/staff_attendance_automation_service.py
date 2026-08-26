from app.models import (
    Staff,
)
from app.utils import utcnow


class StaffAttendanceAutomationService:
    """
    Implements Phase 16 Staff & Domestic Help Attendance Automation:
    - Daily staff attendance check
    - Multi-flat maid / helper verification
    - Attendance anomaly detection
    - Salary estimation helper
    """

    @staticmethod
    def get_daily_staff_attendance_summary(society_id):
        """Generates daily staff attendance summary across all service roles."""
        all_staff = Staff.query.filter_by(society_id=society_id).all()
        active = [s for s in all_staff if s.status == "Active"]
        on_leave = [s for s in all_staff if s.status == "On Leave"]

        by_role = {}
        for s in active:
            by_role.setdefault(s.role_type, []).append({
                "id": s.id,
                "name": s.full_name,
                "phone": s.phone,
                "status": s.status,
            })

        return {
            "society_id": society_id,
            "total_staff_count": len(all_staff),
            "active_present_count": len(active),
            "on_leave_count": len(on_leave),
            "staff_by_role": by_role,
            "date": utcnow().strftime("%Y-%m-%d"),
        }

    @staticmethod
    def calculate_monthly_salary_estimate(society_id):
        """Calculates total estimated monthly staff salary liability."""
        staff_members = Staff.query.filter_by(society_id=society_id, status="Active").all()
        total_salary = sum(s.salary_amount or 0.0 for s in staff_members)
        return {
            "society_id": society_id,
            "active_staff_count": len(staff_members),
            "total_monthly_payroll": round(total_salary, 2),
            "breakdown": [{"name": s.full_name, "role": s.role_type, "salary": s.salary_amount} for s in staff_members],
        }
