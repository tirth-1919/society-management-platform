"""
Smart Form Assistant
====================
Provides real-time form assistance:
- Field explanations
- Suspicious input detection
- Missing field detection
- Obvious formatting mistake detection
- Friendly validation error explanation
Never automatically changes submitted values — shows advisory suggestions only.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
PHONE_REGEX = re.compile(r"^[6-9]\d{9}$")
PINCODE_REGEX = re.compile(r"^\d{6}$")


class FormAssistantService:
    """
    Reusable Form Assistant engine for resident and admin forms.
    """

    FIELD_EXPLANATIONS: Dict[str, str] = {
        "full_name": "Enter the resident's full legal name as it appears on property / identity records.",
        "mobile": "Enter a valid 10-digit Indian mobile number (e.g., 9876543210) used for SMS OTPs and alerts.",
        "email": "Enter an active email address for official invoices, notices, and payment receipts.",
        "flat_number": "The physical door or flat identifier (e.g. '101', 'B-402').",
        "resident_type": "Select whether the resident is an Owner residing in the flat or a Tenant.",
        "is_primary": "Check if this member is the primary billing contact and official account owner.",
        "base_amount": "Monthly maintenance recurring charge for this flat.",
        "late_fee": "Late fee surcharge accrued due to settlement after the billing due date.",
        "advance_balance": "Pre-paid maintenance credit that gets automatically adjusted against future bills.",
        "maintenance_start_month": "The first month from which monthly maintenance billing begins (format: YYYY-MM).",
    }

    @classmethod
    def explain_field(cls, field_name: str) -> str:
        """Returns plain-English explanation of what a form field represents."""
        key = field_name.lower().strip().replace(" ", "_")
        return cls.FIELD_EXPLANATIONS.get(
            key, f"Enter the required value for {field_name.replace('_', ' ').title()}."
        )

    @classmethod
    def inspect_field_value(cls, field_name: str, value: Any) -> List[Dict[str, str]]:
        """
        Validates an individual field value and returns advisory suggestions.
        Does not mutate the value.
        """
        suggestions: List[Dict[str, str]] = []
        val_str = str(value or "").strip()
        key = field_name.lower().strip()

        if "email" in key and val_str:
            if not EMAIL_REGEX.match(val_str):
                suggestions.append({
                    "type": "format_error",
                    "severity": "warning",
                    "message": f"'{val_str}' does not appear to be a standard email address format (e.g. name@example.com).",
                })

        if ("mobile" in key or "phone" in key) and val_str:
            clean_digits = re.sub(r"\D", "", val_str)
            if clean_digits.startswith("91") and len(clean_digits) == 12:
                clean_digits = clean_digits[2:]
            if len(clean_digits) != 10:
                suggestions.append({
                    "type": "format_error",
                    "severity": "warning",
                    "message": f"Mobile number has {len(clean_digits)} digits. Standard Indian mobile numbers require exactly 10 digits.",
                })
            elif clean_digits[0] not in "6789":
                suggestions.append({
                    "type": "suspicious_input",
                    "severity": "info",
                    "message": "Indian mobile numbers typically start with 6, 7, 8, or 9.",
                })

        if "pincode" in key and val_str:
            clean_pin = re.sub(r"\D", "", val_str)
            if len(clean_pin) != 6:
                suggestions.append({
                    "type": "format_error",
                    "severity": "warning",
                    "message": "Pincode should be exactly 6 numeric digits.",
                })

        if ("amount" in key or "price" in key or "fee" in key) and val_str:
            try:
                amt = float(val_str)
                if amt < 0:
                    suggestions.append({
                        "type": "suspicious_input",
                        "severity": "danger",
                        "message": "Amount cannot be negative.",
                    })
                elif amt > 1000000:
                    suggestions.append({
                        "type": "suspicious_input",
                        "severity": "warning",
                        "message": f"Unusually large amount (₹{amt:,.2f}). Please verify digits.",
                    })
            except ValueError:
                suggestions.append({
                    "type": "format_error",
                    "severity": "danger",
                    "message": "Amount must be a valid numeric figure.",
                })

        if "name" in key and val_str:
            if any(char in val_str for char in ["<", ">", "{", "}", ";", "--", "/*"]):
                suggestions.append({
                    "type": "suspicious_input",
                    "severity": "danger",
                    "message": "Name contains invalid or suspicious characters.",
                })
            elif val_str.islower() and len(val_str) > 2:
                suggestions.append({
                    "type": "formatting_suggestion",
                    "severity": "info",
                    "message": f"Suggestion: Consider capitalising the name as '{val_str.title()}'.",
                })

        return suggestions

    @classmethod
    def inspect_form_data(cls, form_context: str, form_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Inspects an entire form submission payload and returns a comprehensive report.
        """
        field_issues: Dict[str, List[Dict[str, str]]] = {}
        missing_fields: List[str] = []

        # Required fields definition per form context
        required_map = {
            "registration": ["full_name", "mobile", "flat_number"],
            "resident_edit": ["full_name", "mobile"],
            "complaint": ["title", "description", "category"],
            "voucher": ["payee_name", "amount", "category"],
            "notice": ["title", "content"],
        }

        required_list = required_map.get(form_context, [])
        for req in required_list:
            if not form_data.get(req) or str(form_data.get(req)).strip() == "":
                missing_fields.append(req.replace("_", " ").title())

        for field_name, value in form_data.items():
            issues = cls.inspect_field_value(field_name, value)
            if issues:
                field_issues[field_name] = issues

        has_critical = any(
            any(i.get("severity") == "danger" for i in issues) for issues in field_issues.values()
        )

        return {
            "form_context": form_context,
            "is_valid": len(missing_fields) == 0 and not has_critical,
            "missing_required_fields": missing_fields,
            "field_suggestions": field_issues,
            "summary": (
                "Form contains input suggestions for your review."
                if (field_issues or missing_fields)
                else "All inputs look clean and well-formatted."
            ),
        }

    @classmethod
    def explain_validation_error(cls, error_message: str) -> str:
        """Translates technical database or validation errors into plain human language."""
        err = (error_message or "").lower()
        if "unique constraint" in err or "already exists" in err:
            if "mobile" in err:
                return "A resident account with this mobile number already exists in the system."
            if "email" in err:
                return "An account with this email address is already registered."
            if "flat" in err:
                return "This flat number is already created in the selected wing/block."
            return "A duplicate record with these unique details already exists."
        if "foreign key" in err or "not found" in err:
            return "The selected wing, block, flat, or resident could not be located in the database."
        if "not null" in err or "required" in err:
            return "Please ensure all required fields are filled before saving."
        return error_message
