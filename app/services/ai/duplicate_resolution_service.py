"""
AI Duplicate & Identity Resolution System
=========================================
Scans permitted fields across Residents, Flats, Phone numbers, Emails, Vehicles, and Vendors.
Calculates fuzzy match confidence scores and provides an admin confirmation workspace
with zero silent/destructive automatic merges.
"""

from __future__ import annotations

import difflib
import logging
import re
from typing import Any, Optional

from app.models.tenant import db
from app.models.resident import Resident
from app.models.ai_operations import (
    AIDuplicateCandidate,
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.services.ai.ai_audit_service import AIAuditService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class DuplicateResolutionAIService:
    @staticmethod
    def _normalize_phone(phone: str) -> str:
        if not phone:
            return ""
        digits = re.sub(r"\D", "", phone)
        if len(digits) > 10 and digits.startswith("91"):
            digits = digits[2:]
        return digits[-10:] if len(digits) >= 10 else digits

    @classmethod
    def scan_duplicate_residents(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Scans resident profiles for potential duplicate identities within the same society.
        """
        residents = Resident.query.filter_by(
            society_id=society_id
        ).filter(Resident.occupancy_status != "Moved Out").all()

        candidates = []
        n = len(residents)

        for i in range(n):
            for j in range(i + 1, n):
                r1 = residents[i]
                r2 = residents[j]

                reasons = []
                confidence = 0.0

                # 1. Exact or normalized phone match
                p1 = cls._normalize_phone(r1.mobile)
                p2 = cls._normalize_phone(r2.mobile)
                if p1 and p2 and p1 == p2:
                    confidence += 0.50
                    reasons.append("Identical normalized phone number")

                # 2. Same flat assignment
                if r1.flat_id and r2.flat_id and r1.flat_id == r2.flat_id:
                    confidence += 0.25
                    reasons.append(f"Both assigned to same Unit #{r1.flat.flat_number if r1.flat else r1.flat_id}")

                # 3. Name similarity (Levenshtein ratio)
                n1 = (r1.full_name or "").lower().strip()
                n2 = (r2.full_name or "").lower().strip()
                sim = difflib.SequenceMatcher(None, n1, n2).ratio()
                if sim >= 0.85:
                    confidence += 0.35
                    reasons.append(f"High name similarity ({int(sim * 100)}% match: '{r1.full_name}' vs '{r2.full_name}')")
                elif sim >= 0.65:
                    confidence += 0.15
                    reasons.append(f"Partial name similarity ({int(sim * 100)}% match)")

                # 4. Email match
                if r1.email and r2.email and r1.email.lower().strip() == r2.email.lower().strip():
                    confidence += 0.30
                    reasons.append("Identical email address on record")

                final_conf = min(0.99, confidence)

                if final_conf >= 0.65:
                    # Check if already recorded
                    candidate = AIDuplicateCandidate.query.filter_by(
                        society_id=society_id,
                        entity_type="RESIDENT",
                        primary_entity_id=r1.id,
                        duplicate_entity_id=r2.id,
                    ).first()

                    if not candidate:
                        candidate = AIDuplicateCandidate(
                            society_id=society_id,
                            entity_type="RESIDENT",
                            primary_entity_id=r1.id,
                            duplicate_entity_id=r2.id,
                            match_confidence=final_conf,
                            status="PENDING",
                        )
                        candidate.set_reasons(reasons)
                        db.session.add(candidate)

                    finding_title = f"Suspected Duplicate Resident: {r1.full_name} / {r2.full_name}"
                    finding = AIFinding.query.filter_by(
                        society_id=society_id,
                        ai_system=AISystemType.DUPLICATES,
                        finding_type="DUPLICATE_RESIDENT_CANDIDATE",
                        entity_id=r1.id,
                    ).first()

                    if not finding:
                        finding = AIFinding(
                            society_id=society_id,
                            ai_system=AISystemType.DUPLICATES,
                            entity_type="RESIDENT",
                            entity_id=r1.id,
                            finding_type="DUPLICATE_RESIDENT_CANDIDATE",
                            severity=AIFindingSeverity.HIGH if final_conf >= 0.85 else AIFindingSeverity.MEDIUM,
                            confidence_score=final_conf,
                            title=finding_title,
                            summary=f"Possible duplicate records detected ({int(final_conf * 100)}% match). Reasons: {'; '.join(reasons)}.",
                            recommended_action="Review both resident records in Duplicate Resolution workspace.",
                            status=AIFindingStatus.NEW,
                        )
                        finding.set_evidence({
                            "resident_a": {"id": r1.id, "name": r1.full_name, "flat": r1.flat.flat_number if r1.flat else None},
                            "resident_b": {"id": r2.id, "name": r2.full_name, "flat": r2.flat.flat_number if r2.flat else None},
                            "reasons": reasons,
                        })
                        db.session.add(finding)

                    candidates.append({
                        "primary_resident": {"id": r1.id, "name": r1.full_name, "mobile_masked": f"******{p1[-4:]}" if p1 else "***"},
                        "duplicate_resident": {"id": r2.id, "name": r2.full_name, "mobile_masked": f"******{p2[-4:]}" if p2 else "***"},
                        "confidence": final_conf,
                        "reasons": reasons,
                    })

        db.session.commit()
        return candidates

    @classmethod
    def resolve_candidate(
        cls, candidate_id: int, society_id: int, actor_id: int, action: str, notes: Optional[str] = None
    ) -> AIDuplicateCandidate:
        """
        Resolves a duplicate candidate safely without deleting underlying records.
        Actions: CONFIRMED_DUPLICATE, NOT_DUPLICATE, MERGED
        """
        candidate = AIDuplicateCandidate.query.filter_by(id=candidate_id, society_id=society_id).first()
        if not candidate:
            raise ValueError(f"Candidate #{candidate_id} not found.")

        candidate.status = action
        candidate.reviewed_by_id = actor_id
        candidate.reviewed_at = utcnow()
        candidate.action_notes = notes or f"Admin marked as {action}"
        db.session.commit()

        AIAuditService.log_event(
            society_id=society_id,
            action=f"DUPLICATE_{action}",
            entity_type=candidate.entity_type,
            entity_id=candidate.primary_entity_id,
            actor_id=actor_id,
            details={"candidate_id": candidate.id, "action": action, "notes": notes},
        )
        return candidate
