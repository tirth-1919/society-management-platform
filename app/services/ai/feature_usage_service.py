"""
Feature Usage Analytics Service
===============================
Tracks safe aggregate telemetry to identify:
- Popular features
- Rarely used features
- Unused features
Collects strictly non-personal aggregate usage statistics (feature names, actions, counts).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.utils import utcnow

logger = logging.getLogger(__name__)

# Aggregate in-memory feature usage store
_FEATURE_USAGE_STORE: Dict[str, Dict[str, Any]] = {}

ALL_STANDARD_FEATURES = [
    "Resident Directory",
    "Maintenance Billing",
    "Payment Gateway (Razorpay)",
    "Payment Reconciliation",
    "Complaint Desk",
    "Visitor Security Passes",
    "Facility Booking",
    "Announcements & Circulars",
    "Document Vault",
    "Accounting Vouchers",
    "Inventory & Assets",
    "Society Health Audit",
    "Automation Engine",
    "Data Quality Center",
    "CSV Import Assistant",
    "Command Palette (Ctrl+K)",
]


class FeatureUsageService:
    """Feature Usage Analytics Engine."""

    @classmethod
    def record_usage(
        cls,
        feature_name: str,
        action: str = "open",
        society_id: Optional[int] = None,
    ) -> None:
        """Records a single usage occurrence for a feature."""
        key = feature_name.strip()
        now_str = utcnow().strftime("%Y-%m-%d %H:%M:%S")

        if key not in _FEATURE_USAGE_STORE:
            _FEATURE_USAGE_STORE[key] = {
                "feature_name": key,
                "usage_count": 0,
                "actions": {},
                "last_used": now_str,
                "first_used": now_str,
            }

        _FEATURE_USAGE_STORE[key]["usage_count"] += 1
        _FEATURE_USAGE_STORE[key]["last_used"] = now_str

        actions_dict = _FEATURE_USAGE_STORE[key]["actions"]
        actions_dict[action] = actions_dict.get(action, 0) + 1

    @classmethod
    def get_analytics_summary(cls, society_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Generates aggregate usage breakdown:
        - Popular features (> 5 uses)
        - Rarely used features (1-4 uses)
        - Unused features (0 recorded uses)
        """
        popular: List[Dict[str, Any]] = []
        rarely_used: List[Dict[str, Any]] = []
        unused: List[str] = []

        recorded_features = set(_FEATURE_USAGE_STORE.keys())

        for fname, data in _FEATURE_USAGE_STORE.items():
            count = data["usage_count"]
            item = {
                "feature_name": fname,
                "usage_count": count,
                "last_used": data["last_used"],
                "top_action": max(data["actions"].items(), key=lambda x: x[1])[0] if data["actions"] else "open",
            }
            if count >= 5:
                popular.append(item)
            else:
                rarely_used.append(item)

        for std_feature in ALL_STANDARD_FEATURES:
            if std_feature not in recorded_features:
                unused.append(std_feature)

        popular.sort(key=lambda x: x["usage_count"], reverse=True)
        rarely_used.sort(key=lambda x: x["usage_count"], reverse=True)

        return {
            "total_interactions": sum(d["usage_count"] for d in _FEATURE_USAGE_STORE.values()),
            "popular_features": popular,
            "rarely_used_features": rarely_used,
            "unused_features": unused,
        }
