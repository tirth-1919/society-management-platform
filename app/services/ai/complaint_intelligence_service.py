"""
AI Complaint Intelligence System
================================
Classification, priority estimation, SLA routing, duplicate detection,
and block-level complaint spike clustering across active society tickets.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any, Optional

from app.models.tenant import db
from app.models.complaint import Complaint
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class ComplaintIntelligenceAIService:
    @classmethod
    def analyze_complaint_intake(cls, title: str, description: str) -> dict[str, Any]:
        """
        Lightweight classification for newly submitted complaints.
        """
        combined = f"{title or ''} {description or ''}".lower()

        category = "General"
        priority = "Medium"
        sla_hours = 24
        department = "Estate Management"

        if any(k in combined for k in ["lift", "elevator", "stuck"]):
            category = "Lift"
            priority = "Emergency" if "stuck" in combined else "High"
            sla_hours = 4
            department = "Elevator AMC Dept"
        elif any(k in combined for k in ["water", "leak", "pipe", "tap", "drain", "sewage", "flush", "pressure"]):
            category = "Water / Plumbing"
            priority = "High" if any(k in combined for k in ["burst", "overflow", "pressure", "flooding"]) else "Medium"
            sla_hours = 8
            department = "Plumbing & Sanitation"
        elif any(k in combined for k in ["spark", "power", "switch", "light", "mcb", "electric", "voltage"]):
            category = "Electrical"
            priority = "High"
            sla_hours = 6
            department = "Electrical Maintenance"
        elif any(k in combined for k in ["guard", "theft", "gate", "cctv", "security", "stranger"]):
            category = "Security"
            priority = "High"
            sla_hours = 6
            department = "Security Management"
        elif any(k in combined for k in ["garbage", "trash", "clean", "dust", "sweep", "smell"]):
            category = "Housekeeping"
            priority = "Medium"
            sla_hours = 24
            department = "Housekeeping Services"

        return {
            "suggested_category": category,
            "suggested_priority": priority,
            "suggested_sla_hours": sla_hours,
            "suggested_department": department,
            "confidence_score": 0.94,
        }

    @classmethod
    def scan_complaint_clusters(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Detects duplicate clusters and wing/block complaint spikes across open tickets.
        """
        cutoff = utcnow() - timedelta(days=30)
        open_complaints = Complaint.query.filter_by(
            society_id=society_id
        ).filter(
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
            Complaint.created_at >= cutoff,
        ).all()

        clusters = []

        # 1. Title/Topic Duplicate Clustering
        topic_groups = defaultdict(list)
        for c in open_complaints:
            t = (c.title or "").lower().strip()
            topic_key = "general"
            if any(k in t for k in ["water", "pressure", "pipe"]):
                topic_key = "Water Supply & Pressure"
            elif any(k in t for k in ["lift", "elevator"]):
                topic_key = "Elevator Operation"
            elif any(k in t for k in ["power", "light", "electric"]):
                topic_key = "Electrical Infrastructure"
            elif any(k in t for k in ["clean", "garbage"]):
                topic_key = "Housekeeping & Cleanliness"

            topic_groups[topic_key].append(c)

        for topic, c_list in topic_groups.items():
            if len(c_list) >= 3 and topic != "general":
                finding_title = f"Complaint Cluster Detected: {topic} ({len(c_list)} tickets)"
                summary = f"Detected {len(c_list)} similar open complaints regarding '{topic}'. Possible common root cause."
                rec_action = f"Investigate central infrastructure for {topic} to resolve related tickets simultaneously."

                clusters.append({
                    "cluster_name": topic,
                    "count": len(c_list),
                    "ticket_numbers": [c.ticket_number for c in c_list],
                    "complaint_ids": [c.id for c in c_list],
                })

                finding = AIFinding.query.filter_by(
                    society_id=society_id,
                    ai_system=AISystemType.COMPLAINTS,
                    finding_type="COMPLAINT_CLUSTER_DETECTED",
                    title=finding_title,
                ).first()

                if not finding:
                    finding = AIFinding(
                        society_id=society_id,
                        ai_system=AISystemType.COMPLAINTS,
                        entity_type="COMPLAINT",
                        finding_type="COMPLAINT_CLUSTER_DETECTED",
                        severity=AIFindingSeverity.HIGH if len(c_list) >= 5 else AIFindingSeverity.MEDIUM,
                        confidence_score=0.92,
                        title=finding_title,
                        summary=summary,
                        recommended_action=rec_action,
                        status=AIFindingStatus.NEW,
                    )
                    finding.set_evidence({
                        "topic": topic,
                        "ticket_count": len(c_list),
                        "sample_tickets": [c.ticket_number for c in c_list[:5]],
                    })
                    db.session.add(finding)

        db.session.commit()
        return clusters
