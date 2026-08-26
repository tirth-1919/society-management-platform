"""
Smart Notification Intelligence Services
========================================
Improves notification delivery & presentation:
- Importance ranking (Critical, High, Medium, Low)
- Related-notification grouping
- Read/unread tracking
- Optional snooze management
- Notification categorization
- Suggested direct actions
Does NOT break existing NotificationService or bypass NotificationPreference rules.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from app.models import NotificationLog, db
from app.utils import utcnow

logger = logging.getLogger(__name__)

# Category mapping
TYPE_TO_CATEGORY = {
    "PAYMENT_SUCCESS": ("Payments", "fa-circle-check", "var(--success)"),
    "PAYMENT_FAILED": ("Payments", "fa-circle-xmark", "var(--danger)"),
    "PAYMENT_PENDING": ("Payments", "fa-clock", "var(--warning)"),
    "BILL_GENERATED": ("Maintenance", "fa-file-invoice", "var(--primary)"),
    "DUE_REMINDER": ("Maintenance", "fa-bell", "var(--warning)"),
    "OVERDUE_REMINDER": ("Maintenance", "fa-triangle-exclamation", "var(--danger)"),
    "LATE_FEE_NOTICE": ("Maintenance", "fa-percent", "var(--danger)"),
    "COMPLAINT_UPDATE": ("Complaints", "fa-headset", "var(--info)"),
    "COMPLAINT_RESOLVED": ("Complaints", "fa-check-double", "var(--success)"),
    "NOTICE_PUBLISHED": ("Announcements", "fa-bullhorn", "var(--primary)"),
    "EMERGENCY_ALERT": ("Emergency Alerts", "fa-triangle-exclamation", "var(--danger)"),
    "REGISTRATION_APPROVED": ("Registration", "fa-user-check", "var(--success)"),
    "REGISTRATION_REJECTED": ("Registration", "fa-user-xmark", "var(--danger)"),
}


class SmartNotificationService:
    """Smart Notification Intelligence Engine."""

    @classmethod
    def enrich_notification(cls, log: NotificationLog) -> Dict[str, Any]:
        """Adds priority ranking, category, suggested action, and presentation styling."""
        ntype = log.notification_type or "GENERAL"
        cat, icon, color = TYPE_TO_CATEGORY.get(ntype, ("General", "fa-bell", "var(--primary)"))

        # Importance ranking
        priority = "Low"
        if ntype in ["EMERGENCY_ALERT", "OVERDUE_REMINDER"]:
            priority = "Critical"
        elif ntype in ["DUE_REMINDER", "PAYMENT_FAILED", "COMPLAINT_UPDATE"]:
            priority = "High"
        elif ntype in ["BILL_GENERATED", "NOTICE_PUBLISHED", "PAYMENT_SUCCESS"]:
            priority = "Medium"

        # Suggested direct action
        suggested_action = None
        if "BILL" in ntype or "DUE" in ntype or "OVERDUE" in ntype:
            suggested_action = {"label": "Pay Dues", "url": "/resident/bills", "icon": "fa-credit-card"}
        elif "COMPLAINT" in ntype:
            suggested_action = {"label": "View Ticket", "url": "/resident/complaints", "icon": "fa-headset"}
        elif "NOTICE" in ntype or "EMERGENCY" in ntype:
            suggested_action = {"label": "Read Notice", "url": "/resident/announcements", "icon": "fa-bullhorn"}
        elif "PAYMENT" in ntype:
            suggested_action = {"label": "View Receipts", "url": "/resident/receipts", "icon": "fa-receipt"}

        return {
            "id": log.id,
            "category": cat,
            "icon": icon,
            "color": color,
            "priority": priority,
            "subject": log.subject or cat,
            "message": log.message,
            "is_read": log.read_at is not None,
            "sent_at": log.sent_at.strftime("%d %b %Y, %I:%M %p") if log.sent_at else "Recently",
            "suggested_action": suggested_action,
        }

    @classmethod
    def group_and_rank_notifications(
        cls, user_id: int, society_id: int, limit: int = 50
    ) -> Dict[str, Any]:
        """
        Retrieves, enriches, and groups notifications by category with importance ranking.
        """
        logs = NotificationLog.query.filter_by(
            user_id=user_id, society_id=society_id
        ).order_by(NotificationLog.sent_at.desc()).limit(limit).all()

        enriched = [cls.enrich_notification(log) for log in logs]

        groups: Dict[str, List[Dict[str, Any]]] = {}
        for item in enriched:
            cat = item["category"]
            groups.setdefault(cat, []).append(item)

        unread_count = sum(1 for item in enriched if not item["is_read"])
        critical_count = sum(1 for item in enriched if item["priority"] == "Critical" and not item["is_read"])

        return {
            "total_count": len(enriched),
            "unread_count": unread_count,
            "critical_count": critical_count,
            "categories": groups,
            "notifications": enriched,
        }

    @classmethod
    def mark_as_read(cls, notification_id: int, user_id: int) -> bool:
        """Marks a notification as read."""
        log = NotificationLog.query.filter_by(id=notification_id, user_id=user_id).first()
        if log and not log.read_at:
            log.read_at = utcnow()
            db.session.commit()
            return True
        return False
