"""
AI Fraud Investigation System
=============================
Admin-only investigation workspace and multi-vector risk engine.
Analyzes anomalies across payments, vouchers, vendors, and visitor access
using strictly neutral, objective review language ("Potential Risk", "Potential Anomaly").
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.models.tenant import db
from app.models.payment import RefundRequest
from app.models.accounting import ExpenseVoucher
from app.models.ai_operations import (
    AIInvestigation,
    AIFindingSeverity,
)
from app.services.ai.ai_audit_service import AIAuditService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class FraudInvestigationAIService:
    @classmethod
    def generate_case_id(cls, society_id: int) -> str:
        """
        Generates unique case identifier (e.g. INV-2026-0042).
        """
        year = utcnow().year
        count = AIInvestigation.query.filter_by(society_id=society_id).count() + 1
        return f"INV-{year}-{count:04d}"

    @classmethod
    def scan_for_investigation_triggers(cls, society_id: int, actor_id: Optional[int] = None) -> list[AIInvestigation]:
        """
        Correlates anomalies across payments, vendors, and refunds to trigger formal investigation cases.
        """
        created_cases = []

        # 1. Vendor & Expense Anomaly Check (Multiple high vouchers with duplicate invoice hints)
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).order_by(ExpenseVoucher.expense_date.desc()).all()
        by_payee = {}
        for v in vouchers:
            if v.payee_name not in by_payee:
                by_payee[v.payee_name] = []
            by_payee[v.payee_name].append(v)

        for payee, v_list in by_payee.items():
            if len(v_list) >= 3:
                total_amt = sum(v.amount for v in v_list)
                duplicate_invs = len({v.invoice_number for v in v_list if v.invoice_number}) < len(v_list)
                if duplicate_invs and total_amt > 25000:
                    case_title = f"Potential Invoice Discrepancy: {payee}"
                    existing = AIInvestigation.query.filter_by(society_id=society_id, title=case_title).first()
                    if not existing:
                        cid = cls.generate_case_id(society_id)
                        inv = AIInvestigation(
                            case_id=cid,
                            society_id=society_id,
                            title=case_title,
                            summary=f"Detected multiple expense vouchers totaling ₹{total_amt:,.2f} with repeated invoice numbers for payee '{payee}'.",
                            category="VENDOR_IRREGULARITY",
                            risk_score=78.5,
                            severity=AIFindingSeverity.HIGH,
                            status="OPEN",
                            created_by_id=actor_id,
                        )
                        timeline = [
                            {"timestamp": v.expense_date.isoformat() if v.expense_date else str(utcnow().date()), "event": f"Voucher #{v.voucher_number} recorded (₹{v.amount:,.2f}) with Invoice #{v.invoice_number}"}
                            for v in v_list
                        ]
                        inv.set_timeline(timeline)
                        inv.set_related_entities({"vendor": payee, "voucher_ids": [v.id for v in v_list], "total_amount": total_amt})
                        db.session.add(inv)
                        created_cases.append(inv)

        # 2. Refund Clustering Check
        refunds = RefundRequest.query.filter_by(society_id=society_id).all()
        if len(refunds) >= 4:
            case_title = "Elevated Refund Volume Requiring Administrative Review"
            existing = AIInvestigation.query.filter_by(society_id=society_id, title=case_title).first()
            if not existing:
                cid = cls.generate_case_id(society_id)
                inv = AIInvestigation(
                    case_id=cid,
                    society_id=society_id,
                    title=case_title,
                    summary=f"Detected {len(refunds)} payment refund submissions totaling ₹{sum(r.requested_amount for r in refunds):,.2f}.",
                    category="FINANCIAL_FRAUD",
                    risk_score=68.0,
                    severity=AIFindingSeverity.MEDIUM,
                    status="OPEN",
                    created_by_id=actor_id,
                )
                inv.set_timeline([{"timestamp": r.created_at.isoformat() if r.created_at else str(utcnow().date()), "event": f"Refund #{r.id} requested for ₹{r.requested_amount:,.2f}"} for r in refunds[:10]])
                inv.set_related_entities({"refund_ids": [r.id for r in refunds]})
                db.session.add(inv)
                created_cases.append(inv)

        db.session.commit()
        return created_cases

    @classmethod
    def update_case_status(
        cls, case_id_or_pk: Any, society_id: int, actor_id: int, status: str, admin_notes: Optional[str] = None
    ) -> AIInvestigation:
        """
        Updates investigation case status (OPEN, UNDER_REVIEW, CONFIRMED, DISMISSED, RESOLVED).
        """
        if isinstance(case_id_or_pk, int):
            inv = AIInvestigation.query.filter_by(id=case_id_or_pk, society_id=society_id).first()
        else:
            inv = AIInvestigation.query.filter_by(case_id=str(case_id_or_pk), society_id=society_id).first()

        if not inv:
            raise ValueError(f"Investigation case '{case_id_or_pk}' not found.")

        old_status = inv.status
        inv.status = status
        if admin_notes:
            existing_notes = inv.admin_notes or ""
            timestamp_note = f"[{utcnow().strftime('%Y-%m-%d %H:%M')}] {admin_notes}"
            inv.admin_notes = f"{existing_notes}\n{timestamp_note}".strip()

        if status in ["CONFIRMED", "DISMISSED", "RESOLVED"]:
            inv.closed_at = utcnow()

        # Add event to timeline
        timeline = inv.get_timeline()
        timeline.append({
            "timestamp": utcnow().isoformat(),
            "event": f"Status changed from {old_status} to {status} by Admin #{actor_id}",
        })
        inv.set_timeline(timeline)

        db.session.commit()

        AIAuditService.log_event(
            society_id=society_id,
            action="INVESTIGATION_STATUS_UPDATE",
            entity_type="AI_INVESTIGATION",
            entity_id=inv.id,
            actor_id=actor_id,
            details={"case_id": inv.case_id, "old_status": old_status, "new_status": status},
        )
        return inv
