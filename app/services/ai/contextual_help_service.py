"""
Smart Contextual Help System
============================
Provides instant in-context guidance for every page across resident and admin portals.
Uses deterministic rule templates first (zero API cost per page click), with AI support for ad-hoc queries.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from app.services.ai.provider import AIProviderFactory

logger = logging.getLogger(__name__)


class ContextualHelpService:
    """
    Delivers structured help metadata for resident and admin views:
    - What this page does
    - What the user can do here
    - Important warnings
    - Common actions
    """

    # Comprehensive local rules catalog
    PAGE_HELP_CATALOG: Dict[str, Dict[str, Any]] = {
        "admin_dashboard": {
            "title": "Admin Dashboard",
            "what_this_page_does": "Provides a comprehensive overview of society operations, financial collections, occupancy, and pending actions.",
            "what_you_can_do_here": [
                "Review daily operational metrics (collection totals, pending bills, open tickets).",
                "Toggle 'Focus Mode' to filter down to urgent pending tasks.",
                "Review pending resident registration requests.",
                "Inspect high-risk defaulters and cash verifications.",
            ],
            "important_warnings": [
                "Financial figures reflect posted bills and verified transactions only.",
                "Cash payments require manual verification before receipts are issued.",
            ],
            "common_actions": [
                {"label": "Review Registrations", "url": "/admin/registrations", "icon": "fa-user-check"},
                {"label": "Verify Payments", "url": "/payments/admin_dashboard", "icon": "fa-receipt"},
                {"label": "Generate Bills", "url": "/payments/bills", "icon": "fa-file-invoice-dollar"},
            ],
        },
        "admin_residents": {
            "title": "Residents Directory",
            "what_this_page_does": "Allows managing resident profiles, flat assignments, occupancy statuses, and contact details.",
            "what_you_can_do_here": [
                "Search and filter residents by name, flat, mobile, or ownership type.",
                "View detailed resident ledgers and payment histories.",
                "Update resident details or record approved move-outs.",
                "Add emergency contacts and vehicle registrations.",
            ],
            "important_warnings": [
                "Changing a primary resident updates the billing recipient for that flat.",
                "Never share login credentials or private contact numbers externally.",
            ],
            "common_actions": [
                {"label": "Pending Registrations", "url": "/admin/registrations", "icon": "fa-user-clock"},
                {"label": "Flats Directory", "url": "/admin/flats", "icon": "fa-city"},
                {"label": "Defaulters List", "url": "/reports/defaulters", "icon": "fa-circle-exclamation"},
            ],
        },
        "admin_flats": {
            "title": "Flats & Wings Inventory",
            "what_this_page_does": "Manages structural property units across wings, blocks, floors, and flat numbers.",
            "what_you_can_do_here": [
                "View flat occupancy statuses (Occupied, Vacant, Under Maintenance).",
                "Add new wings, blocks, or individual flat units.",
                "Configure area sqft and unit flat types (1BHK, 2BHK, 3BHK).",
            ],
            "important_warnings": [
                "Flat numbers must be unique within each wing/block.",
                "Deactivating a flat does not delete historical billing records.",
            ],
            "common_actions": [
                {"label": "Manage Residents", "url": "/admin/residents", "icon": "fa-users"},
                {"label": "Maintenance Config", "url": "/payments/bills", "icon": "fa-gears"},
            ],
        },
        "admin_billing": {
            "title": "Maintenance & Invoicing",
            "what_this_page_does": "Manages monthly maintenance bill generation, late fees, custom adjustments, and offline receipts.",
            "what_you_can_do_here": [
                "Generate monthly bills for all active flats in a single batch.",
                "Apply due late fees to overdue accounts.",
                "Record cash / cheque payments received offline.",
                "Download official billing registers.",
            ],
            "important_warnings": [
                "Billing calculations follow the society's configured rule set.",
                "Ensure late fee grace period has elapsed before applying late penalties.",
            ],
            "common_actions": [
                {"label": "Payment Dashboard", "url": "/payments/admin_dashboard", "icon": "fa-credit-card"},
                {"label": "Accounting Ledger", "url": "/accounting/ledger", "icon": "fa-book"},
            ],
        },
    }


    # Additional resident pages catalog
    PAGE_HELP_CATALOG.update({
        "resident_dashboard": {
            "title": "Resident Dashboard",
            "what_this_page_does": "Provides your personal resident overview: outstanding bills, quick payment access, active visitors, and society announcements.",
            "what_you_can_do_here": [
                "Check your current account status and outstanding dues.",
                "Pay maintenance instantly using secure online payment.",
                "View and track open maintenance complaints.",
                "Generate pre-approved visitor passes.",
            ],
            "important_warnings": [
                "Payments made via UPI / Cards reflect immediately upon gateway capture.",
                "Cash payments require admin verification before receipt is active.",
            ],
            "common_actions": [
                {"label": "Pay Now", "url": "/resident/bills", "icon": "fa-credit-card"},
                {"label": "Download Receipts", "url": "/resident/receipts", "icon": "fa-receipt"},
                {"label": "Raise Complaint", "url": "/resident/complaints", "icon": "fa-headset"},
                {"label": "Invite Visitor", "url": "/resident/visitors", "icon": "fa-id-badge"},
            ],
        },
        "resident_bills": {
            "title": "My Maintenance Bills",
            "what_this_page_does": "Lists all monthly maintenance bills issued for your flat, including itemized breakdowns and payment status.",
            "what_you_can_do_here": [
                "Review bill breakdowns (base maintenance, late fees, adjustments).",
                "Pay individual or multiple months together.",
                "View payment confirmation history.",
            ],
            "important_warnings": [
                "Pay on or before the due date to avoid recurring monthly late fee accruals.",
            ],
            "common_actions": [
                {"label": "Payment History", "url": "/payments/payment_history", "icon": "fa-clock-rotate-left"},
                {"label": "Receipts Vault", "url": "/resident/receipts", "icon": "fa-receipt"},
            ],
        },
        "resident_complaints": {
            "title": "Complaint Desk",
            "what_this_page_does": "Allows reporting maintenance issues, plumbing leaks, electrical problems, or facility grievances directly to the admin staff.",
            "what_you_can_do_here": [
                "Submit a new ticket with title, description, category, and priority.",
                "Track live ticket progress from 'Submitted' to 'Assigned' and 'Resolved'.",
                "Add comments or check technician updates.",
            ],
            "important_warnings": [
                "For life-threatening or fire emergencies, immediately contact emergency security services.",
            ],
            "common_actions": [
                {"label": "New Complaint", "url": "/complaints/create", "icon": "fa-plus"},
                {"label": "Emergency Contacts", "url": "/resident/help_center", "icon": "fa-phone"},
            ],
        },
        "data_quality": {
            "title": "Data Quality Center",
            "what_this_page_does": "Audits society records for anomalies, duplicate entries, invalid contact formats, and orphaned relationships.",
            "what_you_can_do_here": [
                "Scan database for duplicate residents, flats, and invalid emails/mobiles.",
                "Inspect suggested fixes before making updates.",
                "Export data health diagnostic reports.",
            ],
            "important_warnings": [
                "Data quality center is read-only. Database records are never modified automatically.",
            ],
            "common_actions": [
                {"label": "Residents Directory", "url": "/admin/residents", "icon": "fa-users"},
                {"label": "Flats Directory", "url": "/admin/flats", "icon": "fa-city"},
            ],
        },
        "system_health": {
            "title": "Application Health & Monitoring",
            "what_this_page_does": "Monitors backend database performance, scheduled automation jobs, webhook integrity, and error patterns.",
            "what_you_can_do_here": [
                "Inspect real-time database connectivity and table counts.",
                "Monitor scheduled jobs and execution timestamps.",
                "Review recent error patterns and webhook delivery timelines.",
            ],
            "important_warnings": [
                "All health checks are read-only diagnostics.",
            ],
            "common_actions": [
                {"label": "Automation Engine", "url": "/admin/automation", "icon": "fa-robot"},
                {"label": "Backups", "url": "/system/backups", "icon": "fa-server"},
            ],
        },
    })

    @classmethod
    def get_help_for_page(cls, page_key: str) -> Dict[str, Any]:
        """Retrieves structured help for the given page context."""
        cleaned_key = page_key.lower().strip().replace("/", "_").replace("-", "_")

        # Direct match or best prefix match
        if cleaned_key in cls.PAGE_HELP_CATALOG:
            return cls.PAGE_HELP_CATALOG[cleaned_key]

        for k, v in cls.PAGE_HELP_CATALOG.items():
            if k in cleaned_key or cleaned_key in k:
                return v

        # Fallback general guide
        return {
            "title": "Contextual Guidance",
            "what_this_page_does": "This page allows managing society operations, residents, or personal account features.",
            "what_you_can_do_here": [
                "Review presented records and statistics.",
                "Use the search and filter bar to locate specific entries.",
                "Use the action buttons to trigger safe operations.",
            ],
            "important_warnings": [
                "Ensure all form fields are validated before submission.",
            ],
            "common_actions": [
                {"label": "Dashboard", "url": "/dashboard", "icon": "fa-house"},
            ],
        }

    @classmethod
    def answer_contextual_question(cls, page_key: str, question: str) -> str:
        """Answers an ad-hoc question about a page, using local rules first, then AI provider."""
        help_data = cls.get_help_for_page(page_key)
        q_lower = question.lower()

        # Deterministic instant answers
        if any(w in q_lower for w in ["what does this page do", "what is this", "purpose"]):
            return help_data["what_this_page_does"]
        if any(w in q_lower for w in ["what can i do", "how to use", "actions"]):
            return "On this page, you can: " + "; ".join(help_data["what_you_can_do_here"])
        if any(w in q_lower for w in ["warning", "careful", "danger", "precaution"]):
            return "Important: " + "; ".join(help_data["important_warnings"])

        # Try active AI provider
        provider = AIProviderFactory.get_provider()
        prompt = (
            f"You are a helpful assistant for a society management platform. "
            f"The user is viewing the '{help_data['title']}' page.\n"
            f"Context: {help_data['what_this_page_does']}\n"
            f"Capabilities: {', '.join(help_data['what_you_can_do_here'])}\n"
            f"Warnings: {', '.join(help_data['important_warnings'])}\n"
            f"User question: {question}\n"
            f"Provide a friendly, concise answer (max 2 sentences)."
        )
        ai_resp = provider.generate(prompt, max_tokens=150, temperature=0.3)
        return ai_resp or help_data["what_this_page_does"]
