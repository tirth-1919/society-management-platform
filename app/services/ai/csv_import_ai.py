"""
CSV Import Assistant
====================
Provides smart assistance for CSV resident and flat onboarding:
- Automatic column mapping with confidence scoring
- Invalid-row detection (bad phone, bad email, missing fields)
- Duplicate preview against existing society records
- Data formatting suggestions
- Import preview with approve/reject workflow
Admin must approve mappings before final transactional commit.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any, Dict, List, Optional

from app.models import Flat, Resident

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


class CSVImportAIService:
    """CSV Import Assistant Service."""

    KNOWN_FIELDS = {
        "full_name": ["name", "full_name", "resident_name", "member_name", "owner_name", "tenant_name", "resident"],
        "mobile": ["mobile", "phone", "contact", "phone_number", "mobile_no", "cell", "cell_phone", "mobile_number"],
        "email": ["email", "email_id", "email_address", "mail", "e-mail"],
        "flat_number": ["flat", "flat_no", "flat_number", "unit", "unit_no", "door_no", "apartment", "flat_num"],
        "resident_type": ["type", "resident_type", "occupancy", "role", "owner/tenant", "status"],
    }

    @classmethod
    def suggest_column_mappings(cls, headers: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Suggests standard field mappings for raw CSV headers with confidence scores.
        """
        mappings: Dict[str, Dict[str, Any]] = {}

        for header in headers:
            h_clean = re.sub(r"[^a-zA-Z0-9]", "_", header.lower()).strip("_")
            best_match = None
            best_confidence = 0

            for standard_field, aliases in cls.KNOWN_FIELDS.items():
                if h_clean == standard_field:
                    best_match = standard_field
                    best_confidence = 100
                    break
                elif h_clean in aliases:
                    best_match = standard_field
                    best_confidence = 95
                    break
                else:
                    for alias in aliases:
                        if alias in h_clean or h_clean in alias:
                            best_match = standard_field
                            best_confidence = max(best_confidence, 80)

            if best_match and best_confidence >= 70:
                mappings[header] = {
                    "mapped_to": best_match,
                    "confidence": best_confidence,
                    "is_mapped": True,
                }
            else:
                mappings[header] = {
                    "mapped_to": None,
                    "confidence": 0,
                    "is_mapped": False,
                }

        return mappings


    @classmethod
    def preview_and_validate_import(
        cls,
        society_id: int,
        csv_text: str,
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Parses CSV, validates against existing DB, detects formatting suggestions and duplicates.
        Returns detailed preview without committing any changes.
        """
        reader = csv.reader(io.StringIO(csv_text))
        rows = list(reader)

        if not rows:
            return {"error": "CSV file is empty.", "valid_rows": [], "invalid_rows": []}

        raw_headers = [h.strip() for h in rows[0]]
        if not column_mapping:
            mapping_suggestions = cls.suggest_column_mappings(raw_headers)
            column_mapping = {h: m["mapped_to"] for h, m in mapping_suggestions.items() if m["mapped_to"]}

        # Invert mapping: standard_field -> raw_header_index
        field_to_idx: Dict[str, int] = {}
        for idx, h in enumerate(raw_headers):
            std = column_mapping.get(h)
            if std:
                field_to_idx[std] = idx

        existing_residents = Resident.query.filter_by(society_id=society_id).all()
        existing_mobiles = {re.sub(r"\D", "", r.mobile): r for r in existing_residents if r.mobile}
        existing_flats = {f.flat_number.upper(): f for f in Flat.query.filter_by(society_id=society_id).all()}

        valid_rows: List[Dict[str, Any]] = []
        invalid_rows: List[Dict[str, Any]] = []
        duplicate_rows: List[Dict[str, Any]] = []
        formatting_suggestions: List[str] = []

        for row_idx, row in enumerate(rows[1:], start=2):
            if not row or not any(row):
                continue

            full_name = row[field_to_idx["full_name"]].strip() if "full_name" in field_to_idx and field_to_idx["full_name"] < len(row) else ""
            mobile_raw = row[field_to_idx["mobile"]].strip() if "mobile" in field_to_idx and field_to_idx["mobile"] < len(row) else ""
            email_raw = row[field_to_idx["email"]].strip() if "email" in field_to_idx and field_to_idx["email"] < len(row) else ""
            flat_raw = row[field_to_idx["flat_number"]].strip() if "flat_number" in field_to_idx and field_to_idx["flat_number"] < len(row) else ""
            res_type = row[field_to_idx["resident_type"]].strip() if "resident_type" in field_to_idx and field_to_idx["resident_type"] < len(row) else "Owner"

            row_errors: List[str] = []

            # Missing required fields
            if not full_name:
                row_errors.append("Missing full name")
            if not mobile_raw:
                row_errors.append("Missing mobile number")
            if not flat_raw:
                row_errors.append("Missing flat number")

            # Mobile validation
            clean_mob = re.sub(r"\D", "", mobile_raw)
            if clean_mob.startswith("91") and len(clean_mob) == 12:
                clean_mob = clean_mob[2:]
            if len(clean_mob) != 10:
                row_errors.append(f"Invalid mobile ({len(clean_mob)} digits instead of 10)")

            # Email validation
            if email_raw and not EMAIL_REGEX.match(email_raw):
                row_errors.append("Invalid email syntax")

            # Flat existence
            flat_obj = existing_flats.get(flat_raw.upper())
            if not flat_obj and flat_raw:
                row_errors.append(f"Flat '{flat_raw}' does not exist in this society")

            # Duplicate check
            is_dup = clean_mob in existing_mobiles
            if is_dup:
                dup_res = existing_mobiles[clean_mob]
                duplicate_rows.append({
                    "row_number": row_idx,
                    "name": full_name,
                    "mobile": clean_mob,
                    "flat": flat_raw,
                    "existing_resident": f"{dup_res.full_name} (ID #{dup_res.id})",
                })

            # Formatting checks
            if full_name.islower():
                formatting_suggestions.append(f"Row {row_idx}: Auto-capitalize '{full_name}' -> '{full_name.title()}'.")

            parsed_data = {
                "row_number": row_idx,
                "full_name": full_name.title() if full_name.islower() else full_name,
                "mobile": clean_mob,
                "email": email_raw,
                "flat_number": flat_raw,
                "flat_id": flat_obj.id if flat_obj else None,
                "resident_type": res_type.title(),
                "is_duplicate": is_dup,
            }

            if row_errors:
                invalid_rows.append({"row_number": row_idx, "data": parsed_data, "errors": row_errors})
            else:
                valid_rows.append(parsed_data)

        return {
            "total_rows_scanned": len(rows) - 1,
            "valid_count": len(valid_rows),
            "invalid_count": len(invalid_rows),
            "duplicate_count": len(duplicate_rows),
            "valid_rows": valid_rows[:20],  # preview slice
            "invalid_rows": invalid_rows,
            "duplicates": duplicate_rows,
            "formatting_suggestions": formatting_suggestions[:10],
            "ready_for_import": len(invalid_rows) == 0,
            "column_mapping_applied": column_mapping,
        }
