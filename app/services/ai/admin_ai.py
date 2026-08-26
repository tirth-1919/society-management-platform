"""
Admin Productivity & Safety AI Services
=======================================
Provides Admin Work Queue, Admin Focus Mode, Safe Bulk Action Guard, and Record Change Preview.
Ensures safety rules: AI recommends and audits, human admin confirms critical changes.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Set

from app.models import (
    RegistrationRequest,
    Payment,
    Complaint,
    PaymentReconciliationIssue,
    InventoryItem,
    Asset,
    AutomationFailure,
    WebhookLog,
    AuditLog,
    Resident,
    MaintenanceBill,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class AdminWorkQueueService:
    """
    Admin Work Queue Engine:
    Generates a prioritized, deduplicated queue from live operational data.
    Structure:
    {
        "type": "...",
        "title": "...",
        "priority": "low|medium|high|critical",
        "reason": "...",
        "url": "...",
        "created_at": "..."
    }
    """

    @classmethod
    def get_work_queue(cls, society_id: int) -> List[Dict[str, Any]]:
        tasks: List[Dict[str, Any]] = []
        now = utcnow()

        # 1. Pending resident registration requests
        pending_regs = RegistrationRequest.query.filter_by(
            society_id=society_id, status="PENDING_APPROVAL"
        ).order_by(RegistrationRequest.created_at.asc()).all()

        for reg in pending_regs:
            tasks.append({
                "type": "registration_approval",
                "title": f"Approve Registration: {reg.full_name}",
                "priority": "high",
                "reason": f"Resident submitted registration for Flat {reg.flat.flat_number if reg.flat else 'unassigned'}.",
                "url": f"/admin/registrations/{reg.id}",
                "created_at": reg.created_at.isoformat() if reg.created_at else now.isoformat(),
                "action_label": "Review Registration",
                "id": f"reg_{reg.id}",
            })

        # 2. Unverified cash payments
        unverified_cash = Payment.query.filter_by(
            society_id=society_id, payment_method="Cash", status="pending"
        ).order_by(Payment.payment_date.asc()).all()

        for p in unverified_cash:
            tasks.append({
                "type": "cash_verification",
                "title": f"Verify Cash Payment: ₹{p.amount_paid:,.2f} from {p.resident.full_name if p.resident else 'Resident'}",
                "priority": "high",
                "reason": f"Cash collection on {p.payment_date.strftime('%d %b') if p.payment_date else 'recently'} awaiting receipt confirmation.",
                "url": "/payments/admin_dashboard",
                "created_at": p.payment_date.isoformat() if p.payment_date else now.isoformat(),
                "action_label": "Verify & Generate Receipt",
                "id": f"pay_{p.id}",
            })

        # 3. Emergency and critical unresolved complaints
        urgent_complaints = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        ).order_by(Complaint.created_at.asc()).all()

        for c in urgent_complaints:
            is_emergency = c.priority in ["Emergency", "Critical"]
            tasks.append({
                "type": "complaint_resolution",
                "title": f"{'🚨 ' if is_emergency else ''}Complaint #{c.id}: {c.title}",
                "priority": "critical" if is_emergency else ("high" if c.priority == "High" else "medium"),
                "reason": f"Category: {c.category} | Status: {c.status} | Reported by {c.resident.full_name if c.resident else 'Resident'}",
                "url": f"/complaints/{c.id}",
                "created_at": c.created_at.isoformat() if c.created_at else now.isoformat(),
                "action_label": "Assign / Resolve",
                "id": f"comp_{c.id}",
            })


        # 4. Open reconciliation issues
        recon_issues = PaymentReconciliationIssue.query.filter_by(
            society_id=society_id, status="OPEN"
        ).order_by(PaymentReconciliationIssue.detected_at.asc()).all()

        for r in recon_issues:
            tasks.append({
                "type": "payment_reconciliation",
                "title": f"Reconciliation Issue: {r.issue_type}",
                "priority": "high" if r.severity in ["CRITICAL", "HIGH"] else "medium",
                "reason": r.description or "Discrepancy detected in ledger/payment matching.",
                "url": "/admin/reconciliation",
                "created_at": r.detected_at.isoformat() if r.detected_at else now.isoformat(),
                "action_label": "Review & Resolve",
                "id": f"recon_{r.id}",
            })

        # 5. Low stock inventory items
        low_stock = InventoryItem.query.filter(
            InventoryItem.society_id == society_id,
            InventoryItem.current_stock <= InventoryItem.minimum_threshold,
        ).all()

        for item in low_stock:
            is_zero = item.current_stock == 0
            tasks.append({
                "type": "inventory_restock",
                "title": f"Low Stock: {item.item_name} ({item.current_stock} {item.unit or 'units'} left)",
                "priority": "high" if is_zero else "medium",
                "reason": f"Current stock is at or below threshold ({item.minimum_threshold} {item.unit or 'units'}).",
                "url": "/operations/inventory",
                "created_at": now.isoformat(),
                "action_label": "Order Stock",
                "id": f"inv_{item.id}",
            })

        # 6. Expiring AMC / Warranties (within 14 days)
        threshold_date = now.date() + timedelta(days=14)
        expiring_assets = Asset.query.filter(
            Asset.society_id == society_id,
            Asset.warranty_expiry.isnot(None),
            Asset.warranty_expiry <= threshold_date,
            Asset.warranty_expiry >= now.date(),
        ).all()

        for asset in expiring_assets:
            days = (asset.warranty_expiry - now.date()).days
            tasks.append({
                "type": "asset_warranty_expiry",
                "title": f"Warranty Expiring: {asset.asset_name}",
                "priority": "high" if days <= 3 else "low",
                "reason": f"Warranty expires in {days} day(s) on {asset.warranty_expiry.strftime('%d %b %Y')}.",
                "url": "/operations/assets",
                "created_at": now.isoformat(),
                "action_label": "Renew Warranty",
                "id": f"asset_{asset.id}",
            })

        # Sort tasks by priority (critical -> high -> medium -> low) and created_at
        prio_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        tasks.sort(key=lambda t: (prio_map.get(t.get("priority", "medium").lower(), 2), t.get("created_at", "")))

        return tasks


class AdminFocusModeService:
    """
    Admin Focus Mode:
    Filters the admin dashboard down to urgent, actionable work items only.
    Shows high-priority work, pending approvals, failed operations, important alerts,
    unresolved issues, and recently changed records.
    """

    @classmethod
    def get_focus_data(cls, society_id: int) -> Dict[str, Any]:
        all_tasks = AdminWorkQueueService.get_work_queue(society_id)
        high_priority_work = [t for t in all_tasks if t.get("priority") in ["critical", "high"]]

        # Failed operations in last 7 days
        week_ago = utcnow() - timedelta(days=7)
        failed_automations = AutomationFailure.query.filter(
            AutomationFailure.society_id == society_id,
            AutomationFailure.created_at >= week_ago,
            AutomationFailure.resolved_at.is_(None),
        ).count()

        failed_webhooks = WebhookLog.query.filter(
            WebhookLog.signature_verified.is_(False),
            WebhookLog.processed_at >= week_ago,
        ).count()

        # Recently changed records from AuditLog
        recent_changes = AuditLog.query.filter_by(society_id=society_id).order_by(
            AuditLog.created_at.desc()
        ).limit(10).all()

        recent_records = [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "user": log.user.full_name if log.user else "System",
                "timestamp": log.created_at.strftime("%d %b %Y, %I:%M %p") if log.created_at else "N/A",
            }
            for log in recent_changes
        ]

        return {
            "focus_mode_active": True,
            "total_action_items": len(high_priority_work),
            "high_priority_work": high_priority_work,
            "failed_operations_count": failed_automations + failed_webhooks,
            "failed_automations_count": failed_automations,
            "failed_webhooks_count": failed_webhooks,
            "recent_changed_records": recent_records,
            "pending_approvals_count": sum(1 for t in high_priority_work if t["type"] in ["registration_approval", "cash_verification"]),
        }


class SafeBulkActionGuard:
    """
    Safe Bulk Action Guard:
    Evaluates requested bulk operations, warns about large batches,
    provides item counts and preview, and enforces explicit human confirmation.
    """

    LARGE_THRESHOLD = 10

    @classmethod
    def inspect_bulk_action(
        cls,
        action_type: str,
        target_ids: List[int],
        society_id: int,
    ) -> Dict[str, Any]:
        count = len(target_ids)
        is_large = count >= cls.LARGE_THRESHOLD

        destructive_actions = {
            "bulk_delete_residents",
            "bulk_cancel_bills",
            "bulk_move_out",
            "bulk_deactivate_flats",
        }
        is_destructive = action_type in destructive_actions

        preview_items: List[Dict[str, Any]] = []

        if action_type in ["bulk_generate_bills", "bulk_send_reminders"]:
            residents = Resident.query.filter(
                Resident.society_id == society_id,
                Resident.id.in_(target_ids),
            ).limit(5).all()
            preview_items = [{"id": r.id, "name": r.full_name, "flat": r.flat.flat_number if r.flat else "N/A"} for r in residents]
        elif action_type in ["bulk_cancel_bills", "bulk_apply_late_fees"]:
            bills = MaintenanceBill.query.filter(
                MaintenanceBill.society_id == society_id,
                MaintenanceBill.id.in_(target_ids),
            ).limit(5).all()
            preview_items = [{"id": b.id, "bill_number": b.bill_number, "amount": b.total_amount, "month": b.billing_month} for b in bills]

        warning_message = None
        if is_large:
            warning_message = f"Notice: {count} records will be affected by this operation."

        return {
            "action_type": action_type,
            "affected_count": count,
            "is_large_selection": is_large,
            "is_destructive": is_destructive,
            "requires_confirmation": is_destructive or is_large,
            "warning_message": warning_message,
            "preview_items": preview_items,
            "preview_total": count,
            "confirmation_keyword": "CONFIRM" if is_destructive else None,
        }


class RecordChangePreviewService:
    """
    Record Change Preview:
    Computes field-by-field diff (Before vs After) for admin updates.
    Masks sensitive values (passwords, 2FA keys, webhook secrets).
    """

    SENSITIVE_FIELDS = {
        "password",
        "password_hash",
        "two_factor_secret",
        "secret",
        "token",
        "api_key",
        "card_number",
        "cvv",
    }

    @classmethod
    def generate_diff(
        cls,
        entity_name: str,
        before_dict: Dict[str, Any],
        after_dict: Dict[str, Any],
        masked_keys: Optional[Set[str]] = None,
    ) -> List[Dict[str, Any]]:
        diffs: List[Dict[str, Any]] = []
        mask_set = cls.SENSITIVE_FIELDS | (masked_keys or set())

        all_keys = set(before_dict.keys()) | set(after_dict.keys())

        for key in sorted(all_keys):
            if key in mask_set or key.startswith("_"):
                continue

            val_before = before_dict.get(key)
            val_after = after_dict.get(key)

            # Compare stringified / normalized forms
            if str(val_before or "").strip() != str(val_after or "").strip():
                # Pretty print field label
                field_label = key.replace("_", " ").title()
                diffs.append({
                    "field": field_label,
                    "field_key": key,
                    "before": str(val_before) if val_before is not None else "(empty)",
                    "after": str(val_after) if val_after is not None else "(empty)",
                })

        return diffs
