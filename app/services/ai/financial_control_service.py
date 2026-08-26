"""
AI Financial Control System
===========================
Read-only financial intelligence analyzing payments, maintenance bills, expense vouchers,
refund requests, vendor invoices, and account ledgers.
Detects duplicates, statistical expense outliers, refund clusters, and collection trends.
"""

from __future__ import annotations

import logging
import statistics
from collections import defaultdict
from typing import Any, Optional

from app.models.tenant import db
from app.models.payment import Payment, RefundRequest
from app.models.billing import MaintenanceBill
from app.models.accounting import ExpenseVoucher
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.services.ai.ai_audit_service import AIAuditService

logger = logging.getLogger(__name__)


class FinancialControlAIService:
    @classmethod
    def scan_financial_anomalies(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Scans payments, vouchers, and refunds for statistical anomalies and duplicates.
        Strictly read-only; no database mutation of accounting or billing records.
        """
        anomalies = []

        # 1. Detect Duplicate Payments (Multiple successful/pending payments on same bill)
        payments = Payment.query.filter_by(society_id=society_id).order_by(Payment.payment_date.desc()).all()
        bill_payments = defaultdict(list)
        for p in payments:
            bill_payments[p.bill_id].append(p)

        for bill_id, pay_list in bill_payments.items():
            if len(pay_list) > 1:
                completed = [p for p in pay_list if p.status in ["captured", "success", "SUCCESS", "CAPTURED"]]
                if len(completed) > 1:
                    anomalies.append({
                        "type": "DUPLICATE_PAYMENT_DETECTED",
                        "severity": AIFindingSeverity.HIGH,
                        "confidence": 0.96,
                        "title": f"Multiple Successful Payments on Bill #{bill_id}",
                        "summary": f"Detected {len(completed)} captured payments associated with Maintenance Bill #{bill_id}. Total amount ₹{sum(p.amount_paid for p in completed):,.2f}.",
                        "evidence": {
                            "bill_id": bill_id,
                            "transaction_ids": [p.transaction_id for p in completed],
                            "amounts": [p.amount_paid for p in completed],
                            "dates": [p.payment_date.isoformat() if p.payment_date else None for p in completed],
                        },
                        "recommended_action": "Verify bank statement and issue refund if an accidental double-charge occurred.",
                        "entity_type": "PAYMENT",
                        "entity_id": completed[0].id,
                    })

        # 2. Detect Potential Duplicate Invoices / Expense Vouchers
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).order_by(ExpenseVoucher.expense_date.desc()).all()
        inv_map = defaultdict(list)
        for v in vouchers:
            if v.invoice_number and v.invoice_number.strip():
                inv_map[v.invoice_number.strip().upper()].append(v)

        for inv_no, v_list in inv_map.items():
            if len(v_list) > 1:
                anomalies.append({
                    "type": "DUPLICATE_INVOICE_NUMBER",
                    "severity": AIFindingSeverity.HIGH,
                    "confidence": 0.98,
                    "title": f"Duplicate Invoice Number Detected: {inv_no}",
                    "summary": f"Invoice number '{inv_no}' is attached to {len(v_list)} separate expense vouchers (#{', #'.join(str(v.id) for v in v_list)}).",
                    "evidence": {
                        "invoice_number": inv_no,
                        "voucher_ids": [v.id for v in v_list],
                        "amounts": [v.amount for v in v_list],
                        "payees": [v.payee_name for v in v_list],
                    },
                    "recommended_action": "Review voucher records to confirm if this is an unintentional double-entry.",
                    "entity_type": "INVOICE",
                    "entity_id": v_list[0].id,
                })

        # 3. Detect Category Expense Outliers (>2.5x Mean)
        by_category = defaultdict(list)
        for v in vouchers:
            by_category[v.category].append(v.amount)

        for cat, amounts in by_category.items():
            if len(amounts) >= 3:
                avg_amt = statistics.mean(amounts)
                stdev_amt = statistics.stdev(amounts) if len(amounts) > 1 else 0
                threshold = avg_amt + (2.5 * (stdev_amt or (avg_amt * 0.5)))
                for v in vouchers:
                    if v.category == cat and v.amount > threshold and v.amount > 10000:
                        anomalies.append({
                            "type": "UNUSUAL_EXPENSE_AMOUNT",
                            "severity": AIFindingSeverity.MEDIUM,
                            "confidence": 0.88,
                            "title": f"Unusual Expense Spike in {cat}: ₹{v.amount:,.2f}",
                            "summary": f"Expense voucher #{v.voucher_number} (₹{v.amount:,.2f}) for '{v.payee_name}' is significantly above category baseline (Category Avg: ₹{avg_amt:,.2f}).",
                            "evidence": {
                                "voucher_number": v.voucher_number,
                                "amount": v.amount,
                                "category_average": round(avg_amt, 2),
                                "category": cat,
                                "payee": v.payee_name,
                            },
                            "recommended_action": "Audit vendor quote and invoice itemization for this high-value voucher.",
                            "entity_type": "EXPENSE_VOUCHER",
                            "entity_id": v.id,
                        })

        # 4. Detect Repeated Refund Velocity
        refunds = RefundRequest.query.filter_by(society_id=society_id).order_by(RefundRequest.created_at.desc()).all()
        resident_refunds = defaultdict(list)
        for r in refunds:
            if r.resident_id:
                resident_refunds[r.resident_id].append(r)

        for res_id, r_list in resident_refunds.items():
            if len(r_list) >= 3:
                anomalies.append({
                    "type": "REPEATED_REFUND_REQUESTS",
                    "severity": AIFindingSeverity.MEDIUM,
                    "confidence": 0.90,
                    "title": f"Elevated Refund Frequency for Resident #{res_id}",
                    "summary": f"Detected {len(r_list)} refund claims submitted by Resident #{res_id} totaling ₹{sum(r.requested_amount for r in r_list):,.2f}.",
                    "evidence": {
                        "resident_id": res_id,
                        "refund_count": len(r_list),
                        "total_requested": sum(r.requested_amount for r in r_list),
                    },
                    "recommended_action": "Review resident billing history to verify recurring discrepancy source.",
                    "entity_type": "RESIDENT",
                    "entity_id": res_id,
                })

        # Sync findings
        for item in anomalies:
            finding = AIFinding.query.filter_by(
                society_id=society_id,
                ai_system=AISystemType.FINANCE,
                finding_type=item["type"],
                entity_id=item["entity_id"],
            ).filter(AIFinding.status.in_([AIFindingStatus.NEW, AIFindingStatus.REVIEWING])).first()

            if not finding:
                finding = AIFinding(
                    society_id=society_id,
                    ai_system=AISystemType.FINANCE,
                    entity_type=item["entity_type"],
                    entity_id=item["entity_id"],
                    finding_type=item["type"],
                    severity=item["severity"],
                    confidence_score=item["confidence"],
                    title=item["title"],
                    summary=item["summary"],
                    recommended_action=item["recommended_action"],
                    status=AIFindingStatus.NEW,
                )
                finding.set_evidence(item["evidence"])
                db.session.add(finding)

        db.session.commit()

        if actor_id:
            AIAuditService.log_event(
                society_id=society_id,
                action="FINANCE_SCAN",
                entity_type="FINANCE_SCAN",
                actor_id=actor_id,
                details={"anomalies_detected": len(anomalies)},
            )

        return anomalies

    @classmethod
    def get_financial_trends(cls, society_id: int) -> dict[str, Any]:
        """
        Calculates high-level read-only financial trends from real database data.
        """
        bills = MaintenanceBill.query.filter_by(society_id=society_id).all()
        payments = Payment.query.filter_by(society_id=society_id).filter(
            Payment.status.in_(["captured", "success", "SUCCESS", "CAPTURED"])
        ).all()
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).all()
        refunds = RefundRequest.query.filter_by(society_id=society_id).all()

        total_billed = sum(b.total_amount for b in bills)
        total_collected = sum(p.amount_paid for p in payments)
        pending_maintenance = sum(b.remaining_amount for b in bills if b.status in ["Pending", "Overdue", "Partially Paid"])
        total_expenses = sum(v.amount for v in vouchers)
        total_refunds = sum(r.requested_amount for r in refunds if r.status in ["approved", "completed", "APPROVED", "COMPLETED"])

        collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0.0

        # Expenses by category
        cat_breakdown = defaultdict(float)
        for v in vouchers:
            cat_breakdown[v.category] += v.amount

        return {
            "total_billed": round(total_billed, 2),
            "total_collected": round(total_collected, 2),
            "pending_maintenance": round(pending_maintenance, 2),
            "total_expenses": round(total_expenses, 2),
            "total_refunds": round(total_refunds, 2),
            "collection_rate_pct": round(collection_rate, 1),
            "expense_by_category": dict(cat_breakdown),
            "bills_count": len(bills),
            "payments_count": len(payments),
        }
