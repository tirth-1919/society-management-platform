"""
Resident Experience AI Services
===============================
Provides Smart Resident Status Engine and Resident Next-Step Engine.
Strictly read-only derivation of existing resident and account data.
Does not change financial, billing, or payment rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List


from app.models import (
    db,
    Resident,
    MaintenanceBill,
    Payment,
    Complaint,
    Notice,
    Vehicle,
    EmergencyContact,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class SmartResidentStatusService:
    """
    Evaluates the overall health and status of a resident's society account.
    Returns one of four authoritative statuses:
    - 'Everything OK'
    - 'Action Needed'
    - 'Pending'
    - 'Important Update'
    """

    @classmethod
    def get_status(cls, resident_id: int, society_id: int) -> Dict[str, Any]:
        resident = db.session.get(Resident, resident_id)
        if not resident or resident.society_id != society_id:
            return {
                "status": "Unknown",
                "badge_class": "badge-secondary",
                "summary": "Resident profile not found.",
                "details": [],
            }

        now = utcnow().date()

        # 1. Check bills & dues
        unpaid_bills = MaintenanceBill.query.filter(
            MaintenanceBill.resident_id == resident.id,
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"]),
        ).all()

        overdue_bills = [b for b in unpaid_bills if b.status == "Overdue" or (b.due_date and b.due_date < now)]
        total_outstanding = sum(b.remaining_amount for b in unpaid_bills)

        # 2. Check pending verifications
        pending_cash = Payment.query.filter(
            Payment.resident_id == resident.id,
            Payment.society_id == society_id,
            Payment.status == "pending",
        ).all()

        # 3. Check active urgent complaints
        open_complaints = Complaint.query.filter(
            Complaint.resident_id == resident.id,
            Complaint.society_id == society_id,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        ).all()

        # 4. Check recent important announcements (last 7 days)
        recent_important_notices = Notice.query.filter(
            Notice.society_id == society_id,
            Notice.notice_type.in_(["Emergency", "Urgent", "Meeting", "AGM"]),
        ).order_by(Notice.created_at.desc()).limit(3).all()

        # Evaluation hierarchy
        status = "Everything OK"
        badge_class = "badge-success"
        summary = "Your account is in good standing. All accounts are settled."
        details = []

        if overdue_bills:
            status = "Action Needed"
            badge_class = "badge-danger"
            summary = f"You have {len(overdue_bills)} overdue bill(s) totaling ₹{sum(b.remaining_amount for b in overdue_bills):,.2f}."
            details.append("Settle overdue maintenance to prevent late fees.")
        elif unpaid_bills:
            status = "Action Needed"
            badge_class = "badge-warning"
            summary = f"Maintenance bill of ₹{total_outstanding:,.2f} is due."
            details.append("Payment due before the specified due date.")
        elif pending_cash:
            status = "Pending"
            badge_class = "badge-info"
            summary = f"{len(pending_cash)} offline / cash payment(s) awaiting Admin verification."
            details.append("Admin will reconcile your cash receipt shortly.")
        elif recent_important_notices:
            status = "Important Update"
            badge_class = "badge-primary"
            summary = f"New society update: '{recent_important_notices[0].title}'"
            details.append("Read recent announcements from the managing committee.")

        return {
            "status": status,
            "badge_class": badge_class,
            "summary": summary,
            "details": details,
            "total_outstanding": round(total_outstanding, 2),
            "unpaid_bills_count": len(unpaid_bills),
            "overdue_bills_count": len(overdue_bills),
            "pending_payments_count": len(pending_cash),
            "open_complaints_count": len(open_complaints),
        }


class ResidentNextActionService:
    """
    Resident Next-Step Engine:
    Analyzes current resident state and returns structured next actions:
    {
        "action": "complete_profile",
        "title": "Complete your profile",
        "priority": "medium",
        "reason": "Some optional profile information is incomplete",
        "url": "/resident/profile"
    }
    """

    @classmethod
    def get_next_actions(cls, resident_id: int, society_id: int) -> List[Dict[str, Any]]:
        resident = db.session.get(Resident, resident_id)
        if not resident or resident.society_id != society_id:
            return []

        actions: List[Dict[str, Any]] = []
        now = utcnow().date()

        # 1. Overdue / Pending Bills
        unpaid_bills = MaintenanceBill.query.filter(
            MaintenanceBill.resident_id == resident.id,
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"]),
        ).order_by(MaintenanceBill.due_date.asc()).all()

        overdue = [b for b in unpaid_bills if b.status == "Overdue" or (b.due_date and b.due_date < now)]
        if overdue:
            first_b = overdue[0]
            actions.append({
                "action": "pay_overdue_bill",
                "title": f"Pay overdue bill for {first_b.billing_month}",
                "priority": "critical",
                "reason": f"Bill is overdue with outstanding amount of ₹{first_b.remaining_amount:,.2f}.",
                "url": f"/payments/pay/{first_b.id}",
                "icon": "fa-circle-exclamation",
                "btn_text": "Pay Now",
            })
        elif unpaid_bills:
            first_b = unpaid_bills[0]
            days_left = (first_b.due_date - now).days if first_b.due_date else 0
            actions.append({
                "action": "pay_upcoming_bill",
                "title": f"Settle maintenance for {first_b.billing_month}",
                "priority": "high" if days_left <= 3 else "medium",
                "reason": f"Maintenance of ₹{first_b.remaining_amount:,.2f} is due in {days_left} day(s).",
                "url": f"/payments/pay/{first_b.id}",
                "icon": "fa-file-invoice-dollar",
                "btn_text": "Pay Bill",
            })

        # 2. Check for recent successful payment with receipt available
        recent_payment = Payment.query.filter(
            Payment.resident_id == resident.id,
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success"]),
        ).order_by(Payment.payment_date.desc()).first()

        if recent_payment and recent_payment.payment_date:
            days_since = (utcnow().date() - recent_payment.payment_date.date()).days
            if days_since <= 7:
                actions.append({
                    "action": "review_receipt",
                    "title": "Review latest payment receipt",
                    "priority": "low",
                    "reason": f"Official receipt for ₹{recent_payment.amount_paid:,.2f} is available to download.",
                    "url": "/resident/receipts",
                    "icon": "fa-receipt",
                    "btn_text": "View Receipts",
                })

        # 3. Complete Profile Details
        missing_items = []
        if not resident.email:
            missing_items.append("Email Address")
        if not EmergencyContact.query.filter_by(resident_id=resident.id).first():
            missing_items.append("Emergency Contact")
        if not Vehicle.query.filter_by(flat_id=resident.flat_id).first():
            missing_items.append("Vehicle Details")

        if missing_items:
            actions.append({
                "action": "complete_profile",
                "title": "Complete your profile",
                "priority": "medium",
                "reason": f"Some optional profile information is incomplete: {', '.join(missing_items)}.",
                "url": "/resident/profile",
                "icon": "fa-user-pen",
                "btn_text": "Update Profile",
            })

        # 4. Open Complaints Status
        active_complaint = Complaint.query.filter(
            Complaint.resident_id == resident.id,
            Complaint.society_id == society_id,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        ).order_by(Complaint.created_at.desc()).first()

        if active_complaint:
            actions.append({
                "action": "check_pending_item",
                "title": f"Check status of ticket #{active_complaint.id}",
                "priority": "low",
                "reason": f"Complaint '{active_complaint.title}' is currently '{active_complaint.status}'.",
                "url": "/resident/complaints",
                "icon": "fa-headset",
                "btn_text": "Track Ticket",
            })

        # 5. Read Recent Important Notice
        important_notice = Notice.query.filter(
            Notice.society_id == society_id,
            Notice.notice_type.in_(["Emergency", "Urgent", "Meeting", "AGM"]),
        ).order_by(Notice.created_at.desc()).first()

        if important_notice:
            actions.append({
                "action": "read_important_notice",
                "title": f"Read important notice: {important_notice.title}",
                "priority": "medium",
                "reason": f"Managing committee published a {important_notice.notice_type} notice.",
                "url": "/resident/announcements",
                "icon": "fa-bullhorn",
                "btn_text": "View Notice",
            })

        # Sort actions by priority (critical -> high -> medium -> low)
        order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        actions.sort(key=lambda a: order.get(a.get("priority", "medium"), 2))

        return actions
