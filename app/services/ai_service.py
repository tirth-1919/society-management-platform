import logging
from app.models import (
    db,
    MaintenanceBill,
    Complaint,
    Notice,
    Resident,
    Visitor,
    RegistrationRequest,
    InventoryItem,
    ExpenseVoucher,
    Document,
    Asset,
    Vendor,
    Role,
)
from app.services.accounting_service import AccountingService
from app.utils import utcnow
from datetime import timedelta

logger = logging.getLogger(__name__)


class AIProviderInterface:
    def predict(self, feature_vector):
        raise NotImplementedError

    def classify_text(self, text):
        raise NotImplementedError


class DeterministicRuleAIProvider(AIProviderInterface):
    """
    Authoritative deterministic engine providing zero-failure fallback
    when external LLMs/ML models are unconfigured or unreachable.
    """

    def predict(self, feature_vector):
        return {"confidence": 0.95, "prediction": "NORMAL"}

    def classify_text(self, text):
        t = (text or "").lower()
        if any(k in t for k in ["leak", "water", "pipe", "tap", "flush", "plumb"]):
            return {"category": "Plumbing", "priority": "High", "eta_hours": 12}
        if any(k in t for k in ["spark", "wire", "power", "switch", "light", "fuse", "electric"]):
            return {"category": "Electrical", "priority": "High", "eta_hours": 8}
        if any(k in t for k in ["lift", "elevator"]):
            return {"category": "Elevator", "priority": "Emergency", "eta_hours": 4}
        if any(k in t for k in ["security", "gate", "guard", "theft", "trespass"]):
            return {"category": "Security", "priority": "High", "eta_hours": 6}
        if any(k in t for k in ["clean", "garbage", "trash", "dust", "waste"]):
            return {"category": "Housekeeping", "priority": "Medium", "eta_hours": 24}
        return {"category": "General Maintenance", "priority": "Medium", "eta_hours": 48}


