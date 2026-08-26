"""
AI Incident Response System
===========================
Automated incident categorization, severity triage, department routing, SLA calculation,
duplicate detection, and post-closure recurring root cause pattern detection.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any, Optional

from app.models.tenant import db
from app.models.complaint import Complaint
from app.models.operations import WorkOrder
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class IncidentResponseAIService:
    INCIDENT_CATEGORIES = [
        "Lift",
        "Fire",
        "Water",
        "Electrical",
        "Security",
        "Property Damage",
        "Safety",
        "Other",
    ]

    DEPARTMENT_MAP = {
        "Lift": "Elevator Maintenance Dept",
        "Fire": "Fire & Safety Response Team",
        "Water": "Plumbing & Water Supply Dept",
        "Electrical": "Electrical Engineering Dept",
        "Security": "Estate Security Command",
        "Property Damage": "Civil & Infrastructure Dept",
        "Safety": "Health, Safety & Environment (HSE)",
        "Other": "General Society Operations",
    }

    SLA_HOURS = {
        "Lift": 4,
        "Fire": 1,
        "Security": 2,
        "Electrical": 6,
        "Water": 8,
        "Safety": 4,
        "Property Damage": 24,
        "Other": 48,
    }

    @classmethod
    def classify_incident(cls, title: str, description: str) -> dict[str, Any]:
        """
        Classifies incident into primary category, severity, SLA, and responsible department.
        """
        combined = f"{title or ''} {description or ''}".lower()

        # Default fallback
        category = "Other"
        severity = AIFindingSeverity.MEDIUM
        confidence = 0.78
        rec_action = "Assign technician for inspection."

        if any(k in combined for k in ["fire", "smoke", "extinguisher", "flame", "burn"]):
            category = "Fire"
            severity = AIFindingSeverity.CRITICAL
            confidence = 0.98
            rec_action = "Initiate immediate fire safety protocol and notify safety supervisor."
        elif any(k in combined for k in ["lift", "elevator", "stuck between floors", "lift breakdown"]):
            category = "Lift"
            severity = AIFindingSeverity.HIGH if "stuck" in combined else AIFindingSeverity.MEDIUM
            if "stuck" in combined or "trapped" in combined:
                severity = AIFindingSeverity.CRITICAL
            confidence = 0.96
            rec_action = "Dispatch elevator AMC technician for on-site inspection immediately."
        elif any(k in combined for k in ["spark", "power cut", "short circuit", "voltage", "blackout", "mcb", "shock"]):
            category = "Electrical"
            severity = AIFindingSeverity.HIGH if any(k in combined for k in ["spark", "shock", "short circuit"]) else AIFindingSeverity.MEDIUM
            confidence = 0.94
            rec_action = "Dispatch electrician to isolate circuit and verify breaker stability."
        elif any(k in combined for k in ["water leak", "pipe burst", "tank overflow", "no water", "flooding", "sewage", "drainage"]):
            category = "Water"
            severity = AIFindingSeverity.HIGH if any(k in combined for k in ["burst", "flooding", "overflow"]) else AIFindingSeverity.MEDIUM
            confidence = 0.92
            rec_action = "Dispatch plumbing team and check main water valve."
        elif any(k in combined for k in ["theft", "trespass", "fight", "stranger", "guard", "break-in", "cctv"]):
            category = "Security"
            severity = AIFindingSeverity.HIGH
            confidence = 0.91
            rec_action = "Notify head of security and preserve relevant gate/access logs."
        elif any(k in combined for k in ["fall", "injury", "slippery", "hazard", "glass broken", "sharp"]):
            category = "Safety"
            severity = AIFindingSeverity.HIGH
            confidence = 0.89
            rec_action = "Cordon off hazardous zone and attend to resident safety."
        elif any(k in combined for k in ["crack", "wall", "gate broken", "door broken", "tile", "pavement"]):
            category = "Property Damage"
            severity = AIFindingSeverity.LOW if "tile" in combined else AIFindingSeverity.MEDIUM
            confidence = 0.86
            rec_action = "Schedule civil maintenance assessment."

        dept = cls.DEPARTMENT_MAP.get(category, "General Society Operations")
        sla = cls.SLA_HOURS.get(category, 24)
        if severity == AIFindingSeverity.CRITICAL:
            sla = min(sla, 2)

        return {
            "category": category,
            "severity": severity,
            "department": dept,
            "sla_hours": sla,
            "confidence_score": confidence,
            "recommended_action": rec_action,
        }


    @classmethod
    def detect_duplicate_incidents(
        cls, society_id: int, title: str, description: str, flat_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Detects existing open complaints/work orders matching title/description or location.
        """
        duplicates = []
        recent_complaints = Complaint.query.filter_by(
            society_id=society_id
        ).filter(
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
        ).all()

        t_lower = (title or "").lower()
        d_lower = (description or "").lower()

        for c in recent_complaints:
            score = 0
            if c.title and c.title.lower() == t_lower:
                score += 70
            elif c.title and any(w in (c.title.lower()) for w in t_lower.split() if len(w) > 3):
                score += 35

            if d_lower and c.description and d_lower in c.description.lower():
                score += 20

            if flat_id and c.flat_id == flat_id:
                score += 30

            if score >= 60:
                duplicates.append({
                    "complaint_id": c.id,
                    "ticket_number": c.ticket_number,
                    "title": c.title,
                    "status": c.status,
                    "similarity_score": min(95, score),
                    "flat_id": c.flat_id,
                })

        return duplicates

    @classmethod
    def run_root_cause_analysis(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Scans historical complaints and work orders (past 120 days) to identify recurring equipment or location patterns.
        """
        cutoff = utcnow() - timedelta(days=120)
        complaints = Complaint.query.filter_by(society_id=society_id).filter(Complaint.created_at >= cutoff).all()
        work_orders = WorkOrder.query.filter_by(society_id=society_id).filter(WorkOrder.created_at >= cutoff).all()

        patterns = defaultdict(int)
        entity_evidence = defaultdict(list)

        for c in complaints:
            cat = c.category or "General"
            title = (c.title or "").lower()
            key = f"Complaint Category: {cat}"
            if "lift" in title:
                key = "Recurring Lift Operations"
            elif "water" in title or "leak" in title:
                key = "Water Supply & Plumbing Network"
            elif "power" in title or "voltage" in title:
                key = "Electrical Power Stability"

            patterns[key] += 1
            entity_evidence[key].append(f"Ticket #{c.ticket_number}: {c.title}")

        for wo in work_orders:
            cat = wo.category or "Maintenance"
            key = f"Work Order: {cat}"
            patterns[key] += 1
            entity_evidence[key].append(f"WO #{wo.id}: {wo.title}")

        recurring_findings = []
        for pattern_name, count in patterns.items():
            if count >= 3:
                finding_title = f"Recurring Issue Pattern: {pattern_name} ({count} tickets)"
                summary = f"Detected {count} related incidents/complaints in the last 120 days pointing to a potential recurring root cause in {pattern_name}."
                rec_action = f"Initiate comprehensive root-cause engineering audit for {pattern_name}."

                finding = AIFinding.query.filter_by(
                    society_id=society_id,
                    ai_system=AISystemType.INCIDENT,
                    finding_type="RECURRING_ROOT_CAUSE",
                    title=finding_title,
                ).first()

                if not finding:
                    finding = AIFinding(
                        society_id=society_id,
                        ai_system=AISystemType.INCIDENT,
                        entity_type="SYSTEM",
                        finding_type="RECURRING_ROOT_CAUSE",
                        severity=AIFindingSeverity.HIGH if count >= 5 else AIFindingSeverity.MEDIUM,
                        confidence_score=0.91,
                        title=finding_title,
                        summary=summary,
                        recommended_action=rec_action,
                        status=AIFindingStatus.NEW,
                    )
                    finding.set_evidence({"occurrences": count, "sample_tickets": entity_evidence[pattern_name][:5]})
                    db.session.add(finding)

                recurring_findings.append({
                    "pattern": pattern_name,
                    "count": count,
                    "evidence": entity_evidence[pattern_name][:5],
                })

        db.session.commit()
        return recurring_findings
