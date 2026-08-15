from app.models import MaintenanceBill, Complaint, Notice, Resident
from app.services.accounting_service import AccountingService


class AIService:
    @staticmethod
    def answer_query(user, prompt):
        """
        Read-only AI Assistant NLP query processor.
        Analyzes natural language queries and responds using authoritative database stats.
        Strictly read-only: never modifies financial or resident records.
        """
        p = prompt.lower().strip()
        society_id = user.society_id if user else None

        # Resident Dues query
        if any(w in p for w in ["pending", "due", "bill", "maintenance", "how much"]):
            if user and user.role == "Resident":
                resident = Resident.query.filter_by(user_id=user.id).first()
                if resident:
                    bills = MaintenanceBill.query.filter(
                        MaintenanceBill.society_id == user.society_id,
                        MaintenanceBill.resident_id == resident.id,
                        MaintenanceBill.status.in_(
                            ["Pending", "Overdue", "Partially Paid"]
                        ),
                    ).all()
                    summary = {
                        "pending_bills_count": len(bills),
                        "total_remaining_due": sum(b.remaining_amount for b in bills),
                        "total_base_amount": sum(b.base_amount for b in bills),
                        "total_late_fees": sum(b.late_fee for b in bills),
                    }
                    return f"Hello {resident.full_name}, your flat has {summary['pending_bills_count']} pending bill(s). Total remaining due: ₹{summary['total_remaining_due']:,.2f} (Base: ₹{summary['total_base_amount']:,.2f}, Late Fees: ₹{summary['total_late_fees']:,.2f})."

            # Admin summary query
            if society_id:
                bills = (
                    MaintenanceBill.query.filter_by(society_id=society_id)
                    .filter(
                        MaintenanceBill.status.in_(
                            ["Pending", "Overdue", "Partially Paid"]
                        )
                    )
                    .all()
                )
                total_pending = sum(b.remaining_amount for b in bills)
                return f"Society Overdue Summary: There are currently {len(bills)} overdue maintenance bill(s) totaling ₹{total_pending:,.2f} pending collection."

        # Complaints status query
        if any(w in p for w in ["complaint", "ticket", "issue", "repair"]):
            if society_id:
                open_complaints = (
                    Complaint.query.filter_by(society_id=society_id)
                    .filter(
                        Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
                    )
                    .all()
                )
                return f"Complaint Status Summary: There are {len(open_complaints)} active unresolved complaint ticket(s) currently being processed by maintenance staff."

        # Expenses / Financial Collection query
        if any(
            w in p for w in ["expense", "collection", "financial", "summary", "surplus"]
        ):
            if society_id:
                fin = AccountingService.get_financial_summary(society_id)
                return f"Financial Performance: Total Collected Income: ₹{fin['total_income']:,.2f} | Total Approved Expenses: ₹{fin['total_expense']:,.2f} | Net Surplus: ₹{fin['net_surplus']:,.2f}."

        # Notices query
        if any(w in p for w in ["notice", "announcement", "meeting"]):
            if society_id:
                notices = (
                    Notice.query.filter_by(society_id=society_id)
                    .order_by(Notice.publish_date.desc())
                    .limit(3)
                    .all()
                )
                if notices:
                    titles = "; ".join(
                        [f"'{n.title}' ({n.notice_type})" for n in notices]
                    )
                    return f"Recent Society Notices: {titles}."
                return "No active notices posted recently."

        # Default helpful assistant response
        return "I am your AI Society Assistant. You can ask me questions like: 'How much maintenance is pending?', 'Show my complaint status', or 'Give me this month's collection summary'."