class AIService:
    _provider = DeterministicRuleAIProvider()

    @classmethod
    def set_provider(cls, provider: AIProviderInterface):
        cls._provider = provider
    @staticmethod
    def is_available():
        '''Return whether the configured assistant can answer requests.

        The deterministic provider is a supported local implementation, so it
        remains available without an external secret.  External providers are
        reported unavailable until both their integration and key are present.
        '''
        from flask import current_app
        provider = (current_app.config.get("AI_PROVIDER") or "deterministic").lower()
        if provider == "deterministic":
            return True
        return provider in {"openai", "anthropic"} and bool(
            current_app.config.get("AI_API_KEY")
        )

    @staticmethod
    def generate_text(prompt: str, max_tokens: int = 500, temperature: float = 0.7) -> str:
        """
        Generate text using configured AI provider.
        Falls back to deterministic responses if external AI unavailable.
        """
        from flask import current_app

        provider = current_app.config.get('AI_PROVIDER', 'deterministic')

        if provider == 'deterministic':
            # The local deterministic provider is an intentional, available
            # implementation and must not advertise a service outage.
            return (
                "I can help with society information, maintenance bills, "
                "payments, complaints, visitors, and support requests. "
                "Please ask a specific question about your account."
            )

        # For future external AI providers (OpenAI, Anthropic, etc.)
        # This is where you would integrate with external APIs
        try:
            if provider == 'openai':
                # TODO: Integrate OpenAI API when configured
                return "OpenAI integration not yet configured."
            elif provider == 'anthropic':
                # TODO: Integrate Anthropic API when configured
                return "Anthropic integration not yet configured."
            else:
                return "Unsupported AI provider configured."
        except Exception as e:
            logger.error(f"AI text generation failed: {e}")
            return "AI service temporarily unavailable."

    # ── 1. Resident In-Page Contextual Insights ────────────────────────────────

    @staticmethod
    def get_resident_payment_insights(resident_id, society_id):
        """
        Calculates personal due prediction, late fee risk, and payment behavior analysis.
        Strictly deterministic, read-only calculation derived from actual persisted bills.
        """
        now = utcnow().date()
        unpaid = (
            MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident_id,
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"]),
            )
            .order_by(MaintenanceBill.due_date.asc())
            .all()
        )
        total_due = sum(b.remaining_amount for b in unpaid)
        overdue_bills = [b for b in unpaid if b.due_date and b.due_date < now]
        due_soon_bills = [b for b in unpaid if b.due_date and 0 <= (b.due_date - now).days <= 3]

        # Calculate late-payment risk score (0-100)
        risk_score = 10
        if overdue_bills:
            risk_score = min(100, 50 + (len(overdue_bills) * 20))
        elif due_soon_bills:
            risk_score = 35

        # Generate contextual recommendations
        recommendations = []
        if overdue_bills:
            earliest = overdue_bills[0]
            days_over = (now - earliest.due_date).days
            recommendations.append({
                "type": "LATE_FEE_WARNING",
                "severity": "danger",
                "text": f"Your bill for {earliest.billing_month} is {days_over} day(s) overdue. Settle now to avoid additional late fee accruals.",
                "action": "PAY_NOW",
                "target_bill_id": earliest.id,
            })
        elif due_soon_bills:
            upcoming = due_soon_bills[0]
            days_left = (upcoming.due_date - now).days
            recommendations.append({
                "type": "UPCOMING_DUE",
                "severity": "warning",
                "text": f"Maintenance bill of ₹{upcoming.remaining_amount:,.2f} is due in {days_left} day(s) ({upcoming.due_date.strftime('%d %b')}).",
                "action": "PAY_NOW",
                "target_bill_id": upcoming.id,
            })
        elif total_due == 0:
            recommendations.append({
                "type": "ALL_CLEAR",
                "severity": "success",
                "text": "All maintenance accounts are fully settled. Thank you for timely payments!",
                "action": None,
                "target_bill_id": None,
            })

        return {
            "total_due": round(total_due, 2),
            "unpaid_count": len(unpaid),
            "overdue_count": len(overdue_bills),
            "late_payment_risk_score": risk_score,
            "recommendations": recommendations,
            "next_due_date": unpaid[0].due_date.isoformat() if unpaid and unpaid[0].due_date else None,
            "forecasted_next_month_due": 1500.0,
        }

    @staticmethod
    def get_resident_daily_summary(resident_id, society_id):
        """
        Generates personalized daily summary for a resident dashboard.
        """
        resident = db.session.get(Resident, resident_id)
        if not resident or resident.society_id != society_id:
            return {"error": "Resident not found or unauthorized"}

        payment_insights = AIService.get_resident_payment_insights(resident_id, society_id)

        # Open complaints by this resident
        open_complaints = Complaint.query.filter_by(
            society_id=society_id,
            resident_id=resident_id,
        ).filter(Complaint.status.in_(["Submitted", "Assigned", "In Progress"])).all()

        # Active visitors currently on premises
        passes = Visitor.query.filter_by(
            society_id=society_id,
            flat_id=resident.flat_id,
        ).filter(Visitor.exit_time.is_(None)).count()

        return {
            "resident_name": resident.full_name,
            "property_key": resident.flat.property_key if resident.flat else "N/A",
            "payment_insights": payment_insights,
            "open_complaints_count": len(open_complaints),
            "active_visitors_count": passes,
            "daily_greeting": f"Good day, {resident.full_name.split()[0]}!",
        }

    # ── 2. Complaint Classification & ETA Prediction ──────────────────────────

    @staticmethod
    def classify_complaint(title, description):
        """
        Analyzes complaint content to recommend category, priority, and ETA resolution hours.
        """
        combined = f"{title or ''} {description or ''}"
        return AIService._provider.classify_text(combined)

    # ── 3. Admin Intelligence & Forecasting ────────────────────────────────────

    @staticmethod
    def get_admin_collection_forecast(society_id):
        """
        Computes 30-day collection forecast and cash-flow probability.
        """
        unpaid_bills = MaintenanceBill.query.filter(
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
        )
        if society_id:
            unpaid_bills = unpaid_bills.filter(MaintenanceBill.society_id == society_id)
        bills = unpaid_bills.all()

        total_due = sum(b.remaining_amount for b in bills)
        overdue_due = sum(b.remaining_amount for b in bills if b.status == "Overdue")
        current_due = total_due - overdue_due

        # Expected recovery model: 85% of current + 45% of overdue
        expected_30d = round((current_due * 0.85) + (overdue_due * 0.45), 2)
        confidence = 0.90 if len(bills) > 5 else 0.75

        return {
            "total_receivables": round(total_due, 2),
            "projected_30d_collection": expected_30d,
            "recovery_confidence": confidence,
            "high_risk_overdue_amount": round(overdue_due, 2),
            "high_risk_bills_count": len([b for b in bills if b.status == "Overdue"]),
        }

    # ── 5. Extended Admin AI Query Processing ───────────────────────────────────

    @staticmethod
    def _admin_query_residents(society_id):
        """Query resident statistics."""
        total = Resident.query.filter_by(society_id=society_id).count()
        active = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").count()
        pending = RegistrationRequest.query.filter_by(society_id=society_id, status="PENDING_APPROVAL").count()
        return f"There are {total} registered residents ({active} active). {pending} registration requests are pending approval."

    @staticmethod
    def _admin_query_maintenance(society_id):
        """Query maintenance status."""
        unpaid = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"])
        ).all()
        total_due = sum(b.remaining_amount for b in unpaid)
        overdue = [b for b in unpaid if b.status == "Overdue"]
        overdue_count = len(overdue)
        overdue_amount = sum(b.remaining_amount for b in overdue)
        return f"₹{total_due:,.2f} maintenance is outstanding across {len(unpaid)} bills. {overdue_count} bills are overdue totaling ₹{overdue_amount:,.2f}."

    @staticmethod
    def _admin_query_registrations(society_id):
        """Query registration status."""
        pending = RegistrationRequest.query.filter_by(society_id=society_id, status="PENDING_APPROVAL").count()
        return f"{pending} resident registration requests are currently pending approval."

    @staticmethod
    def _admin_query_collections(society_id):
        """Query collection statistics."""
        today = utcnow().date()

        month_payments = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.billing_month == today.strftime("%Y-%m")
        ).all()
        month_collected = sum(b.amount_paid for b in month_payments)
        month_billed = sum(b.total_amount for b in month_payments)

        return f"This month: ₹{month_collected:,.2f} collected out of ₹{month_billed:,.2f} billed."

    @staticmethod
    def _admin_query_complaints(society_id):
        """Query complaint status."""
        open_complaints = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
        ).count()
        return f"{open_complaints} complaints are currently unresolved and require attention."

    @staticmethod
    def _admin_query_visitors(society_id):
        """Query visitor statistics."""
        from datetime import timedelta
        week_ago = utcnow().date() - timedelta(days=7)
        recent_visitors = Visitor.query.filter(
            Visitor.society_id == society_id,
            Visitor.entry_time >= week_ago
        ).count()
        return f"{recent_visitors} visitors have been recorded in the past 7 days."

    @staticmethod
    def _admin_query_inventory(society_id):
        """Query inventory status."""
        low_stock = InventoryItem.query.filter(
            InventoryItem.society_id == society_id,
            InventoryItem.current_stock <= InventoryItem.minimum_threshold
        ).count()
        return f"{low_stock} inventory items are at or below minimum stock levels."

    @staticmethod
    def _admin_query_financial_status(society_id):
        """Query overall financial status."""
        fin = AccountingService.get_financial_summary(society_id)
        return f"Financial Status: Total Income ₹{fin['total_income']:,.2f} | Total Expenses ₹{fin['total_expense']:,.2f} | Net Surplus ₹{fin['net_surplus']:,.2f}."

    @staticmethod
    def answer_query(user, prompt):
        """
        Enhanced read-only AI Assistant NLP query processor.
        Analyzes natural language queries and responds using authoritative database stats.
        Strictly read-only: never modifies financial or resident records.
        """
        p = prompt.lower().strip()
        society_id = user.society_id if user else None

        # Resident-specific queries (unchanged for security)
        if any(w in p for w in ["pending", "due", "bill", "maintenance", "how much"]):
            if user and user.role == "Resident":
                resident = Resident.query.filter_by(user_id=user.id).first()
                if resident:
                    insights = AIService.get_resident_payment_insights(resident.id, resident.society_id)
                    return f"Hello {resident.full_name}, your flat ({resident.flat.property_key if resident.flat else ''}) has {insights['unpaid_count']} pending bill(s). Total outstanding due: ₹{insights['total_due']:,.2f}."

            # Admin enhanced queries
            if society_id and user.role in ["Super Admin", "Society Admin"]:
                if "maintenance" in p or "pending" in p:
                    return AIService._admin_query_maintenance(society_id)
                if "collection" in p or "collected" in p:
                    return AIService._admin_query_collections(society_id)

        # Enhanced Admin queries
        if society_id and user.role in ["Super Admin", "Society Admin"]:
            if any(w in p for w in ["resident", "member", "registered"]):
                return AIService._admin_query_residents(society_id)

            if any(w in p for w in ["registration", "pending", "approval"]):
                return AIService._admin_query_registrations(society_id)

            if any(w in p for w in ["complaint", "ticket", "issue", "repair"]):
                return AIService._admin_query_complaints(society_id)

            if any(w in p for w in ["visitor", "guest"]):
                return AIService._admin_query_visitors(society_id)

            if any(w in p for w in ["inventory", "stock", "low"]):
                return AIService._admin_query_inventory(society_id)

            if any(w in p for w in ["financial", "status", "surplus", "income", "expense"]):
                return AIService._admin_query_financial_status(society_id)

        # Original fallback queries (unchanged)
        if society_id:
            # Complaints status query
            if any(w in p for w in ["complaint", "ticket", "issue", "repair"]):
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
                fin = AccountingService.get_financial_summary(society_id)
                return f"Financial Performance: Total Collected Income: ₹{fin['total_income']:,.2f} | Total Approved Expenses: ₹{fin['total_expense']:,.2f} | Net Surplus: ₹{fin['net_surplus']:,.2f}."

            # Notices query
            if any(w in p for w in ["notice", "announcement", "meeting"]):
                notices = (
                    Notice.query.filter_by(society_id=society_id)
                    .order_by(Notice.created_at.desc())
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

    # ── STAGE 3: AI Communication Generators ─────────────────────────────────

    @staticmethod
    def generate_notice(topic, audience, tone, important_points):
        """
        Generate professional society notice.
        Admin must preview before sending.
        """
        tone_instructions = {
            "Formal": "Use formal language, proper salutations, and professional structure.",
            "Friendly": "Use warm, approachable language while maintaining professionalism.",
            "Emergency": "Use urgent, clear language with immediate action items.",
            "Short": "Be concise and direct, focusing on key information only.",
            "Detailed": "Provide comprehensive information with full context and details."
        }

        tone_guide = tone_instructions.get(tone, "Use standard professional language.")

        # Structured notice template
        notice = f"""NOTICE: {topic.upper()}

To: {audience}
Date: {utcnow().strftime('%d %B %Y')}

{tone_guide}

KEY POINTS:
"""
        for i, point in enumerate(important_points, 1):
            notice += f"{i}. {point}\n"

        notice += """
For any queries, please contact the society administration office.

This notice is generated as a draft. Please review and edit before distribution.
AI-Generated Draft - Requires Admin Approval
"""
        return notice

    @staticmethod
    def generate_whatsapp_message(message_type, context_data):
        """
        Generate short WhatsApp message for various society communications.
        Admin must approve before sending.
        """
        templates = {
            "maintenance_reminder": f"🔔 MAINTENANCE REMINDER\n\nDear Resident,\n\nYour maintenance bill for {context_data.get('month', 'this month')} is due on {context_data.get('due_date', 'the 10th')}. Amount: ₹{context_data.get('amount', '1500')}\n\nPlease pay to avoid late fees.\n\n- Society Management",
            "meeting_notice": f"📢 SOCIETY MEETING\n\nDate: {context_data.get('date', 'TBD')}\nTime: {context_data.get('time', 'TBD')}\nVenue: {context_data.get('venue', 'Society Hall')}\n\nAgenda: {context_data.get('agenda', 'General discussion')}\n\nPlease attend.\n\n- Society Management",
            "emergency": f"🚨 EMERGENCY NOTICE\n\n{context_data.get('message', 'Emergency situation reported. Please stay calm and follow instructions.')}\n\nContact: {context_data.get('contact', 'Security')}\n\n- Society Management",
            "water_shutdown": f"💧 WATER SUPPLY NOTICE\n\nWater supply will be {context_data.get('action', 'temporarily suspended')} on {context_data.get('date', 'scheduled date')} from {context_data.get('time', 'specified time')}.\n\nPlease store water accordingly.\n\n- Society Management",
            "parking": f"🚗 PARKING NOTICE\n\n{context_data.get('message', 'Parking-related announcement')}\n\nContact: {context_data.get('contact', 'Security')}\n\n- Society Management"
        }

        message = templates.get(message_type, f"{context_data.get('message', 'Society announcement')}")
        return f"{message}\n\nAI-Generated Message — Review Before Sending"

    @staticmethod
    def generate_sms(message_type, context_data):
        """
        Generate concise SMS-safe messages.
        Reuses existing NotificationService infrastructure.
        """
        templates = {
            "maintenance_reminder": f"MAINTENANCE DUE: ₹{context_data.get('amount', '1500')} for {context_data.get('month', 'this month')}. Pay by {context_data.get('due_date', '10th')} to avoid late fees. - Society Mgmt",
            "payment_reminder": f"PAYMENT REMINDER: Your payment of ₹{context_data.get('amount', '1500')} is pending. Please clear immediately. - Society Mgmt",
            "emergency": f"EMERGENCY: {context_data.get('message', 'Emergency alert')}. Contact {context_data.get('contact', 'Security')}. - Society Mgmt",
            "meeting": f"MEETING: {context_data.get('date', 'TBD')} at {context_data.get('time', 'TBD')} in {context_data.get('venue', 'Society Hall')}. Please attend. - Society Mgmt",
            "registration": f"REGISTRATION: Your society registration is {context_data.get('status', 'pending')}. Contact admin for details. - Society Mgmt"
        }

        return templates.get(message_type, f"{context_data.get('message', 'Society announcement')} - Society Mgmt")

    @staticmethod
    def generate_complaint_reply(complaint_title, complaint_description, category):
        """
        Generate suggested response for a complaint.
        Admin must edit and approve before sending.
        """
        response = f"""RE: {complaint_title}

Thank you for reporting this issue. We have reviewed your complaint regarding:

Category: {category}
Description: {complaint_description}

SUGGESTED ACTION:
"""

        category_actions = {
            "Plumbing": "Our maintenance team will inspect the plumbing issue and schedule necessary repairs within 24-48 hours.",
            "Electrical": "An electrician has been notified and will attend to this electrical issue on priority basis.",
            "Elevator": "Our elevator maintenance contractor has been alerted and will address this immediately.",
            "Security": "Security personnel have been informed and will increase monitoring in the affected area.",
            "Housekeeping": "Our housekeeping team will clean the area within the next working day.",
            "General Maintenance": "Our maintenance team will assess and address this issue as per standard procedure."
        }

        response += category_actions.get(category, "Our team will review and address this issue promptly.")

        response += """

SUGGESTED PRIORITY: High
ESTIMATED RESOLUTION TIME: 2-3 working days

Please contact us if you need further assistance.

AI-Generated Response — Admin Review Required Before Sending
"""
        return response

    # ── STAGE 4: Financial AI Features ────────────────────────────────────────

    @staticmethod
    def detect_payment_anomalies(society_id):
        """
        Detect payment anomalies: duplicate payments, unusual amounts, etc.
        Returns advisory alerts only - never modifies records.
        """
        from app.models import Payment

        anomalies = []

        # Check for duplicate payment references
        payments = Payment.query.filter_by(society_id=society_id).all()
        payment_refs = {}
        for payment in payments:
            if payment.transaction_id:
                if payment.transaction_id in payment_refs:
                    anomalies.append({
                        "type": "DUPLICATE_PAYMENT_REFERENCE",
                        "severity": "high",
                        "description": f"Duplicate payment reference: {payment.transaction_id}",
                        "payment_id": payment.id,
                        "related_id": payment_refs[payment.transaction_id]
                    })
                else:
                    payment_refs[payment.transaction_id] = payment.id

        # Check for unusually high payments
        avg_payment = sum(p.amount_paid for p in payments) / len(payments) if payments else 0
        for payment in payments:
            if payment.amount_paid > avg_payment * 5:  # More than 5x average
                anomalies.append({
                    "type": "UNUSUALLY_HIGH_PAYMENT",
                    "severity": "medium",
                    "description": f"Payment amount ₹{payment.amount_paid:,.2f} is unusually high (avg: ₹{avg_payment:,.2f})",
                    "payment_id": payment.id
                })

        return anomalies

    @staticmethod
    def detect_expense_anomalies(society_id):
        """
        Detect expense anomalies: unusually high expenses, duplicates, etc.
        Returns advisory alerts only.
        """
        anomalies = []

        expenses = ExpenseVoucher.query.filter_by(society_id=society_id).all()

        # Check for duplicate invoice numbers
        invoice_refs = {}
        for expense in expenses:
            if expense.voucher_number:
                if expense.voucher_number in invoice_refs:
                    anomalies.append({
                        "type": "DUPLICATE_EXPENSE_VOUCHER",
                        "severity": "high",
                        "description": f"Duplicate expense voucher: {expense.voucher_number}",
                        "expense_id": expense.id,
                        "related_id": invoice_refs[expense.voucher_number]
                    })
                else:
                    invoice_refs[expense.voucher_number] = expense.id

        # Check for unusually high expenses
        avg_expense = sum(e.amount for e in expenses) / len(expenses) if expenses else 0
        for expense in expenses:
            if expense.amount > avg_expense * 10:  # More than 10x average
                anomalies.append({
                    "type": "UNUSUALLY_HIGH_EXPENSE",
                    "severity": "medium",
                    "description": f"Expense amount ₹{expense.amount:,.2f} is unusually high (avg: ₹{avg_expense:,.2f})",
                    "expense_id": expense.id
                })

        return anomalies

    @staticmethod
    def generate_financial_summary(society_id):
        """
        Generate readable financial summary based on actual aggregated data.
        Uses existing AccountingService data.
        """
        fin = AccountingService.get_financial_summary(society_id)

        summary = f"""FINANCIAL SUMMARY — Society Management

INCOME & COLLECTIONS:
• Total Collected Income: ₹{fin['total_income']:,.2f}
• Total Approved Expenses: ₹{fin['total_expense']:,.2f}
• Net Surplus: ₹{fin['net_surplus']:,.2f}

ANALYSIS:
"""
        if fin['net_surplus'] > 0:
            summary += f"• The society is operating with a positive surplus of ₹{fin['net_surplus']:,.2f}.\n"
        elif fin['net_surplus'] < 0:
            summary += f"• The society is operating with a deficit of ₹{abs(fin['net_surplus']):,.2f}.\n"
        else:
            summary += "• The society is breaking even with no surplus or deficit.\n"

        summary += """
RECOMMENDATIONS:
• Continue monitoring expense categories with highest expenditure.
• Review collection efficiency for maintenance dues.
• Maintain adequate reserves for emergency repairs.

AI-Generated Summary — Based on Actual Financial Data
"""
        return summary

    # ── STAGE 6: Document AI Features ────────────────────────────────────────

    @staticmethod
    def suggest_document_categorization(title, description):
        """
        Suggest document category based on title and description.
        Admin can override the suggestion.
        """
        text = f"{title} {description}".lower()

        categories = {
            "Financial": ["invoice", "receipt", "payment", "bill", "account", "financial", "tax", "audit"],
            "Legal": ["agreement", "contract", "legal", "deed", "lease", "bylaw", "regulation"],
            "Maintenance": ["maintenance", "repair", "service", "warranty", "amc", "inspection"],
            "Administrative": ["meeting", "minutes", "agenda", "notice", "circular", "announcement"],
            "Resident": ["resident", "owner", "tenant", "registration", "identity", "proof"],
            "Property": ["property", "building", "construction", "plan", "map", "layout"]
        }

        for category, keywords in categories.items():
            if any(keyword in text for keyword in keywords):
                return category

        return "General"

    @staticmethod
    def generate_document_summary(document_title, document_content):
        """
        Generate document summary based on content.
        For unsupported formats, returns graceful fallback.
        """
        if not document_content:
            return "Document content not available for summarization. This format may not be supported for AI processing."

        # Simple extractive summary (first few lines + key sections)
        lines = document_content.split('\n')
        if len(lines) > 10:
            summary = "\n".join(lines[:5]) + "\n\n[Document continues...]\n\n" + "\n".join(lines[-3:])
        else:
            summary = document_content

        return f"""DOCUMENT SUMMARY
Title: {document_title}

Content Preview:
{summary}

AI-Generated Summary — Based on Document Content Only
"""

    @staticmethod
    def ask_document(question, document_content):
        """
        Answer questions about a specific document.
        Answer must be grounded ONLY in the document content.
        """
        if not document_content:
            return "This document does not contain that information (content not available)."

        # Simple keyword-based search in document
        question_lower = question.lower()
        content_lower = document_content.lower()

        if question_lower in content_lower:
            # Find context around the keyword
            lines = document_content.split('\n')
            relevant_lines = [line for line in lines if question_lower in line.lower()]

            if relevant_lines:
                context = "\n".join(relevant_lines[:3])
                return f"Based on the document:\n\n{context}\n\nAI-Generated Answer — Grounded in Document Only"

        return "This document does not contain that information."

    # ── STAGE 2 Extended: Weekly and Monthly Summaries ────────────────────────

    @staticmethod
    def get_weekly_summary(society_id):
        """
        Generate weekly society management summary.
        Uses actual database aggregation.
        """
        today = utcnow().date()
        week_ago = today - timedelta(days=7)

        # Weekly statistics
        weekly_regs = RegistrationRequest.query.filter(
            RegistrationRequest.society_id == society_id,
            RegistrationRequest.created_at >= week_ago
        ).count()

        weekly_payments = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status == "Paid",
            MaintenanceBill.updated_at >= week_ago
        ).count()

        weekly_complaints = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.created_at >= week_ago
        ).count()

        weekly_visitors = Visitor.query.filter(
            Visitor.society_id == society_id,
            Visitor.entry_time >= week_ago
        ).count()

        # Calculate weekly collection
        weekly_bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.billing_month >= week_ago.strftime("%Y-%m")
        ).all()
        weekly_collection = sum(b.amount_paid for b in weekly_bills if b.updated_at and b.updated_at.date() >= week_ago)

        summary = f"""WEEKLY SOCIETY SUMMARY
Period: {week_ago.strftime('%d %B %Y')} to {today.strftime('%d %B %Y')}

REGISTRATIONS:
• New registrations: {weekly_regs}
• Approvals: Pending admin review

PAYMENTS:
• Payments received: {weekly_payments}
• Weekly collection: ₹{weekly_collection:,.2f}

COMPLAINTS:
• New complaints: {weekly_complaints}
• Resolution status: In progress

OPERATIONS:
• Visitor entries: {weekly_visitors}
• Inventory alerts: Check low stock items

AI-Generated Weekly Summary — Based on Actual Data
"""
        return summary

    @staticmethod
    def get_monthly_summary(society_id):
        """
        Generate monthly society management summary.
        Uses existing financial calculations.
        """
        today = utcnow().date()
        month_start = today.replace(day=1)

        # Monthly statistics
        monthly_regs = RegistrationRequest.query.filter(
            RegistrationRequest.society_id == society_id,
            RegistrationRequest.created_at >= month_start
        ).all()

        approved_count = sum(1 for r in monthly_regs if r.status == "APPROVED")
        rejected_count = sum(1 for r in monthly_regs if r.status == "REJECTED")

        monthly_bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.billing_month == today.strftime("%Y-%m")
        ).all()

        monthly_collection = sum(b.amount_paid for b in monthly_bills)
        monthly_outstanding = sum(b.remaining_amount for b in monthly_bills)

        monthly_complaints = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.created_at >= month_start
        ).count()

        # Financial summary using existing service
        fin = AccountingService.get_financial_summary(society_id)

        summary = f"""MONTHLY SOCIETY SUMMARY
Month: {today.strftime('%B %Y')}

FINANCIAL OVERVIEW:
• Total Collection: ₹{monthly_collection:,.2f}
• Outstanding Amount: ₹{monthly_outstanding:,.2f}
• Total Income: ₹{fin['total_income']:,.2f}
• Total Expenses: ₹{fin['total_expense']:,.2f}
• Net Surplus: ₹{fin['net_surplus']:,.2f}

REGISTRATION ACTIVITY:
• New Applications: {len(monthly_regs)}
• Approved: {approved_count}
• Rejected: {rejected_count}

COMPLAINT ACTIVITY:
• New Complaints: {monthly_complaints}
• Resolution Rate: Pending analysis

OPERATIONAL ALERTS:
• Inventory: Check low stock items
• Documents: Review expiring documents
• Tasks: Review overdue follow-ups

AI-Generated Monthly Summary — Based on Actual Financial Data
"""
        return summary

    # ── STAGE 4 Extended: Collection Prediction & Cash-Flow Forecast ──────────

    @staticmethod
    def generate_collection_prediction(society_id):
        """
        Generate collection prediction forecast using historical payment data.
        Returns estimated collection with confidence indicators.
        """
        six_months_ago = utcnow().date() - timedelta(days=180)
        historical_bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.billing_month >= six_months_ago.strftime("%Y-%m")
        ).all()

        if not historical_bills:
            return {
                "current_month": utcnow().strftime("%Y-%m"),
                "total_billed": 0.0,
                "already_collected": 0.0,
                "remaining_to_collect": 0.0,
                "predicted_collection": 0.0,
                "confidence": 0.5,
                "recovery_rate": 0.0,
                "trend": "stable",
                "trend_percentage": 0.0,
                "historical_months_analyzed": 0,
                "note": "ESTIMATE — Insufficient historical data for reliable prediction"
            }

        # Calculate historical collection patterns
        monthly_collections = {}
        for bill in historical_bills:
            month = bill.billing_month[:7]  # YYYY-MM
            if month not in monthly_collections:
                monthly_collections[month] = 0.0
            monthly_collections[month] += bill.amount_paid

        # Calculate total billed for recovery rate calculation
        total_billed_history = sum(b.total_amount for b in historical_bills)
        total_collected_history = sum(monthly_collections.values())

        # Calculate trend
        months_list = sorted(monthly_collections.keys())
        if len(months_list) >= 2:
            first_month = monthly_collections[months_list[0]]
            last_month = monthly_collections[months_list[-1]]
            trend = "increasing" if last_month > first_month else ("decreasing" if last_month < first_month else "stable")
            trend_pct = round(((last_month - first_month) / first_month * 100) if first_month > 0 else 0, 1)
        else:
            trend = "stable"
            trend_pct = 0.0

        # Current month prediction
        current_month = utcnow().strftime("%Y-%m")
        current_bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.billing_month == current_month
        ).all()

        total_billed = sum(b.total_amount for b in current_bills)
        already_collected = sum(b.amount_paid for b in current_bills)
        remaining_to_collect = total_billed - already_collected

        # Predict based on historical recovery rate
        if total_billed_history > 0:
            recovery_rate = total_collected_history / total_billed_history
        else:
            recovery_rate = 0.75  # Default recovery rate

        predicted_collection = round(already_collected + (remaining_to_collect * recovery_rate), 2)
        confidence = min(0.95, 0.75 + (len(months_list) * 0.03))  # Higher confidence with more history

        return {
            "current_month": current_month,
            "total_billed": round(total_billed, 2),
            "already_collected": round(already_collected, 2),
            "remaining_to_collect": round(remaining_to_collect, 2),
            "predicted_collection": predicted_collection,
            "confidence": round(confidence, 2),
            "recovery_rate": round(recovery_rate * 100, 1),
            "trend": trend,
            "trend_percentage": trend_pct,
            "historical_months_analyzed": len(months_list),
            "note": "ESTIMATE — Based on historical collection patterns only"
        }

    @staticmethod
    def generate_cash_flow_forecast(society_id):
        """
        Generate projected cash flow forecast.
        Uses historical collections, outstanding bills, and approved expenses.
        """
        today = utcnow().date()
        next_month = today.replace(day=1) + timedelta(days=32)
        next_month = next_month.replace(day=1)

        # Inflow projections
        unpaid_bills = MaintenanceBill.query.filter(
            MaintenanceBill.society_id == society_id,
            MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
        ).all()

        # Expected recovery based on overdue status
        expected_inflow = 0
        for bill in unpaid_bills:
            if bill.status == "Overdue":
                # Lower confidence for overdue
                expected_inflow += bill.remaining_amount * 0.45
            elif bill.status == "Pending":
                expected_inflow += bill.remaining_amount * 0.85
            else:  # Partially Paid
                expected_inflow += bill.remaining_amount * 0.65

        expected_inflow = round(expected_inflow, 2)

        # Outflow projections - approved expenses in next 30 days
        # Check what fields are available in ExpenseVoucher
        from app.models import ExpenseVoucher

        # Try different date field names
        next_month_expenses = []
        for expense in ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.status == "APPROVED"
        ).all():
            # Try various date field names
            expense_date = None
            if hasattr(expense, 'voucher_date') and expense.voucher_date:
                expense_date = expense.voucher_date
            elif hasattr(expense, 'created_at') and expense.created_at:
                expense_date = expense.created_at.date() if hasattr(expense.created_at, 'date') else expense.created_at
            elif hasattr(expense, 'date') and expense.date:
                expense_date = expense.date

            if expense_date and today <= expense_date <= today + timedelta(days=30):
                next_month_expenses.append(expense)

        expected_outflow = sum(e.amount for e in next_month_expenses)
        expected_outflow = round(expected_outflow, 2)

        # Projected balance
        current_balance = AccountingService.get_financial_summary(society_id).get("net_surplus", 0)
        projected_balance = round(current_balance + expected_inflow - expected_outflow, 2)

        # Confidence indicator based on data quality
        data_quality = "good" if len(unpaid_bills) > 5 else "limited"

        return {
            "forecast_period": {
                "start": today.isoformat(),
                "end": (today + timedelta(days=30)).isoformat()
            },
            "expected_inflow": expected_inflow,
            "expected_outflow": expected_outflow,
            "projected_balance": projected_balance,
            "current_balance": round(current_balance, 2),
            "data_quality": data_quality,
            "key_assumptions": [
                "Recovery rate: 45-85% based on payment status",
                "No new major expenses outside approved list",
                "Historical collection patterns continue"
            ],
            "note": "ESTIMATE — NOT ACTUAL ACCOUNTING DATA. For planning purposes only."
        }

    # ── STAGE 5 Extended: Automatic Task Escalation ───────────────────────────

    @staticmethod
    def get_overdue_tasks(society_id, days_overdue=0):
        """
        Find tasks that are overdue and may need escalation.
        Returns advisory list - never modifies tasks.
        """
        from datetime import timedelta
        from app.models import DefaulterFollowUp

        overdue_q = DefaulterFollowUp.query.filter(
            DefaulterFollowUp.society_id == society_id,
            DefaulterFollowUp.due_date < utcnow().date(),
            DefaulterFollowUp.status == "OPEN"
        )

        if days_overdue > 0:
            cutoff = utcnow().date() - timedelta(days=days_overdue)
            overdue_q = overdue_q.filter(DefaulterFollowUp.due_date < cutoff)

        overdue_tasks = overdue_q.all()

        tasks = []
        for task in overdue_tasks:
            days_over = (utcnow().date() - task.due_date).days
            # Determine escalation level based on days overdue
            if days_over > 30:
                priority = "CRITICAL"
                escalation_level = 3
            elif days_over > 15:
                priority = "HIGH"
                escalation_level = 2
            else:
                priority = "MEDIUM"
                escalation_level = 1

            tasks.append({
                "task_id": task.id,
                "description": task.reason or task.notes,
                "due_date": task.due_date.isoformat(),
                "days_overdue": days_over,
                "priority": priority,
                "escalation_level": escalation_level,
                "resident_id": task.resident_id,
                "flat_id": task.flat_id,
                "assigned_to": task.assigned_to_id,
                "advisory": "Review and escalate if necessary"
            })

        return tasks

    @staticmethod
    def generate_task_escalation_alert(society_id):
        """
        Generate task escalation alerts for overdue tasks.
        Returns advisory summary - never modifies tasks.
        """
        overdue_tasks = AIService.get_overdue_tasks(society_id, days_overdue=3)

        critical_count = sum(1 for t in overdue_tasks if t.get("priority") == "CRITICAL")
        high_count = sum(1 for t in overdue_tasks if t.get("priority") == "HIGH")
        medium_count = sum(1 for t in overdue_tasks if t.get("priority") == "MEDIUM")

        if not overdue_tasks:
            return {
                "summary": "No overdue tasks requiring immediate attention.",
                "critical_count": 0,
                "high_priority_count": 0,
                "medium_priority_count": 0,
                "tasks": [],
                "advisory_only": True,
                "note": "Review and escalate if necessary"
            }

        alert = {
            "summary": f"{len(overdue_tasks)} overdue task(s) detected. {critical_count} require immediate escalation.",
            "critical_count": critical_count,
            "high_priority_count": high_count,
            "medium_priority_count": medium_count,
            "tasks": overdue_tasks,
            "recommendations": [
                "Review critical tasks immediately",
                "Assign to senior staff for high-priority tasks",
                "Document reasons for delays"
            ],
            "advisory_only": True,
            "note": "Review and escalate if necessary"
        }

        return alert

    # ── STAGE 5 Extended: Automatic Expiry Reminders ───────────────────────────

    @staticmethod
    def get_expiring_items(society_id, days_threshold=30):
        """
        Find items that are expiring within the threshold.
        Supports: document contracts, vendor contracts, asset warranties, AMC.
        Returns advisory list - never modifies records.
        """
        today = utcnow().date()
        expiry_threshold = today + timedelta(days=days_threshold)

        expiring = []

        # Documents don't have expiry_date in current model - skip for now

        # Assets with warranty expiring
        assets = Asset.query.filter(
            Asset.society_id == society_id,
            Asset.warranty_expiry >= today,
            Asset.warranty_expiry <= expiry_threshold,
            Asset.warranty_expiry.isnot(None)
        ).all()

        for asset in assets:
            days_until_expiry = (asset.warranty_expiry - today).days
            expiring.append({
                "type": "asset_warranty",
                "id": asset.id,
                "name": asset.asset_name,
                "category": asset.category,
                "expiry_date": asset.warranty_expiry.isoformat(),
                "days_until_expiry": days_until_expiry,
                "severity": "critical" if days_until_expiry <= 7 else ("warning" if days_until_expiry <= 14 else "info"),
                "action": "Contact vendor for warranty extension"
            })

        # Vendor contracts expiring
        vendors = Vendor.query.filter(
            Vendor.society_id == society_id,
            Vendor.contract_end >= today,
            Vendor.contract_end <= expiry_threshold,
            Vendor.contract_end.isnot(None)
        ).all()

        for vendor in vendors:
            days_until_expiry = (vendor.contract_end - today).days
            expiring.append({
                "type": "vendor_contract",
                "id": vendor.id,
                "name": vendor.company_name,
                "category": vendor.category,
                "expiry_date": vendor.contract_end.isoformat(),
                "days_until_expiry": days_until_expiry,
                "severity": "critical" if days_until_expiry <= 7 else ("warning" if days_until_expiry <= 14 else "info"),
                "action": "Renegotiate or select replacement"
            })

        # AMC expiring (stored as next_service_due in asset)
        amc_items = Asset.query.filter(
            Asset.society_id == society_id,
            Asset.next_service_due >= today,
            Asset.next_service_due <= expiry_threshold,
            Asset.next_service_due.isnot(None)
        ).all()

        for asset in amc_items:
            days_until_amc = (asset.next_service_due - today).days
            expiring.append({
                "type": "amc",
                "id": asset.id,
                "name": asset.asset_name,
                "category": asset.category,
                "expiry_date": asset.next_service_due.isoformat(),
                "days_until_expiry": days_until_amc,
                "severity": "critical" if days_until_amc <= 7 else ("warning" if days_until_amc <= 14 else "info"),
                "action": "Schedule AMC renewal"
            })

        return expiring

    @staticmethod
    def generate_expiry_reminder_summary(society_id, days_threshold=30):
        """
        Generate expiry reminder summary for admin review.
        Uses actual expiry dates from database - never modifies records.
        """
        expiring_items = AIService.get_expiring_items(society_id, days_threshold)

        if not expiring_items:
            return {
                "summary": f"No items expiring within the next {days_threshold} days.",
                "total_expiring": 0,
                "items": [],
                "note": "Check again after threshold period"
            }

        critical_count = sum(1 for i in expiring_items if i["severity"] == "critical")

        summary = f"""EXPIRY REMINDERS SUMMARY
Period: Next {days_threshold} days

CRITICAL ({critical_count} items):
"""
        for item in expiring_items:
            if item["severity"] == "critical":
                summary += f"• {item['type'].replace('_', ' ').title()}: {item.get('name', 'Unknown')} - {item['expiry_date'][:10]}\n"

        summary += """
RECOMMENDATIONS:
1. Prioritize critical items (expiring within 7 days)
2. Contact vendors for warranty/AMC renewals
3. Archive or renew expired documents
4. Update expiry dates in system

AI-Generated Reminder Summary — Based on Database Records
"""

        return {
            "summary": summary,
            "total_expiring": len(expiring_items),
            "critical_count": critical_count,
            "warning_count": sum(1 for i in expiring_items if i["severity"] == "warning"),
            "items": expiring_items,
            "note": "REVIEW REQUIRED - AI summary only"
        }

    # ── STAGE 5 Extended: Low Stock Automation ─────────────────────────────────

    @staticmethod
    def get_low_stock_items(society_id, include_reorder_suggestions=True):
        """
        Find inventory items at or below minimum stock levels.
        Returns advisory list with optional reorder suggestions.
        """
        inventory_items = InventoryItem.query.filter(
            InventoryItem.society_id == society_id,
            InventoryItem.current_stock <= InventoryItem.minimum_threshold
        ).all()

        items = []
        for item in inventory_items:
            # Calculate suggested reorder quantity (2x minimum threshold or 10 units, whichever is higher)
            suggested_qty = max(item.minimum_threshold * 2, 10)

            items.append({
                "item_id": item.id,
                "item_name": item.item_name,
                "category": item.category,
                "current_stock": item.current_stock,
                "minimum_threshold": item.minimum_threshold,
                "unit": item.unit or "units",
                "severity": "critical" if item.current_stock == 0 else ("warning" if item.current_stock <= item.minimum_threshold / 2 else "info"),
                "days_until_exhaustion": item.current_stock * 7 if item.current_stock > 0 else 0,
                "suggested_reorder_quantity": suggested_qty if include_reorder_suggestions else None,
                "advisory": "Review and place reorder order"
            })

        return items

    @staticmethod
    def generate_low_stock_alert(society_id):
        """
        Generate low stock alert summary for admin review.
        Returns advisory summary - never modifies inventory.
        """
        low_stock_items = AIService.get_low_stock_items(society_id)

        if not low_stock_items:
            return {
                "summary": "All inventory items are adequately stocked.",
                "total_low_stock": 0,
                "items": [],
                "note": "No action required"
            }

        critical_count = sum(1 for i in low_stock_items if i["severity"] == "critical")
        warning_count = sum(1 for i in low_stock_items if i["severity"] == "warning")

        alert = {
            "summary": f"{len(low_stock_items)} inventory item(s) at or below minimum stock levels. {critical_count} items require immediate restocking.",
            "total_low_stock": len(low_stock_items),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "items": low_stock_items,
            "recommendations": [
                "Immediate: Reorder critical items (stock = 0)",
                "Urgent: Restock warning-level items",
                "Review inventory management thresholds"
            ],
            "advisory_only": True
        }

        return alert

    # ── STAGE 6 Extended: AI Document Search ───────────────────────────────────

    @staticmethod
    def ai_search_documents(society_id, query, categories=None, tags=None):
        """
        AI-enhanced document search with categorization support.
        Searches filename, metadata, category, tags, and extracted text.
        Respects Admin authorization and society isolation.
        """

        q = Document.query.filter_by(society_id=society_id)

        # Search by category if specified
        if categories:
            if isinstance(categories, str):
                categories = [categories]
            q = q.filter(Document.category.in_(categories))

        # Search by tags if specified
        if tags:
            if isinstance(tags, str):
                tags = [tags]
            for tag in tags:
                q = q.filter(
                    Document.tags.ilike(f"%{tag}%") |
                    Document.category.ilike(f"%{tag}%")
                )

        # Search by query string in filename, title, description, category
        if query:
            search_pattern = f"%{query}%"
            q = q.filter(
                Document.title.ilike(search_pattern) |
                Document.description.ilike(search_pattern) |
                Document.category.ilike(search_pattern) |
                Document.tags.ilike(search_pattern)
            )

        documents = q.order_by(Document.created_at.desc()).all()

        # Score documents by relevance (simple heuristic)
        results = []
        query_lower = query.lower() if query else ""

        for doc in documents:
            # Calculate relevance score
            score = 0

            if doc.title and query_lower in doc.title.lower():
                score += 10
            if doc.description and query_lower in doc.description.lower():
                score += 5
            if doc.category and query_lower in doc.category.lower():
                score += 3
            if doc.tags and query_lower in doc.tags.lower():
                score += 2

            if score > 0:
                results.append({
                    "id": doc.id,
                    "title": doc.title,
                    "category": doc.category,
                    "tags": doc.tags,
                    "description": doc.description[:200] if doc.description else None,
                    "access_level": doc.access_level,
                    "relevance_score": score,
                    "suggested_action": "View document details"
                })

        # Sort by relevance score descending
        results.sort(key=lambda x: x["relevance_score"], reverse=True)

        return {
            "query": query,
            "total_results": len(results),
            "results": results,
            "note": "AI-Enhanced Search - Results ranked by relevance"
        }

    # ── STAGE 7: Resident AI Assistant ─────────────────────────────────────────

    @staticmethod
    def get_resident_assistant_response(user, prompt):
        """
        AI Assistant for residents with strict data isolation.
        Only returns data authorized for the current resident.
        Never trusts user_id, society_id, or flat_id from request body.
        Derives all values from authenticated session.
        """
        if not user or (hasattr(user, "role") and str(user.role) not in [Role.RESIDENT, "Resident", "Role.RESIDENT"]):
            return {"error": "Resident authentication required"}

        society_id = user.society_id
        if not society_id:
            return {"error": "Society association not found"}

        # Derive resident from user_id in session
        resident = Resident.query.filter_by(
            user_id=user.id,
            society_id=society_id
        ).first()

        if not resident:
            return {"error": "Resident profile not found for this account"}

        prompt_lower = prompt.lower().strip()

        # Check for overdue bills
        if any(w in prompt_lower for w in ["overdue", "late fee", "penalty", "any overdue"]):
            overdue_bills = MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status == "Overdue"
            ).all()

            if overdue_bills:
                total_overdue = sum(b.remaining_amount for b in overdue_bills)
                return {
                    "response": f"You have {len(overdue_bills)} overdue bill(s) totalling ₹{total_overdue:,.2f}. Please pay soon to avoid additional penalties.",
                    "overdue_count": len(overdue_bills),
                    "total_overdue": round(total_overdue, 2),
                    "data_source": "your_bills"
                }
            else:
                return {
                    "response": "Great news! You have no overdue maintenance bills. Your account is in good standing.",
                    "overdue_count": 0,
                    "total_overdue": 0,
                    "data_source": "your_bills"
                }

        # Check for complaint status
        if any(w in prompt_lower for w in ["status of my complaint", "complaint status", "my complaint", "track complaint", "service request status"]):
            complaints = Complaint.query.filter_by(
                resident_id=resident.id,
                society_id=society_id
            ).order_by(Complaint.created_at.desc()).limit(3).all()

            if complaints:
                items = [f"• #{c.ticket_number} ({c.title}) — Status: {c.status}" for c in complaints]
                return {
                    "response": "Here are your recent complaints:\n" + "\n".join(items),
                    "complaints_count": len(complaints),
                    "data_source": "your_complaints"
                }
            else:
                return {
                    "response": "You have no logged complaints at this time. You can submit a new one from the Complaint Desk.",
                    "complaints_count": 0,
                    "data_source": "your_complaints"
                }

        # Check payment history
        if any(w in prompt_lower for w in ["payment history", "my payments", "past payments", "recent payments", "show my payment"]):
            from app.models import Payment as _Payment
            recent_payments = _Payment.query.filter(
                _Payment.resident_id == resident.id,
                _Payment.society_id == society_id
            ).order_by(_Payment.payment_date.desc()).limit(3).all()

            if recent_payments:
                items = [f"• ₹{p.amount_paid:,.2f} on {p.payment_date.strftime('%d %b %Y') if p.payment_date else 'N/A'} ({p.status})" for p in recent_payments]
                return {
                    "response": "Your recent payment transactions:\n" + "\n".join(items),
                    "payments_count": len(recent_payments),
                    "data_source": "your_payments"
                }
            else:
                return {
                    "response": "No recorded payments found on your account yet.",
                    "payments_count": 0,
                    "data_source": "your_payments"
                }

        # Response 2: "When is my next bill due?"
        if any(w in prompt_lower for w in ["next bill", "when is my", "due date", "when due", "next due"]):
            upcoming_bill = MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(["Pending", "Partially Paid"])
            ).order_by(MaintenanceBill.due_date.asc()).first()

            if upcoming_bill and upcoming_bill.due_date:
                days_until_due = (upcoming_bill.due_date - utcnow().date()).days
                return {
                    "response": f"Your next bill is due on {upcoming_bill.due_date.strftime('%d %B %Y')} ({days_until_due} days from today).",
                    "due_date": upcoming_bill.due_date.isoformat(),
                    "days_until_due": days_until_due,
                    "data_source": "your_bills"
                }
            else:
                return {
                    "response": "You don't have any pending bills at this time. All your maintenance is up to date.",
                    "due_date": None,
                    "days_until_due": None,
                    "data_source": "your_bills"
                }

        # Response 1: "What is my pending amount?"
        if any(w in prompt_lower for w in ["pending amount", "how much do i owe", "outstanding", "balance due", "amount due", "total due", "pending maintenance", "pending"]):
            pending_bills = MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.status.in_(["Pending", "Partially Paid", "Overdue"])
            ).all()

            total_due = sum(b.remaining_amount for b in pending_bills)

            if total_due > 0:
                return {
                    "response": f"Hello {resident.full_name.split()[0]}, your pending maintenance amount is ₹{total_due:,.2f} across {len(pending_bills)} bill(s).",
                    "bill_count": len(pending_bills),
                    "total_due": round(total_due, 2),
                    "data_source": "your_bills"
                }
            else:
                return {
                    "response": f"Hello {resident.full_name.split()[0]}, all your maintenance bills are fully paid. No pending amount.",
                    "bill_count": 0,
                    "total_due": 0,
                    "data_source": "your_bills"
                }

        # Response 3: "Explain my bill."
        if any(w in prompt_lower for w in ["explain my bill", "what is this charge", "bill details", "charge breakdown"]):
            recent_bills = MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.society_id == society_id
            ).order_by(MaintenanceBill.billing_month.desc()).limit(1).all()

            if recent_bills:
                bill = recent_bills[0]
                return {
                    "response": f"Your {bill.billing_month} maintenance bill of ₹{bill.total_amount:,.2f} includes base amount of ₹{bill.base_amount:,.2f}. Status: {bill.status}.",
                    "billing_month": bill.billing_month,
                    "total_amount": bill.total_amount,
                    "base_amount": bill.base_amount,
                    "status": bill.status,
                    "data_source": "your_bills"
                }
            else:
                return {
                    "response": "No recent bills found for your account.",
                    "billing_month": None,
                    "data_source": "your_bills"
                }

        # Response 4: "Why is my payment pending?"
        if any(w in prompt_lower for w in ["payment pending", "payment status", "transaction status", "why pending"]):
            from app.models import Payment as _Payment
            recent_payments = _Payment.query.filter(
                _Payment.resident_id == resident.id,
                _Payment.society_id == society_id
            ).order_by(_Payment.payment_date.desc()).limit(5).all()

            if recent_payments:
                pending_payments = [p for p in recent_payments if p.status in ["Pending", "Processing", "Initiated"]]
                if pending_payments:
                    payment = pending_payments[0]
                    return {
                        "response": f"Your payment of ₹{payment.amount_paid:,.2f} (TXN: {payment.transaction_id or 'N/A'}) is currently {payment.status}. Please allow 24-48 hours for processing.",
                        "payment_status": payment.status,
                        "amount": payment.amount_paid,
                        "transaction_id": payment.transaction_id,
                        "data_source": "your_payments"
                    }
                else:
                    return {
                        "response": "All your recent payments have been processed successfully. No pending payments found.",
                        "payment_status": "none_pending",
                        "data_source": "your_payments"
                    }
            else:
                return {
                    "response": "No payment records found for your account.",
                    "payment_status": "none_found",
                    "data_source": "your_payments"
                }

        # Response 5: "How can I contact the society?"
        if any(w in prompt_lower for w in ["contact society", "contact admin", "society contact", "phone number", "email"]):
            return {
                "response": "You can contact the society administration through:\n• Admin Office: Available during working hours\n• Mobile: Contact your society admin for direct number\n• In-App: Use the complaints section for non-urgent matters",
                "contact_methods": ["admin_office", "mobile", "in_app_complaints"],
                "data_source": "general_info"
            }

        # Response 6: "How do I submit a complaint?"
        if any(w in prompt_lower for w in ["submit complaint", "file complaint", "raise issue", "complaint process"]):
            return {
                "response": "To submit a complaint:\n1. Go to the Complaints section\n2. Select category\n3. Describe your issue\n4. Attach photos if needed\n5. Submit and track status",
                "steps": ["go_to_complaints", "select_category", "describe_issue", "attach_photos", "submit"],
                "data_source": "general_info"
            }

        # Response 7: "How do I download my receipt?"
        if any(w in prompt_lower for w in ["download receipt", "receipt download", "payment receipt", "get receipt"]):
            return {
                "response": "To download your receipt:\n1. Go to Payments > Payment History\n2. Find your transaction\n3. Click 'Download Receipt' button\n4. Save the PDF to your device",
                "steps": ["go_to_payments", "find_transaction", "click_download", "save_pdf"],
                "data_source": "general_info"
            }

        # Default response
        return {
            "response": "I can help you with questions about your pending amount, bill due dates, payment status, contacting the society, submitting complaints, or downloading receipts. What would you like to know?",
            "supported_queries": [
                "What is my pending amount?",
                "When is my next bill due?",
                "Explain my bill.",
                "Why is my payment pending?",
                "How can I contact the society?",
                "How do I submit a complaint?",
                "How do I download my receipt?"
            ],
            "data_source": "general_info"
        }


    # ── PHASE 1: Bill Explanation ─────────────────────────────────────────────

    @staticmethod
    def explain_bill(bill, resident):
        """
        Generate a plain-language explanation for a single MaintenanceBill.
        Read-only — never modifies the bill.
        bill  : MaintenanceBill ORM object (caller must verify ownership)
        resident: Resident ORM object (caller must verify session ownership)
        Returns a dict with 'explanation' (str) and supporting data fields.
        """
        try:
            from app.utils import utcnow as _utcnow

            today = _utcnow().date()
            try:
                from datetime import datetime as _dt
                billing_display = _dt.strptime(bill.billing_month, "%Y-%m").strftime("%B %Y")
            except (ValueError, AttributeError):
                billing_display = bill.billing_month or "this month"

            parts = []

            # Core maintenance line
            parts.append(
                f"Your maintenance for {billing_display} is ₹{bill.base_amount:,.2f}."
            )

            # Previous balance
            if getattr(bill, "previous_balance", 0) and bill.previous_balance > 0:
                parts.append(
                    f"You had an outstanding balance of ₹{bill.previous_balance:,.2f} carried forward from the previous period."
                )

            # Late fee
            if bill.late_fee and bill.late_fee > 0:
                parts.append(
                    f"A late fee of ₹{bill.late_fee:,.2f} has been applied because payment was not received by the due date."
                )

            # Additional charges
            if getattr(bill, "additional_charges", 0) and bill.additional_charges > 0:
                parts.append(
                    f"Additional charges of ₹{bill.additional_charges:,.2f} have been included."
                )

            # Discount
            if getattr(bill, "discount", 0) and bill.discount > 0:
                parts.append(
                    f"A discount of ₹{bill.discount:,.2f} has been applied."
                )

            # Total and status
            parts.append(
                f"The total bill amount is ₹{bill.total_amount:,.2f}."
            )

            if bill.status == "Paid":
                parts.append("This bill has been fully paid. No amount is outstanding.")
            elif bill.status == "Partially Paid":
                parts.append(
                    f"You have paid ₹{bill.amount_paid:,.2f} so far. The remaining balance is ₹{bill.remaining_amount:,.2f}."
                )
            elif bill.status == "Overdue":
                if bill.due_date:
                    overdue_days = (today - bill.due_date).days
                    parts.append(
                        f"This bill is overdue by {overdue_days} day(s). The balance due is ₹{bill.remaining_amount:,.2f}. "
                        "Please pay as soon as possible to avoid further late charges."
                    )
                else:
                    parts.append(
                        f"This bill is overdue. The balance due is ₹{bill.remaining_amount:,.2f}."
                    )
            else:  # Pending
                if bill.due_date:
                    days_left = (bill.due_date - today).days
                    if days_left > 0:
                        parts.append(
                            f"Payment of ₹{bill.remaining_amount:,.2f} is due on "
                            f"{bill.due_date.strftime('%d %B %Y')} ({days_left} day(s) remaining)."
                        )
                    elif days_left == 0:
                        parts.append(
                            f"Payment of ₹{bill.remaining_amount:,.2f} is due today. "
                            "Please pay now to avoid late fees."
                        )
                    else:
                        parts.append(
                            f"Payment of ₹{bill.remaining_amount:,.2f} was due on "
                            f"{bill.due_date.strftime('%d %B %Y')}. Please settle immediately."
                        )
                else:
                    parts.append(
                        f"₹{bill.remaining_amount:,.2f} is outstanding on this bill."
                    )

            explanation = " ".join(parts)

            return {
                "explanation": explanation,
                "billing_month": bill.billing_month,
                "billing_month_display": billing_display,
                "base_amount": bill.base_amount,
                "late_fee": bill.late_fee,
                "total_amount": bill.total_amount,
                "amount_paid": bill.amount_paid,
                "remaining_amount": bill.remaining_amount,
                "status": bill.status,
                "due_date": bill.due_date.isoformat() if bill.due_date else None,
                "ai_powered": False,  # deterministic, no LLM call
            }
        except Exception as exc:
            logger.warning("explain_bill error: %s", exc)
            return {
                "explanation": "AI Assistant is temporarily unavailable. Please view the bill details directly.",
                "error": True,
            }

    # ── PHASE 1: Payment Status Explanation ──────────────────────────────────

    @staticmethod
    def explain_payment_status(payment, resident):
        """
        Generate a plain-language explanation of a payment's current status.
        Read-only — never modifies the payment.
        Returns a dict with 'explanation' (str) and supporting metadata.
        """
        try:
            status = (payment.status or "").lower()
            method = payment.payment_method or "Online"
            amount = payment.amount_paid
            txn = payment.transaction_id or "N/A"

            status_map = {
                "captured": (
                    f"Your payment of ₹{amount:,.2f} via {method} (Reference: {txn}) was "
                    "successfully processed and has been applied to your bill.",
                    "success",
                ),
                "success": (
                    f"Your payment of ₹{amount:,.2f} via {method} (Reference: {txn}) was "
                    "successfully processed.",
                    "success",
                ),
                "paid": (
                    f"Your payment of ₹{amount:,.2f} via {method} has been confirmed.",
                    "success",
                ),
                "authorized": (
                    f"Your payment of ₹{amount:,.2f} has been authorised by your bank but "
                    "has not yet been captured. This usually resolves automatically within a few minutes. "
                    "If this persists, please contact the society office.",
                    "warning",
                ),
                "pending": (
                    f"Your payment of ₹{amount:,.2f} via {method} is currently being processed. "
                    "This usually takes a few minutes. Please do not make another payment for the same bill.",
                    "warning",
                ),
                "created": (
                    f"Your payment of ₹{amount:,.2f} has been initiated. "
                    "Please complete the payment on the payment page.",
                    "warning",
                ),
                "failed": (
                    f"Your payment of ₹{amount:,.2f} via {method} was unsuccessful. "
                    f"Reason: {payment.failure_reason or 'Payment could not be completed'}. "
                    "Please try again or contact your bank if the issue persists.",
                    "danger",
                ),
                "cancelled": (
                    f"Your payment of ₹{amount:,.2f} was cancelled. "
                    "If this was unintentional, please initiate a new payment.",
                    "danger",
                ),
                "refunded": (
                    f"A refund of ₹{payment.refund_amount or amount:,.2f} has been processed. "
                    "Please allow 5–7 business days for it to reflect in your account.",
                    "info",
                ),
                "partially_refunded": (
                    f"A partial refund of ₹{payment.refund_amount or 0:,.2f} has been processed. "
                    "The remaining amount is retained. Contact the society office for details.",
                    "warning",
                ),
            }

            # Cash / manual payments needing verification
            if method.lower() in ("cash", "bank transfer", "manual") and status in ("pending", "created"):
                explanation = (
                    f"Your cash/bank payment of ₹{amount:,.2f} has been submitted and is "
                    "awaiting verification by the society Admin. Once verified, your bill will be "
                    "marked as paid. This usually happens within 1–2 working days."
                )
                severity = "warning"
            else:
                explanation, severity = status_map.get(
                    status,
                    (
                        f"Your payment of ₹{amount:,.2f} has a status of '{payment.status}'. "
                        "If you have any questions, please contact the society office.",
                        "info",
                    ),
                )

            return {
                "explanation": explanation,
                "severity": severity,
                "payment_status": payment.status,
                "payment_method": method,
                "amount_paid": amount,
                "transaction_id": txn,
                "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
                "ai_powered": False,
            }
        except Exception as exc:
            logger.warning("explain_payment_status error: %s", exc)
            return {
                "explanation": "AI Assistant is temporarily unavailable.",
                "error": True,
            }

    # ── PHASE 1: Personal Dashboard AI Summary ────────────────────────────────

    @staticmethod
    def get_resident_account_summary(resident, society_id):
        """
        Generate a concise personal financial/account summary for the dashboard.
        Uses only authenticated resident's data — no cross-resident leakage.
        Returns dict with 'summary_text' (str) and key metrics.
        """
        try:
            from app.models import Payment as _Payment, Complaint as _Complaint

            # All bills for this resident
            all_bills = MaintenanceBill.query.filter_by(
                resident_id=resident.id,
                society_id=society_id,
            ).order_by(MaintenanceBill.billing_month.desc()).all()

            total_billed = sum(b.total_amount for b in all_bills)
            total_paid = sum(b.amount_paid for b in all_bills)
            total_outstanding = sum(b.remaining_amount for b in all_bills if b.status != "Paid")
            overdue_bills = [b for b in all_bills if b.status == "Overdue"]
            pending_bills = [b for b in all_bills if b.status in ("Pending", "Partially Paid")]

            # Last confirmed payment
            last_payment = (
                _Payment.query.filter(
                    _Payment.resident_id == resident.id,
                    _Payment.society_id == society_id,
                    _Payment.status.in_(["captured", "Success", "paid"]),
                )
                .order_by(_Payment.payment_date.desc())
                .first()
            )

            # Open complaints
            open_complaints = _Complaint.query.filter(
                _Complaint.resident_id == resident.id,
                _Complaint.society_id == society_id,
                _Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
            ).count()

            # Build summary text
            if total_outstanding == 0 and not overdue_bills:
                status_line = "Your maintenance account is fully up to date. No outstanding dues."
            elif overdue_bills:
                n = len(overdue_bills)
                amt = sum(b.remaining_amount for b in overdue_bills)
                status_line = (
                    f"You have {n} overdue bill(s) totalling ₹{amt:,.0f}. "
                    "Please settle immediately to avoid additional late fees."
                )
            else:
                n = len(pending_bills)
                status_line = (
                    f"You have ₹{total_outstanding:,.0f} outstanding across {n} pending bill(s)."
                )

            last_pay_line = ""
            if last_payment and last_payment.payment_date:
                last_pay_line = (
                    f"Your last payment of ₹{last_payment.amount_paid:,.0f} "
                    f"was received on {last_payment.payment_date.strftime('%d %b %Y')}."
                )

            complaint_line = ""
            if open_complaints > 0:
                complaint_line = (
                    f"You have {open_complaints} open complaint(s) being processed."
                )

            lines = [status_line]
            if last_pay_line:
                lines.append(last_pay_line)
            if complaint_line:
                lines.append(complaint_line)
            summary_text = " ".join(lines)

            # Next bill due
            next_bill = (
                min(pending_bills, key=lambda b: b.due_date)
                if pending_bills and all(b.due_date for b in pending_bills)
                else (pending_bills[0] if pending_bills else None)
            )

            return {
                "summary_text": summary_text,
                "status": (
                    "all_clear" if total_outstanding == 0
                    else ("overdue" if overdue_bills else "pending")
                ),
                "total_billed": round(total_billed, 2),
                "total_paid": round(total_paid, 2),
                "total_outstanding": round(total_outstanding, 2),
                "overdue_count": len(overdue_bills),
                "pending_count": len(pending_bills),
                "open_complaints": open_complaints,
                "last_payment_date": (
                    last_payment.payment_date.strftime("%d %b %Y")
                    if last_payment and last_payment.payment_date else None
                ),
                "last_payment_amount": (
                    round(last_payment.amount_paid, 2) if last_payment else None
                ),
                "next_due_date": (
                    next_bill.due_date.isoformat() if next_bill and next_bill.due_date else None
                ),
                "next_due_amount": (
                    round(next_bill.remaining_amount, 2) if next_bill else None
                ),
                "ai_powered": False,
            }
        except Exception as exc:
            logger.warning("get_resident_account_summary error: %s", exc)
            return {
                "summary_text": "Summary unavailable. Please check your bills directly.",
                "error": True,
            }

    # ── PHASE 1: Smart Notification Grouping ─────────────────────────────────

    @staticmethod
    def group_resident_notifications(notifications):
        """
        Group a list of NotificationLog objects into categorised buckets.
        Does NOT create, delete, or modify any notification records.
        Returns a dict with category buckets and an unread count.
        """
        groups = {
            "payments": [],
            "maintenance": [],
            "notices": [],
            "complaints": [],
            "account": [],
            "general": [],
        }

        _PAYMENT_TYPES = {
            "PAYMENT_SUCCESS", "PAYMENT_FAILED", "PAYMENT_PENDING",
            "CASH_VERIFICATION", "REFUND",
        }
        _MAINTENANCE_TYPES = {
            "DUE_REMINDER", "OVERDUE_REMINDER", "LATE_FEE_NOTICE",
            "ESCALATION_NOTICE", "BILLING_NOTICE",
        }
        _COMPLAINT_TYPES = {"COMPLAINT_UPDATE", "COMPLAINT_RESOLVED", "COMPLAINT_ASSIGNED"}
        _ACCOUNT_TYPES = {"ACCOUNT_STATUS", "REGISTRATION", "PASSWORD_CHANGE", "OTP"}

        total_unread = 0
        for n in notifications:
            ntype = (getattr(n, "notification_type", None) or "").upper()
            cat = getattr(n, "category", None) or ""
            is_unread = getattr(n, "read_at", None) is None

            if is_unread:
                total_unread += 1

            entry = {
                "id": n.id,
                "message": n.message,
                "subject": n.subject,
                "notification_type": n.notification_type,
                "sent_at": n.sent_at.isoformat() if getattr(n, "sent_at", None) else None,
                "created_at": (
                    n.created_at.isoformat()
                    if getattr(n, "created_at", None) else None
                ),
                "is_unread": is_unread,
                "channel": n.channel,
            }

            if ntype in _PAYMENT_TYPES or cat.upper() == "PAYMENT":
                groups["payments"].append(entry)
            elif ntype in _MAINTENANCE_TYPES or cat.upper() in ("MAINTENANCE", "REMINDER"):
                groups["maintenance"].append(entry)
            elif ntype in _COMPLAINT_TYPES or cat.upper() == "COMPLAINT":
                groups["complaints"].append(entry)
            elif ntype in _ACCOUNT_TYPES or cat.upper() == "ACCOUNT":
                groups["account"].append(entry)
            elif cat.upper() in ("ANNOUNCEMENT", "NOTICE"):
                groups["notices"].append(entry)
            else:
                groups["general"].append(entry)

        non_empty = {k: v for k, v in groups.items() if v}
        return {
            "groups": non_empty,
            "total_notifications": len(notifications),
            "total_unread": total_unread,
            "category_counts": {k: len(v) for k, v in groups.items()},
        }
