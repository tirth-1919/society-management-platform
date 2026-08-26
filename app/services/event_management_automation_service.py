from app.models import (
    db,
    Notice,
    ExpenseVoucher,
)


class EventManagementAutomationService:
    """
    Implements Phase 24 Society Event & Festival Management Automation:
    - Community festival & event circulars
    - Event budget vs actual expense tracking
    - Event notification broadcasts
    """

    @staticmethod
    def calculate_event_financials(society_id, event_keyword="Festival"):
        """Calculates total approved expenses for society cultural/festival events."""
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            (ExpenseVoucher.category.ilike(f"%{event_keyword}%")) |
            (ExpenseVoucher.description.ilike(f"%{event_keyword}%"))
        ).all()

        total_spent = sum(v.amount for v in vouchers)
        return {
            "society_id": society_id,
            "event_keyword": event_keyword,
            "total_vouchers_count": len(vouchers),
            "total_event_expenditure": round(total_spent, 2),
            "vouchers": [{"number": v.voucher_number, "payee": v.payee_name, "amount": v.amount, "desc": v.description} for v in vouchers],
        }

    @staticmethod
    def create_event_broadcast_notice(society_id, event_name, event_date, venue="Clubhouse", details=""):
        """Creates an official event notice for all society residents."""
        content = f"You are cordially invited to celebrate '{event_name}' on {event_date} at {venue}. {details}. We look forward to your presence!"
        notice = Notice(
            society_id=society_id,
            title=f"Event Invitation: {event_name}",
            content=content,
            notice_type="Meeting",
            priority="Normal",
            audience="All",
        )
        db.session.add(notice)
        db.session.commit()
        return notice
