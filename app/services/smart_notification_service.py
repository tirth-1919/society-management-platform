"""
SmartNotificationService
========================
Presentation-layer grouping and alerting for NotificationLog records.

RULES:
- Read-only: never creates, modifies, or deletes NotificationLog rows.
- Resident-scoped: every method takes (user_id, society_id) from the
  server-side session, never from request bodies.
- Deduplication: uses the existing unique constraint
  (user_id, billing_month, notification_type) for cooldown checks.
"""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.models import (
    MaintenanceBill,
    NotificationLog,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Maps notification_type values → display category
_TYPE_TO_CATEGORY: Dict[str, str] = {
    # Payments
    "PAYMENT_SUCCESS":      "Payments",
    "PAYMENT_FAILED":       "Payments",
    "PAYMENT_PENDING":      "Payments",
    "CASH_VERIFICATION":    "Payments",
    "REFUND":               "Payments",
    # Maintenance
    "BILL_GENERATED":       "Maintenance",
    "DUE_REMINDER":         "Maintenance",
    "OVERDUE_REMINDER":     "Maintenance",
    "LATE_FEE_NOTICE":      "Maintenance",
    "ESCALATION_NOTICE":    "Maintenance",
    "BILLING_NOTICE":       "Maintenance",
    # Complaints
    "COMPLAINT_UPDATE":     "Complaints",
    "COMPLAINT_RESOLVED":   "Complaints",
    "COMPLAINT_ASSIGNED":   "Complaints",
    # Notices / society
    "NOTICE_PUBLISHED":     "Society Notices",
    "EMERGENCY_ALERT":      "Society Notices",
    "ANNOUNCEMENT":         "Society Notices",
    # Registration / account
    "REGISTRATION_APPROVED": "Registration",
    "REGISTRATION_REJECTED":  "Registration",
    "ACCOUNT_STATUS":         "Registration",
    "ACCOUNT_UPDATE":         "Registration",
}

_ALL_CATEGORIES = [
    "Payments",
    "Maintenance",
    "Complaints",
    "Society Notices",
    "Registration",
    "General",
]


def _category(notification_type: Optional[str]) -> str:
    return _TYPE_TO_CATEGORY.get((notification_type or "").upper(), "General")


# ---------------------------------------------------------------------------
# SmartNotificationService
# ---------------------------------------------------------------------------

class SmartNotificationService:
    """Read-only presentation layer on top of NotificationLog."""

    # ── Grouping ─────────────────────────────────────────────────────────

    @staticmethod
    def group(notifications: list) -> Dict[str, Any]:
        """
        Group a flat list of NotificationLog ORM objects into category buckets.

        Returns:
        {
          "groups": { "Payments": [...], "Maintenance": [...], ... },
          "category_counts": { "Payments": 3, ... },
          "total": 12,
          "unread": 4,
          "all_categories": ["Payments", ...]
        }
        Every entry in a bucket is a lightweight dict (no ORM objects).
        """
        buckets: Dict[str, List[Dict]] = {c: [] for c in _ALL_CATEGORIES}
        total_unread = 0

        for n in notifications:
            ntype  = (getattr(n, "notification_type", None) or "").upper()
            cat    = _category(ntype)
            unread = getattr(n, "read_at", None) is None
            if unread:
                total_unread += 1

            entry = {
                "id":                n.id,
                "subject":           getattr(n, "subject", None),
                "message":           n.message,
                "notification_type": n.notification_type,
                "billing_month":     getattr(n, "billing_month", None),
                "channel":           getattr(n, "channel", "In-App"),
                "sent_at": (
                    n.sent_at.strftime("%d %b %Y, %I:%M %p")
                    if getattr(n, "sent_at", None) else None
                ),
                "created_at": (
                    n.created_at.strftime("%d %b %Y, %I:%M %p")
                    if getattr(n, "created_at", None) else None
                ),
                "is_unread": unread,
                "category":  cat,
            }
            buckets[cat].append(entry)

        non_empty = {k: v for k, v in buckets.items() if v}
        return {
            "groups":          non_empty,
            "category_counts": {k: len(v) for k, v in buckets.items()},
            "total":           len(notifications),
            "unread":          total_unread,
            "all_categories":  _ALL_CATEGORIES,
        }

    # ── Smart Alerts (prominent banners for resident dashboard) ──────────

    @staticmethod
    def build_smart_alerts(
        user_id: int,
        society_id: int,
        resident_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Return a deduplicated list of high-priority alert dicts for the
        resident dashboard banner area.

        Each alert:
        {
          "level":   "danger" | "warning" | "info" | "success",
          "icon":    "fa-solid fa-...",
          "title":   "Payment Failed",
          "message": "...",
          "action_url": "/payments/...",
          "action_label": "Retry"
        }

        Pure read — no DB writes.
        """
        alerts: List[Dict[str, Any]] = []
        seen: set = set()

        def _add(key: str, alert: Dict) -> None:
            if key not in seen:
                seen.add(key)
                alerts.append(alert)

        # ── 1. Failed payments ────────────────────────────────────────────
        from app.models import Payment
        failed_payments = (
            Payment.query.filter_by(
                resident_id=resident_id,
                society_id=society_id,
                status="failed",
            )
            .order_by(Payment.payment_date.desc())
            .limit(3)
            .all()
        ) if resident_id else []

        for p in failed_payments:
            _add(f"pay_fail_{p.id}", {
                "level":        "danger",
                "icon":         "fa-solid fa-xmark-circle",
                "title":        "Payment Failed",
                "message":      (
                    f"Payment of ₹{p.amount_paid:,.2f} on "
                    f"{p.payment_date.strftime('%d %b') if p.payment_date else 'unknown date'} "
                    f"was unsuccessful."
                    + (f" {p.failure_reason}" if p.failure_reason else "")
                ),
                "action_url":   None,
                "action_label": None,
            })

        # ── 2. Pending cash verification ──────────────────────────────────
        pending_cash = (
            Payment.query.filter_by(
                resident_id=resident_id,
                society_id=society_id,
                payment_method="Cash",
                status="pending",
            )
            .order_by(Payment.payment_date.desc())
            .limit(2)
            .all()
        ) if resident_id else []

        for p in pending_cash:
            _add(f"cash_pend_{p.id}", {
                "level":        "warning",
                "icon":         "fa-solid fa-clock",
                "title":        "Cash Payment Pending Verification",
                "message":      (
                    f"Your cash payment of ₹{p.amount_paid:,.2f} on "
                    f"{p.payment_date.strftime('%d %b') if p.payment_date else 'unknown date'} "
                    f"is awaiting Admin verification."
                ),
                "action_url":   None,
                "action_label": None,
            })

        # ── 3. Overdue bills ──────────────────────────────────────────────
        if resident_id:
            overdue = MaintenanceBill.query.filter_by(
                resident_id=resident_id,
                society_id=society_id,
                status="Overdue",
            ).count()
            if overdue:
                _add("overdue_bills", {
                    "level":        "danger",
                    "icon":         "fa-solid fa-triangle-exclamation",
                    "title":        f"{overdue} Overdue Bill(s)",
                    "message":      "Immediate payment required to stop late fee accumulation.",
                    "action_url":   "/resident/bills?status=Overdue",
                    "action_label": "Pay Overdue",
                })

        # ── 4. Unread important notifications (last 7 days) ───────────────
        cutoff = utcnow() - timedelta(days=7)
        important_types = {"EMERGENCY_ALERT", "ACCOUNT_STATUS", "REGISTRATION_APPROVED",
                           "REGISTRATION_REJECTED"}
        important_unread = (
            NotificationLog.query.filter(
                NotificationLog.user_id == user_id,
                NotificationLog.society_id == society_id,
                NotificationLog.notification_type.in_(important_types),
                NotificationLog.read_at.is_(None),
                NotificationLog.created_at >= cutoff,
            )
            .order_by(NotificationLog.created_at.desc())
            .limit(2)
            .all()
        )
        for n in important_unread:
            _add(f"imp_{n.id}", {
                "level":        "info",
                "icon":         "fa-solid fa-bell",
                "title":        n.subject or (n.notification_type or "").replace("_", " ").title(),
                "message":      (n.message or "")[:200],
                "action_url":   "/resident/notifications",
                "action_label": "View",
            })

        return alerts

    # ── Digest summary (for "Society Updates" widget) ────────────────────

    @staticmethod
    def build_digest(
        user_id: int,
        society_id: int,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Build a short "Society Updates" digest for the last `days` days.
        Returns counts per category and the 3 most recent unread subjects.
        Read-only.
        """
        cutoff = utcnow() - timedelta(days=days)
        recent = (
            NotificationLog.query.filter(
                NotificationLog.user_id == user_id,
                NotificationLog.society_id == society_id,
                NotificationLog.created_at >= cutoff,
            )
            .order_by(NotificationLog.created_at.desc())
            .limit(50)
            .all()
        )

        grouped = SmartNotificationService.group(recent)
        highlights = [
            n["subject"] or n["notification_type"] or "Update"
            for n in recent[:3]
            if n if True
        ]
        # Flatten recent to dicts for the highlights
        highlights = []
        for n in recent[:3]:
            subj = getattr(n, "subject", None) or (getattr(n, "notification_type", None) or "Update").replace("_", " ").title()
            highlights.append(subj)

        return {
            "days":         days,
            "total":        grouped["total"],
            "unread":       grouped["unread"],
            "categories":   grouped["category_counts"],
            "highlights":   highlights,
            "has_updates":  grouped["total"] > 0,
        }
