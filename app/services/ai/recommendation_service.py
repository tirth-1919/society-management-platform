"""
AI Recommendation Architecture
==============================
Provides a standardized recommendation interface across all AI and automation modules.
Enforces safety rules: recommendations are advisory only and never mutate database records directly.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models import (
    User,
    Role,
    Resident,
    MaintenanceBill,
    Complaint,
    RegistrationRequest,
    Payment,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class AIRecommendationService:
    """
    Standard interface for generating prioritized, actionable recommendations.
    Output conforms to the unified structure:
    {
        "recommendations": [
            {
                "type": "...",
                "title": "...",
                "description": "...",
                "priority": "low|medium|high|critical",
                "confidence": 0.91,
                "action_url": "...",
                "requires_confirmation": True
            }
        ]
    }
    """

    @classmethod
    def get_recommendations(
        cls,
        user: Optional[User] = None,
        society_id: Optional[int] = None,
        context: Optional[str] = None,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Generates contextual recommendations for the authenticated user.
        Derives recommendations from real persisted data with strict tenant isolation.
        """
        recommendations: List[Dict[str, Any]] = []

        if not user:
            return {"recommendations": []}

        user_society_id = user.society_id or society_id
        if not user_society_id:
            return {"recommendations": []}

        if user.role == Role.RESIDENT:
            recommendations.extend(cls._get_resident_recommendations(user, user_society_id, context))
        elif user.role in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
            recommendations.extend(cls._get_admin_recommendations(user, user_society_id, context))

        # Sort recommendations by priority (critical -> high -> medium -> low) and confidence
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        recommendations.sort(
            key=lambda r: (priority_order.get(r.get("priority", "medium").lower(), 2), -r.get("confidence", 0.8))
        )

        return {"recommendations": recommendations}


    @classmethod
    def _get_resident_recommendations(
        cls, user: User, society_id: int, context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        resident = Resident.query.filter_by(user_id=user.id, society_id=society_id).first()
        if not resident:
            return recs

        now = utcnow().date()

        # 1. Unpaid / Overdue bills
        unpaid = MaintenanceBill.query.filter(
            MaintenanceBill.resident_id == resident.id,
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"]),
        ).order_by(MaintenanceBill.due_date.asc()).all()

        overdue = [b for b in unpaid if b.status == "Overdue" or (b.due_date and b.due_date < now)]
        if overdue:
            first_overdue = overdue[0]
            recs.append({
                "type": "settle_overdue_bill",
                "title": f"Overdue Maintenance: ₹{first_overdue.remaining_amount:,.2f}",
                "description": f"Bill for {first_overdue.billing_month} is past due date. Settle to avoid further late fees.",
                "priority": "critical",
                "confidence": 0.98,
                "action_url": f"/payments/pay/{first_overdue.id}",
                "requires_confirmation": True,
                "metadata": {"bill_id": first_overdue.id, "amount": first_overdue.remaining_amount},
            })
        elif unpaid:
            first_unpaid = unpaid[0]
            days_left = (first_unpaid.due_date - now).days if first_unpaid.due_date else 0
            recs.append({
                "type": "pay_upcoming_bill",
                "title": f"Upcoming Bill Due: ₹{first_unpaid.remaining_amount:,.2f}",
                "description": f"Maintenance due {first_unpaid.due_date.strftime('%d %b') if first_unpaid.due_date else 'soon'} ({days_left} days remaining).",
                "priority": "high" if days_left <= 3 else "medium",
                "confidence": 0.95,
                "action_url": f"/payments/pay/{first_unpaid.id}",
                "requires_confirmation": True,
                "metadata": {"bill_id": first_unpaid.id, "amount": first_unpaid.remaining_amount},
            })

        # 2. Incomplete profile check
        missing_fields = []
        if not resident.email:
            missing_fields.append("Email Address")
        if not resident.emergency_contacts:
            missing_fields.append("Emergency Contact")
        if missing_fields:
            recs.append({
                "type": "complete_profile",
                "title": "Complete your profile",
                "description": f"Missing: {', '.join(missing_fields)}. Keep details up to date for emergency alerts.",
                "priority": "medium",
                "confidence": 0.90,
                "action_url": "/resident/profile",
                "requires_confirmation": False,
                "metadata": {"missing": missing_fields},
            })

        # 3. Open complaint status check
        open_complaints = Complaint.query.filter(
            Complaint.resident_id == resident.id,
            Complaint.society_id == society_id,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        ).all()
        if open_complaints:
            recs.append({
                "type": "track_complaint",
                "title": f"{len(open_complaints)} active complaint ticket(s)",
                "description": f"Latest: '{open_complaints[0].title}' is currently {open_complaints[0].status}.",
                "priority": "low",
                "confidence": 0.88,
                "action_url": "/resident/complaints",
                "requires_confirmation": False,
                "metadata": {"count": len(open_complaints)},
            })

        return recs

    @classmethod
    def _get_admin_recommendations(
        cls, user: User, society_id: int, context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []

        # 1. Pending registration requests
        pending_regs = RegistrationRequest.query.filter_by(
            society_id=society_id, status="PENDING_APPROVAL"
        ).count()
        if pending_regs > 0:
            recs.append({
                "type": "approve_registrations",
                "title": f"{pending_regs} resident registration(s) pending approval",
                "description": "New residents are awaiting access to their society account and portals.",
                "priority": "high",
                "confidence": 0.99,
                "action_url": "/admin/registrations",
                "requires_confirmation": True,
                "metadata": {"pending_count": pending_regs},
            })

        # 2. Unverified cash payments
        unverified_cash = Payment.query.filter_by(
            society_id=society_id, payment_method="Cash", status="pending"
        ).count()
        if unverified_cash > 0:
            recs.append({
                "type": "verify_cash_payments",
                "title": f"{unverified_cash} cash payment(s) awaiting verification",
                "description": "Residents submitted cash collections awaiting admin reconciliation & receipt generation.",
                "priority": "high",
                "confidence": 0.97,
                "action_url": "/payments/admin_dashboard",
                "requires_confirmation": True,
                "metadata": {"unverified_count": unverified_cash},
            })

        # 3. Critical unresolved complaints
        urgent_complaints = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.priority.in_(["Emergency", "Critical", "High"]),
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        ).count()
        if urgent_complaints > 0:
            recs.append({
                "type": "review_urgent_complaints",
                "title": f"{urgent_complaints} urgent / emergency complaint(s) open",
                "description": "High-priority resident complaints require assignment or resolution follow-up.",
                "priority": "critical" if urgent_complaints > 2 else "high",
                "confidence": 0.95,
                "action_url": "/complaints/",
                "requires_confirmation": False,
                "metadata": {"urgent_count": urgent_complaints},
            })

        return recs
