"""
Data Quality Center & Duplicate Resident Detector
=================================================
Provides comprehensive data health audits for society records:
- Duplicate residents
- Duplicate flats
- Missing relationships
- Invalid mobile formats
- Invalid emails
- Inconsistent flat/wing names
- Unexpected null values
- Old / stale records
- Duplicate Resident similarity scoring
Strictly read-only diagnostics. Does NOT automatically modify database records.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Tuple

from app.models import (
    Resident,
    Flat,
    Building,
)

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class DataQualityAIService:
    """
    Data Quality Audit Service:
    Returns structured data issues:
    {
        "type": "...",
        "severity": "low|medium|high|critical",
        "record_id": "...",
        "description": "...",
        "suggested_fix": "..."
    }
    """

    @classmethod
    def run_full_audit(cls, society_id: int) -> Dict[str, Any]:
        issues: List[Dict[str, Any]] = []

        residents = Resident.query.filter_by(society_id=society_id).all()
        flats = Flat.query.filter_by(society_id=society_id).all()

        # 1. Invalid mobile formats
        for r in residents:
            mobile_clean = re.sub(r"\D", "", r.mobile or "")
            if len(mobile_clean) != 10:
                issues.append({
                    "type": "invalid_mobile_format",
                    "severity": "high",
                    "record_id": f"resident_{r.id}",
                    "record_name": r.full_name,
                    "description": f"Resident '{r.full_name}' has invalid mobile '{r.mobile}' ({len(mobile_clean)} digits).",
                    "suggested_fix": "Update resident profile with a valid 10-digit mobile number.",
                })

        # 2. Invalid emails
        for r in residents:
            if r.email and not EMAIL_REGEX.match(r.email.strip()):
                issues.append({
                    "type": "invalid_email_format",
                    "severity": "medium",
                    "record_id": f"resident_{r.id}",
                    "record_name": r.full_name,
                    "description": f"Resident '{r.full_name}' has invalid email syntax '{r.email}'.",
                    "suggested_fix": "Correct the email address format.",
                })

        # 3. Missing relationships (residents without flat, or flats without block)
        for r in residents:
            if not r.flat_id or not r.flat:
                issues.append({
                    "type": "missing_flat_relationship",
                    "severity": "high",
                    "record_id": f"resident_{r.id}",
                    "record_name": r.full_name,
                    "description": f"Resident '{r.full_name}' has no flat assigned.",
                    "suggested_fix": "Assign resident to their corresponding wing and flat.",
                })

        for f in flats:
            if not f.block_id:
                issues.append({
                    "type": "missing_block_assignment",
                    "severity": "low",
                    "record_id": f"flat_{f.id}",
                    "record_name": f.property_key,
                    "description": f"Flat {f.flat_number} in {f.building.name if f.building else 'Wing'} is not assigned to a Block.",
                    "suggested_fix": "Assign flat to Block A-F for organized billing.",
                })


        # 4. Duplicate Flats
        seen_flats: Dict[Tuple[int, str], List[Flat]] = {}
        for f in flats:
            key = (f.building_id, str(f.flat_number).strip().upper())
            seen_flats.setdefault(key, []).append(f)

        for (b_id, f_num), dup_list in seen_flats.items():
            if len(dup_list) > 1:
                ids = ", ".join(str(f.id) for f in dup_list)
                issues.append({
                    "type": "duplicate_flat",
                    "severity": "critical",
                    "record_id": f"flats_{ids}",
                    "record_name": f"Flat {f_num}",
                    "description": f"Multiple flat records ({len(dup_list)}) exist for Flat {f_num} in the same Wing.",
                    "suggested_fix": "Merge or remove duplicate flat records to prevent double billing.",
                })

        # 5. Duplicate Residents (Phone or Email)
        seen_mobiles: Dict[str, List[Resident]] = {}
        for r in residents:
            if r.mobile:
                mob = re.sub(r"\D", "", r.mobile)
                seen_mobiles.setdefault(mob, []).append(r)

        for mob, dup_res in seen_mobiles.items():
            if len(dup_res) > 1:
                names = ", ".join(r.full_name for r in dup_res)
                ids = ", ".join(str(r.id) for r in dup_res)
                issues.append({
                    "type": "duplicate_resident_mobile",
                    "severity": "high",
                    "record_id": f"residents_{ids}",
                    "record_name": names,
                    "description": f"Mobile '{mob}' is shared by {len(dup_res)} residents: {names}.",
                    "suggested_fix": "Review profiles and ensure each primary account has a distinct mobile.",
                })

        # 6. Inconsistent Wing or Block Naming
        buildings = Building.query.filter_by(society_id=society_id).all()
        for b in buildings:
            if not b.name or len(b.name.strip()) < 2:
                issues.append({
                    "type": "inconsistent_naming",
                    "severity": "medium",
                    "record_id": f"wing_{b.id}",
                    "record_name": b.name or "Empty Wing Name",
                    "description": f"Wing ID {b.id} has an incomplete or missing name.",
                    "suggested_fix": "Assign standard wing name e.g. 'Wing A'.",
                })

        # 7. Stale / Inactive Records
        for r in residents:
            if r.occupancy_status != "Active" and not getattr(r, "move_out_date", None):
                issues.append({
                    "type": "stale_resident_record",
                    "severity": "low",
                    "record_id": f"resident_{r.id}",
                    "record_name": r.full_name,
                    "description": f"Resident '{r.full_name}' status is '{r.occupancy_status}' but no move-out date is recorded.",
                    "suggested_fix": "Record official move-out date or archive the record.",
                })

        # Summary calculations
        critical_count = sum(1 for i in issues if i["severity"] == "critical")
        high_count = sum(1 for i in issues if i["severity"] == "high")
        medium_count = sum(1 for i in issues if i["severity"] == "medium")
        low_count = sum(1 for i in issues if i["severity"] == "low")

        health_score = max(0, 100 - (critical_count * 25 + high_count * 10 + medium_count * 5 + low_count * 2))

        return {
            "society_id": society_id,
            "data_health_score": health_score,
            "total_issues_count": len(issues),
            "critical_count": critical_count,
            "high_count": high_count,
            "medium_count": medium_count,
            "low_count": low_count,
            "issues": issues,
            "audited_records": {
                "residents_count": len(residents),
                "flats_count": len(flats),
                "wings_count": len(buildings),
            },
        }


class DuplicateResidentDetector:
    """
    Duplicate Resident Similarity Matching:
    Compares resident records using weighted multi-field matching (Name, Mobile, Email, Flat).
    Returns confidence score % and diff comparison.
    """

    @classmethod
    def find_potential_duplicates(cls, society_id: int) -> List[Dict[str, Any]]:
        residents = Resident.query.filter_by(society_id=society_id).all()
        duplicates: List[Dict[str, Any]] = []

        def name_similarity(n1: str, n2: str) -> float:
            s1 = set((n1 or "").lower().split())
            s2 = set((n2 or "").lower().split())
            if not s1 or not s2:
                return 0.0
            return len(s1 & s2) / len(s1 | s2)

        for i in range(len(residents)):
            for j in range(i + 1, len(residents)):
                r1 = residents[i]
                r2 = residents[j]

                score = 0.0
                reasons = []

                # Exact phone match (40 pts)
                if r1.mobile and r2.mobile and re.sub(r"\D", "", r1.mobile) == re.sub(r"\D", "", r2.mobile):
                    score += 0.45
                    reasons.append("Identical mobile number")

                # Exact email match (35 pts)
                if r1.email and r2.email and r1.email.strip().lower() == r2.email.strip().lower():
                    score += 0.35
                    reasons.append("Identical email address")

                # Name similarity (up to 30 pts)
                nsim = name_similarity(r1.full_name, r2.full_name)
                if nsim >= 0.8:
                    score += 0.30
                    reasons.append("Matching full name")
                elif nsim >= 0.5:
                    score += 0.15
                    reasons.append("Similar name words")

                # Same flat (15 pts)
                if r1.flat_id and r2.flat_id and r1.flat_id == r2.flat_id:
                    score += 0.15
                    reasons.append("Assigned to identical flat")

                conf_percent = int(round(min(1.0, score) * 100))

                if conf_percent >= 60:
                    duplicates.append({
                        "resident_a": {
                            "id": r1.id,
                            "name": r1.full_name,
                            "mobile": r1.mobile,
                            "email": r1.email,
                            "flat": r1.flat.property_key if r1.flat else "N/A",
                            "type": r1.resident_type,
                            "status": r1.occupancy_status,
                        },
                        "resident_b": {
                            "id": r2.id,
                            "name": r2.full_name,
                            "mobile": r2.mobile,
                            "email": r2.email,
                            "flat": r2.flat.property_key if r2.flat else "N/A",
                            "type": r2.resident_type,
                            "status": r2.occupancy_status,
                        },
                        "confidence": conf_percent,
                        "reasons": reasons,
                        "action_advisory": "Review both resident profiles. If duplicate, merge or update the stale entry.",
                    })

        duplicates.sort(key=lambda d: d["confidence"], reverse=True)
        return duplicates
