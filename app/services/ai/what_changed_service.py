"""
'What Changed?' Audit Summary Service
=====================================
Analyzes historical AuditLog and state transitions for records:
Explains recent changes in plain human language without inventing data.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.models import AuditLog

logger = logging.getLogger(__name__)


class WhatChangedService:
    """'What Changed?' Service for record history diffing."""

    @classmethod
    def get_changes_summary(
        cls,
        entity_type: str,
        entity_id: Optional[int] = None,
        society_id: Optional[int] = None,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Retrieves and translates recent AuditLog entries for an entity into plain-language change bullets:
        e.g.:
        "3 things changed:
         1. Resident status changed from PENDING to ACTIVE.
         2. Payment of ₹1,500.00 verified.
         3. Mobile number updated."
        """
        query = AuditLog.query
        if society_id:
            query = query.filter_by(society_id=society_id)

        # Filter by entity type in action or details
        if entity_type:
            pattern = f"%{entity_type.upper()}%"
            query = query.filter(AuditLog.action.ilike(pattern) | AuditLog.details.ilike(pattern))

        logs = query.order_by(AuditLog.created_at.desc()).limit(limit).all()

        if not logs:
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "total_changes": 0,
                "summary": "No recent changes recorded for this record.",
                "changes_list": [],
            }

        changes_list: List[Dict[str, Any]] = []

        for log in logs:
            user_name = log.user.full_name if log.user else "System"
            time_str = log.created_at.strftime("%d %b %Y, %I:%M %p") if log.created_at else "Recently"
            desc = log.details or f"Action '{log.action}' performed by {user_name}."

            changes_list.append({
                "id": log.id,
                "action": log.action,
                "description": desc,
                "actor": user_name,
                "timestamp": time_str,
            })

        count = len(changes_list)
        summary_header = f"{count} change(s) recently recorded:"

        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "total_changes": count,
            "summary": summary_header,
            "changes_list": changes_list,
        }
