"""
Resident AI Service
===================
Provides AI-powered assistance for residents with strict data isolation.

SECURITY GUARANTEES:
- Every method derives the resident identity from the Flask session.
- User-supplied IDs from request bodies are NEVER trusted.
- A resident can only read their own data (society_id + resident.id checked).
- No write operations are performed here (read-only service).
- AI fallback: if AI_PROVIDER == 'deterministic', deterministic text is returned
  so the Resident portal never breaks when an external LLM is unconfigured.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from flask import current_app, session

from app.models import (
    Complaint,
    MaintenanceBill,
    NotificationLog,
    Payment,
    Resident,
    Role,
    User,
    db,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _fmt_money(amount: float) -> str:
    return f"₹{amount:,.2f}"


def _session_resident() -> Optional[Resident]:
    """
    Return the authenticated Resident for the current request.

    CRITICAL — all lookups start here.  We read the user_id from the
    server-side Flask session, validate role and account status, then
    look up the resident row that belongs to that user **in the same
    society**.  An attacker who tampers with a client-side value cannot
    bypass this chain.
    """
    user_id = session.get("user_id")
    role = session.get("role")
    society_id = session.get("society_id")

    if not user_id or role != Role.RESIDENT or not society_id:
        return None

    user = db.session.get(User, int(user_id))
    if (
        not user
        or user.role != Role.RESIDENT
        or user.account_status != "ACTIVE"
        or user.society_id != int(society_id)
    ):
        return None

    return Resident.query.filter_by(
        user_id=user.id,
        society_id=user.society_id,
        is_primary=True,
    ).first()


def _verify_owns_bill(bill_id: int, resident: Resident) -> Optional[MaintenanceBill]:
    """Return the bill only if it belongs to this resident in this society."""
    from sqlalchemy import or_
    return MaintenanceBill.query.filter(
        MaintenanceBill.id == bill_id,
        MaintenanceBill.society_id == resident.society_id,
        or_(
            MaintenanceBill.resident_id == resident.id,
            db.and_(
                MaintenanceBill.resident_id.is_(None),
                MaintenanceBill.flat_id == resident.flat_id,
            ),
        ),
    ).first()


def _verify_owns_payment(payment_id: int, resident: Resident) -> Optional[Payment]:
    """Return the payment only if it belongs to this resident in this society."""
    return Payment.query.filter_by(
        id=payment_id,
        resident_id=resident.id,
        society_id=resident.society_id,
    ).first()


# ---------------------------------------------------------------------------
# AI text generation (with graceful fallback)
# ---------------------------------------------------------------------------

def _generate(prompt: str, max_tokens: int = 300, temperature: float = 0.4) -> Optional[str]:
    """
    Call the configured AI provider.
    Returns None if the provider is 'deterministic' or if the call fails,
    so callers can fall back to rule-based strings.
    """
    provider = current_app.config.get("AI_PROVIDER", "deterministic")
    if provider == "deterministic" or not provider:
        return None  # signal: use deterministic fallback

    api_key = current_app.config.get("AI_API_KEY", "")
    if not api_key:
        logger.warning("AI_API_KEY not configured; falling back to deterministic mode.")
        return None

    try:
        if provider == "openai":
            import openai  # type: ignore
            openai.api_key = api_key
            model = current_app.config.get("AI_MODEL", "gpt-3.5-turbo")
            timeout = current_app.config.get("AI_TIMEOUT_SECONDS", 30)
            response = openai.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=timeout,
            )
            return response.choices[0].message.content.strip()

        if provider == "anthropic":
            import anthropic  # type: ignore
            client = anthropic.Anthropic(api_key=api_key)
            model = current_app.config.get("AI_MODEL", "claude-3-haiku-20240307")
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text.strip()

        logger.warning(f"Unknown AI_PROVIDER '{provider}'; falling back to deterministic mode.")
        return None

    except Exception as exc:
        logger.error(f"AI generation failed [{provider}]: {exc}")
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ResidentAIService:
    """
    All public methods are classmethods so they can be called without
    instantiation.  Each method re-authenticates via _session_resident()
    before touching any data.
    """

    # ── Financial summary ──────────────────────────────────────────────────

    @classmethod
    def get_financial_summary(cls, resident: Optional[Resident] = None) -> Dict[str, Any]:
        """
        Build a lightweight financial summary for the resident.
        Pass a pre-fetched Resident to avoid a second session lookup.
        """
        if resident is None:
            resident = _session_resident()
        if resident is None:
            return {}

        bills = (
            MaintenanceBill.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
            )
            .order_by(MaintenanceBill.billing_month.desc())
            .all()
        )

        pending_bills = [b for b in bills if b.status in ("Pending", "Overdue", "Partially Paid")]
        total_outstanding = sum(b.remaining_amount for b in pending_bills)

        # Latest successful payment
        last_payment = (
            Payment.query.filter(
                Payment.resident_id == resident.id,
                Payment.society_id == resident.society_id,
                Payment.status.in_(["captured", "Success"]),
            )
            .order_by(Payment.payment_date.desc())
            .first()
        )

        # Earliest pending bill = next due
        next_bill = (
            sorted(pending_bills, key=lambda b: b.due_date or b.billing_month)
        )[0] if pending_bills else None

        return {
            "total_bills": len(bills),
            "paid_bills_count": sum(1 for b in bills if b.status == "Paid"),
            "pending_bills_count": len(pending_bills),
            "total_outstanding": round(total_outstanding, 2),
            "advance_balance": round(resident.advance_balance or 0.0, 2),
            "last_payment_date": (
                last_payment.payment_date.strftime("%d %b %Y") if last_payment else None
            ),
            "last_payment_amount": round(last_payment.amount_paid, 2) if last_payment else None,
            "next_due_date": (
                next_bill.due_date.strftime("%d %b %Y")
                if next_bill and next_bill.due_date
                else None
            ),
            "next_due_amount": round(next_bill.remaining_amount, 2) if next_bill else None,
        }

    # ── Dashboard AI summary ───────────────────────────────────────────────

    @classmethod
    def dashboard_summary(cls) -> Dict[str, Any]:
        """
        Returns the financial summary dict plus an ai_message string.
        ai_message is always populated (deterministic fallback if LLM unavailable).
        """
        resident = _session_resident()
        if not resident:
            return {"error": "Authentication required"}

        summary = cls.get_financial_summary(resident)
        outstanding = summary.get("total_outstanding", 0)
        pending_count = summary.get("pending_bills_count", 0)
        last_date = summary.get("last_payment_date")
        next_date = summary.get("next_due_date")

        # Try LLM; fall back to rule-based
        prompt = (
            f"Write ONE friendly sentence (max 20 words) summarising this resident's account. "
            f"Outstanding: ₹{outstanding:.2f}, Pending bills: {pending_count}, "
            f"Last payment: {last_date or 'none'}, Next due: {next_date or 'none'}. "
            f"Be warm. No financial advice. No hallucination."
        )
        ai_msg = _generate(prompt, max_tokens=60, temperature=0.5)

        if ai_msg is None:
            # Deterministic fallback
            if outstanding == 0:
                ai_msg = "Your account is fully up to date — great job!"
            elif pending_count == 1:
                ai_msg = f"You have 1 pending bill totalling {_fmt_money(outstanding)}."
            else:
                ai_msg = (
                    f"You have {pending_count} pending billing periods "
                    f"totalling {_fmt_money(outstanding)}."
                )

        return {**summary, "ai_message": ai_msg, "resident_name": resident.full_name}

    # ── Bill explanation ───────────────────────────────────────────────────

    @classmethod
    def explain_bill(cls, bill_id: int) -> Optional[str]:
        """
        Return a plain-language explanation of a bill.
        Returns None if the bill doesn't belong to the authenticated resident.
        """
        resident = _session_resident()
        if not resident:
            return None

        bill = _verify_owns_bill(bill_id, resident)
        if not bill:
            return None

        # Try LLM
        prompt = (
            f"Explain this maintenance bill in 2-3 plain sentences for a resident. "
            f"Billing month: {bill.billing_month}. "
            f"Base maintenance: {_fmt_money(bill.base_amount)}. "
            f"Late fee: {_fmt_money(bill.late_fee)}. "
            f"Previous balance: {_fmt_money(bill.previous_balance)}. "
            f"Additional charges: {_fmt_money(bill.additional_charges)}. "
            f"Discount: {_fmt_money(bill.discount)}. "
            f"Total: {_fmt_money(bill.total_amount)}. "
            f"Paid so far: {_fmt_money(bill.amount_paid)}. "
            f"Balance due: {_fmt_money(bill.remaining_amount)}. "
            f"Due date: {bill.due_date.strftime('%d %b %Y') if bill.due_date else 'N/A'}. "
            f"Status: {bill.status}. "
            f"Only use these exact numbers. Do not invent values."
        )
        result = _generate(prompt, max_tokens=180, temperature=0.3)

        if result is None:
            # Deterministic fallback
            parts = [f"Your {bill.billing_month} maintenance bill is {_fmt_money(bill.base_amount)}."]
            if bill.late_fee > 0:
                parts.append(f"A late fee of {_fmt_money(bill.late_fee)} has been added.")
            if bill.additional_charges > 0:
                parts.append(f"There are additional charges of {_fmt_money(bill.additional_charges)}.")
            if bill.discount > 0:
                parts.append(f"A discount of {_fmt_money(bill.discount)} has been applied.")
            if bill.amount_paid > 0 and bill.remaining_amount > 0:
                parts.append(
                    f"You have paid {_fmt_money(bill.amount_paid)} so far; "
                    f"{_fmt_money(bill.remaining_amount)} remains due."
                )
            elif bill.remaining_amount == 0:
                parts.append("This bill is fully paid.")
            else:
                parts.append(
                    f"The total amount due is {_fmt_money(bill.remaining_amount)}"
                    + (f", payable by {bill.due_date.strftime('%d %b %Y')}." if bill.due_date else ".")
                )
            result = " ".join(parts)

        return result

    # ── Payment explanation ────────────────────────────────────────────────

    @classmethod
    def explain_payment(cls, payment_id: int) -> Optional[str]:
        """
        Return a plain-language explanation of a payment status.
        Returns None if the payment doesn't belong to the authenticated resident.
        """
        resident = _session_resident()
        if not resident:
            return None

        payment = _verify_owns_payment(payment_id, resident)
        if not payment:
            return None

        status_labels: Dict[str, str] = {
            "created":             "initiated but not yet completed",
            "pending":             "being processed",
            "authorized":          "authorised, awaiting capture",
            "captured":            "successful",
            "failed":              "failed",
            "cancelled":           "cancelled",
            "refunded":            "refunded",
            "partially_refunded":  "partially refunded",
        }
        status_label = status_labels.get(payment.status.lower(), payment.status)

        date_str = (
            payment.payment_date.strftime("%d %b %Y, %I:%M %p")
            if payment.payment_date
            else "unknown date"
        )

        # Try LLM
        prompt = (
            f"Explain in 1-2 plain sentences the status of this payment for a resident. "
            f"Amount: {_fmt_money(payment.amount_paid)}. "
            f"Method: {payment.payment_method or 'online'}. "
            f"Status: {payment.status} ({status_label}). "
            f"Date: {date_str}. "
            f"Webhook verified: {'yes' if payment.webhook_verified else 'no'}. "
            + (f"Failure reason: {payment.failure_reason}. " if payment.failure_reason else "")
            + "Be clear and friendly. Do not invent details."
        )
        result = _generate(prompt, max_tokens=120, temperature=0.3)

        if result is None:
            # Deterministic fallback
            if payment.status == "captured":
                result = (
                    f"Your payment of {_fmt_money(payment.amount_paid)} via "
                    f"{payment.payment_method or 'online'} was successful on {date_str}."
                )
            elif payment.status == "pending":
                if payment.payment_method and payment.payment_method.lower() == "cash":
                    result = (
                        f"Your cash payment of {_fmt_money(payment.amount_paid)} has been "
                        f"submitted on {date_str} and is awaiting Admin verification. "
                        f"It has not yet been marked as completed."
                    )
                else:
                    result = (
                        f"Your payment of {_fmt_money(payment.amount_paid)} is currently "
                        f"being processed. Please check back shortly."
                    )
            elif payment.status == "failed":
                reason = f" Reason: {payment.failure_reason}." if payment.failure_reason else ""
                result = (
                    f"Your payment of {_fmt_money(payment.amount_paid)} on {date_str} "
                    f"was unsuccessful.{reason} Please try again."
                )
            elif payment.status == "cancelled":
                result = (
                    f"Your payment of {_fmt_money(payment.amount_paid)} was cancelled. "
                    f"No amount has been deducted."
                )
            else:
                result = (
                    f"Your payment of {_fmt_money(payment.amount_paid)} has the status: "
                    f"{status_label}."
                )

        return result

    # ── General AI chat ────────────────────────────────────────────────────

    @classmethod
    def chat(cls, question: str) -> str:
        """
        Answer a free-form resident question.
        Always returns a string (never None) — falls back to deterministic
        rule-matching when LLM unavailable.
        """
        resident = _session_resident()
        if not resident:
            return "Please log in to use the AI assistant."

        q = question.strip().lower()

        # ── Try deterministic answers first for common queries ──
        summary = cls.get_financial_summary(resident)
        outstanding = summary.get("total_outstanding", 0)
        pending_count = summary.get("pending_bills_count", 0)
        last_date = summary.get("last_payment_date")
        last_amount = summary.get("last_payment_amount")
        next_date = summary.get("next_due_date")
        next_amount = summary.get("next_due_amount")

        # Outstanding / balance
        if any(w in q for w in ("outstanding", "owe", "pending amount", "balance due", "how much")):
            if outstanding == 0:
                return "You have no outstanding balance. Your account is fully up to date! 🎉"
            return (
                f"You currently have {_fmt_money(outstanding)} outstanding "
                f"across {pending_count} billing period(s)."
            )

        # Next due
        if any(w in q for w in ("next bill", "next due", "when is my", "due date")):
            if next_date and next_amount:
                return f"Your next payment of {_fmt_money(next_amount)} is due on {next_date}."
            return "You have no pending bills at this time."

        # Last payment
        if any(w in q for w in ("last payment", "last paid", "when did i pay", "payment history")):
            if last_date and last_amount:
                return f"Your last payment was {_fmt_money(last_amount)} on {last_date}."
            return "No completed payment records found yet."

        # Overdue
        if any(w in q for w in ("overdue", "late fee", "penalty")):
            overdue_bills = MaintenanceBill.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
                status="Overdue",
            ).all()
            if not overdue_bills:
                return "You have no overdue bills. 🎉"
            total_overdue = sum(b.remaining_amount for b in overdue_bills)
            return (
                f"You have {len(overdue_bills)} overdue bill(s) "
                f"totalling {_fmt_money(total_overdue)}. Please pay as soon as possible to avoid additional late fees."
            )

        # Payment methods
        if any(w in q for w in ("how to pay", "payment method", "how do i pay", "pay online", "upi")):
            return (
                "You can pay your maintenance bill online via UPI, Credit/Debit Card, "
                "or Net Banking through the secure payment gateway on the 'Pay Now' button "
                "on your bill page. Cash payment can also be submitted for Admin verification."
            )

        # Submit a complaint
        if any(w in q for w in ("complaint", "issue", "problem", "report")):
            return (
                "To submit a complaint, click on 'Complaint Desk' in the sidebar. "
                "You can describe the issue and our team will respond promptly. "
                "You can also track the status of existing complaints there."
            )

        # Receipt / download
        if any(w in q for w in ("receipt", "download", "invoice")):
            return (
                "You can view and download all your payment receipts from the "
                "'Receipts' section in the sidebar. Each receipt has a PDF download option."
            )

        # Profile / mobile
        if any(w in q for w in ("profile", "mobile", "phone", "email", "update")):
            return (
                "You can update your profile details from the 'My Profile' section in the sidebar. "
                "To change your mobile number, please contact the society Admin."
            )

        # Contact society / admin
        if any(w in q for w in ("contact", "admin", "office", "society")):
            return (
                "To contact the society administration, visit the 'Help & Support' section "
                "or submit a support request. Emergency contacts are also listed there."
            )

        # Society rules / FAQ
        if any(w in q for w in ("rule", "bylaw", "policy", "parking", "visitor")):
            return (
                "Society rules and policies are published in the 'Announcements' and "
                "'Documents' sections. Please check there for the latest guidelines."
            )

        # Notifications
        if any(w in q for w in ("notification", "alert", "reminder")):
            return (
                "Your notifications are available under the 'Notifications' section. "
                "You can manage notification preferences from 'Preferences' in the sidebar."
            )

        # ── Try LLM for everything else ──
        provider = current_app.config.get("AI_PROVIDER", "deterministic")
        if provider != "deterministic" and current_app.config.get("AI_API_KEY"):
            context_prompt = (
                f"You are an AI assistant for a society management system. "
                f"The resident's name is {resident.full_name}. "
                f"Financial context: outstanding {_fmt_money(outstanding)}, "
                f"pending bills: {pending_count}, "
                f"last payment: {last_date or 'none'}, "
                f"next due: {next_date or 'none'}.\n\n"
                f"Rules:\n"
                f"1. Only answer using the data provided. Do NOT invent amounts or dates.\n"
                f"2. If you don't know, say 'I don't have that information.'\n"
                f"3. Never change bills, payments, or account status.\n"
                f"4. Be friendly and concise (max 3 sentences).\n\n"
                f"Resident question: {question}"
            )
            llm_answer = _generate(context_prompt, max_tokens=200, temperature=0.5)
            if llm_answer:
                return llm_answer

        return (
            "I'm sorry, I don't have enough information to answer that. "
            "Please check your bills, receipts, or notifications in the sidebar, "
            "or contact the society office for assistance."
        )

    # ── Complaint improvement suggestion ──────────────────────────────────

    @classmethod
    def suggest_complaint_improvement(
        cls, title: str, description: str
    ) -> Optional[Dict[str, str]]:
        """
        Suggest an improved title, description, category, and priority.
        The resident must review and confirm before submission.
        Returns None if unauthenticated or AI unavailable.
        Does NOT submit the complaint.
        """
        if not _session_resident():
            return None

        prompt = (
            f"Improve this society complaint submission. Respond in EXACTLY this format:\n"
            f"TITLE: <improved title, max 100 chars>\n"
            f"DESCRIPTION: <improved description, 1-3 sentences>\n"
            f"CATEGORY: <one of: Plumbing, Electrical, Security, Cleaning, Parking, Noise, Maintenance, Other>\n"
            f"PRIORITY: <one of: Low, Normal, High>\n\n"
            f"Original title: {title}\n"
            f"Original description: {description}\n\n"
            f"Keep factual details. Do not invent details. Be professional."
        )
        raw = _generate(prompt, max_tokens=200, temperature=0.4)
        if not raw:
            # Deterministic fallback using keyword classification
            from app.services.ai_service import AIService
            classification = AIService.classify_complaint(title, description)
            return {
                "title": title[:100],
                "description": description,
                "category": classification.get("category", "General Maintenance"),
                "priority": classification.get("priority", "Normal"),
            }

        result: Dict[str, str] = {}
        for line in raw.splitlines():
            for key in ("TITLE", "DESCRIPTION", "CATEGORY", "PRIORITY"):
                if line.upper().startswith(f"{key}:"):
                    result[key.lower()] = line[len(key) + 1:].strip()
        return result if len(result) >= 2 else None

    # ── Notification grouping (presentation layer, read-only) ─────────────

    @classmethod
    def group_notifications(cls, notifications: list) -> Dict[str, list]:
        """
        Group a list of NotificationLog objects by category.
        Pure presentation layer — does NOT modify database records.
        """
        groups: Dict[str, list] = {
            "Payments": [],
            "Maintenance": [],
            "Complaints": [],
            "Society Notices": [],
            "Registration": [],
            "General": [],
        }
        type_to_group = {
            "PAYMENT_SUCCESS": "Payments",
            "PAYMENT_FAILED": "Payments",
            "PAYMENT_PENDING": "Payments",
            "BILL_GENERATED": "Maintenance",
            "DUE_REMINDER": "Maintenance",
            "OVERDUE_REMINDER": "Maintenance",
            "LATE_FEE_NOTICE": "Maintenance",
            "COMPLAINT_UPDATE": "Complaints",
            "COMPLAINT_RESOLVED": "Complaints",
            "NOTICE_PUBLISHED": "Society Notices",
            "EMERGENCY_ALERT": "Society Notices",
            "REGISTRATION_APPROVED": "Registration",
            "REGISTRATION_REJECTED": "Registration",
        }
        for n in notifications:
            group = type_to_group.get(n.notification_type or "", "General")
            groups[group].append(n)
        # Remove empty groups
        return {k: v for k, v in groups.items() if v}

    # ── Quick-action badge counts ──────────────────────────────────────────

    @classmethod
    def quick_action_badges(cls) -> Dict[str, Any]:
        """
        Return badge counts for Resident Quick Actions panel.
        Authenticated resident only. All queries scoped to resident + society.
        """
        resident = _session_resident()
        if not resident:
            return {}

        pending_bills_count = MaintenanceBill.query.filter_by(
            resident_id=resident.id,
            society_id=resident.society_id,
        ).filter(
            MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"])
        ).count()

        open_complaints_count = Complaint.query.filter_by(
            resident_id=resident.id,
            society_id=resident.society_id,
        ).filter(
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
        ).count()

        unread_notifications_count = NotificationLog.query.filter_by(
            user_id=resident.user_id,
            society_id=resident.society_id,
        ).filter(NotificationLog.read_at.is_(None)).count()

        has_outstanding = pending_bills_count > 0
        outstanding_amount = 0.0
        if has_outstanding:
            bills = MaintenanceBill.query.filter_by(
                resident_id=resident.id,
                society_id=resident.society_id,
            ).filter(
                MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"])
            ).all()
            outstanding_amount = round(sum(b.remaining_amount for b in bills), 2)

        return {
            "pending_bills": pending_bills_count,
            "open_complaints": open_complaints_count,
            "unread_notifications": unread_notifications_count,
            "has_outstanding": has_outstanding,
            "outstanding_amount": outstanding_amount,
        }

    # ── AI availability check ─────────────────────────────────────────────

    @staticmethod
    def is_ai_available() -> bool:
        """Return True only if an external LLM is configured and has an API key."""
        provider = current_app.config.get("AI_PROVIDER", "deterministic")
        api_key = current_app.config.get("AI_API_KEY", "")
        return provider not in ("deterministic", "", None) and bool(api_key)
