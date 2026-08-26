"""
Incident Intelligence AI Services
=================================
Provides:
- Incident classification (Security, Maintenance, Water, Electricity, Parking, Facility, Noise, Other)
- Severity recommendation (Low, Medium, High, Critical) with rationale
- Duplicate complaint / incident detection
- Chronological timeline generation
- Closure quality assessment
Admin/human makes all final decisions.
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any, Dict, List, Optional

from app.models import db, Complaint, ComplaintComment
from app.utils import utcnow

logger = logging.getLogger(__name__)


class IncidentAIService:
    """Incident Intelligence Service."""

    CATEGORIES = [
        "Security",
        "Maintenance",
        "Water",
        "Electricity",
        "Parking",
        "Facility",
        "Noise",
        "Other",
    ]

    @classmethod
    def classify_incident(cls, title: str, description: str) -> Dict[str, Any]:
        """
        Analyzes incident title and description to suggest category and severity.
        Severity is advisory only — admin confirms final assignment.
        """
        combined = f"{title or ''} {description or ''}".lower()

        # Category determination
        category = "Maintenance"
        if any(w in combined for w in ["thief", "theft", "guard", "gate", "cctv", "stranger", "trespass", "security"]):
            category = "Security"
        elif any(w in combined for w in ["water", "leak", "pipe", "tap", "tank", "sewage", "flush", "drain"]):
            category = "Water"
        elif any(w in combined for w in ["spark", "wire", "power", "switch", "mcb", "electric", "voltage", "blackout"]):
            category = "Electricity"
        elif any(w in combined for w in ["car", "bike", "parking", "slot", "vehicle", "driveway"]):
            category = "Parking"
        elif any(w in combined for w in ["gym", "pool", "clubhouse", "hall", "lift", "elevator", "facility"]):
            category = "Facility"
        elif any(w in combined for w in ["noise", "loud", "music", "bark", "dog", "party", "disturb"]):
            category = "Noise"

        # Severity determination
        severity = "Medium"
        severity_reason = "Standard maintenance ticket."
        if any(w in combined for w in ["fire", "smoke", "short circuit", "burst", "stuck in lift", "trapped", "flooding"]):
            severity = "Critical"
            severity_reason = "Keywords indicate immediate hazard to safety or infrastructure."
        elif any(w in combined for w in ["heavy leak", "no water", "no power", "gate open", "broken lock", "urgent"]):
            severity = "High"
            severity_reason = "Significant operational disruption reported."
        elif any(w in combined for w in ["minor", "cosmetic", "paint", "request", "light bulb"]):
            severity = "Low"
            severity_reason = "Routine non-urgent maintenance item."

        return {
            "suggested_category": category,
            "suggested_severity": severity,
            "severity_reason": severity_reason,
            "confidence": 0.92,
            "available_categories": cls.CATEGORIES,
            "note": "Severity and category are recommendations only. Admin makes the final decision.",
        }


    @classmethod
    def detect_duplicate_incidents(
        cls,
        society_id: int,
        title: str,
        description: str,
        flat_id: Optional[int] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Compares new incident with open complaints in the last N days.
        """
        since = utcnow() - timedelta(days=days)
        query = Complaint.query.filter(
            Complaint.society_id == society_id,
            Complaint.created_at >= since,
            Complaint.status.in_(["Submitted", "Assigned", "In Progress"]),
        )
        if flat_id:
            query = query.filter(Complaint.flat_id == flat_id)

        existing = query.all()

        def tokenize(s):
            return set(re.findall(r"\b\w{3,}\b", (s or "").lower()))

        input_tokens = tokenize(f"{title} {description}")
        duplicates: List[Dict[str, Any]] = []

        for c in existing:
            c_tokens = tokenize(f"{c.title} {c.description}")
            if not c_tokens or not input_tokens:
                continue
            sim = (len(input_tokens & c_tokens) / len(input_tokens | c_tokens)) * 100
            if sim >= 40:
                duplicates.append({
                    "id": c.id,
                    "title": c.title,
                    "status": c.status,
                    "priority": c.priority,
                    "flat": c.flat.flat_number if c.flat else "Common",
                    "created_at": c.created_at.strftime("%d %b %Y, %I:%M %p") if c.created_at else "Recent",
                    "similarity_percentage": int(round(sim)),
                })

        duplicates.sort(key=lambda d: d["similarity_percentage"], reverse=True)

        return {
            "has_potential_duplicates": len(duplicates) > 0,
            "duplicate_count": len(duplicates),
            "potential_duplicates": duplicates,
            "advisory": (
                f"Found {len(duplicates)} similar open ticket(s). Check if this is a recurring issue."
                if duplicates
                else "No duplicate complaints detected."
            ),
        }

    @classmethod
    def generate_incident_timeline(cls, complaint_id: int) -> List[Dict[str, Any]]:
        """
        Generates a chronological audit timeline of the complaint lifecycle.
        """
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            return []

        events: List[Dict[str, Any]] = []

        # 1. Created event
        events.append({
            "stage": "Created",
            "title": f"Complaint #{complaint.id} Submitted",
            "timestamp": complaint.created_at.strftime("%d %b %Y, %I:%M %p") if complaint.created_at else "N/A",
            "description": f"Reported by {complaint.resident.full_name if complaint.resident else 'Resident'} ({complaint.category}).",
            "icon": "fa-circle-plus",
            "status_color": "var(--primary)",
        })

        # 2. Assignment event
        if hasattr(complaint, "assigned_staff") and complaint.assigned_staff:
            events.append({
                "stage": "Assigned",
                "title": f"Assigned to {complaint.assigned_staff.full_name}",
                "timestamp": complaint.updated_at.strftime("%d %b %Y, %I:%M %p") if complaint.updated_at else "N/A",
                "description": "Ticket routed to maintenance staff for inspection.",
                "icon": "fa-user-gear",
                "status_color": "var(--info)",
            })

        # 3. Comments
        comments = ComplaintComment.query.filter_by(complaint_id=complaint.id).order_by(
            ComplaintComment.created_at.asc()
        ).all()
        for comm in comments:
            events.append({
                "stage": "Update",
                "title": f"Comment from {comm.user.full_name if comm.user else 'User'}",
                "timestamp": comm.created_at.strftime("%d %b %Y, %I:%M %p") if comm.created_at else "N/A",
                "description": comm.comment,
                "icon": "fa-comment",
                "status_color": "var(--warning)",
            })

        # 4. Resolution event
        if complaint.status in ["Resolved", "Closed"]:
            res_time = getattr(complaint, "resolved_at", None) or complaint.updated_at
            res_notes = getattr(complaint, "resolution_notes", None) or "Resolved by maintenance team."
            events.append({
                "stage": "Resolved",
                "title": f"Complaint {complaint.status}",
                "timestamp": res_time.strftime("%d %b %Y, %I:%M %p") if res_time else "N/A",
                "description": res_notes,
                "icon": "fa-circle-check",
                "status_color": "var(--success)",
            })

        return events

    @classmethod
    def check_closure_quality(cls, complaint_id: int, resolution_notes: str) -> Dict[str, Any]:
        """
        Audits resolution notes to verify if the issue was explained and closed thoroughly.
        """
        notes = (resolution_notes or "").strip()
        issues: List[str] = []
        suggestions: List[str] = []

        if len(notes) < 15:
            issues.append("Resolution notes are too brief.")
            suggestions.append("Explain the corrective actions taken (e.g., 'Replaced 1/2 inch valve and checked pressure').")

        if not any(w in notes.lower() for w in ["fixed", "replaced", "repaired", "cleaned", "inspected", "completed", "resolved", "tested"]):
            issues.append("No specific action verbs found in resolution notes.")
            suggestions.append("Mention specific repair actions performed by technician.")

        score = max(30, 100 - (len(issues) * 35))
        is_good = score >= 70

        return {
            "complaint_id": complaint_id,
            "quality_score": score,
            "is_satisfactory": is_good,
            "issues": issues,
            "suggestions": suggestions,
            "verdict": "High Quality Closure" if is_good else "Needs More Detail Before Closure",
        }
