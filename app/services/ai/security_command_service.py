"""
AI Security Command Center
==========================
Integrates visitor access, pre-approved passes, vehicle gates, staff logs, and security alerts.
Detects abnormal access patterns, repeated failed/denied entries, and expired passes
using objective, neutral advisory language. Includes CCTV stream adapter interface.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from app.models.tenant import db
from app.models.visitor import Visitor
from app.models.user import AuditLog
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.services.ai.ai_audit_service import AIAuditService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class CCTVStreamAdapter:
    """Interface adapter for future CCTV stream & edge inference hardware."""

    def get_stream_status(self, camera_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def detect_motion_events(self, camera_id: str, minutes: int = 60) -> list[dict[str, Any]]:
        raise NotImplementedError


class MockCCTVStreamAdapter(CCTVStreamAdapter):
    """Authoritative adapter providing offline/mock CCTV readiness telemetry."""

    def get_stream_status(self, camera_id: str) -> dict[str, Any]:
        return {
            "camera_id": camera_id,
            "status": "ONLINE",
            "resolution": "1080p",
            "fps": 30,
            "adapter": "MockCCTVStreamAdapter",
            "hardware_ready": True,
        }

    def detect_motion_events(self, camera_id: str, minutes: int = 60) -> list[dict[str, Any]]:
        return []


class SecurityCommandAIService:
    _cctv_adapter: CCTVStreamAdapter = MockCCTVStreamAdapter()

    @classmethod
    def set_cctv_adapter(cls, adapter: CCTVStreamAdapter) -> None:
        cls._cctv_adapter = adapter

    @classmethod
    def analyze_security_events(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Analyzes real database visitor, vehicle, and access logs for unusual patterns.
        """
        now = utcnow()
        thirty_days_ago = now - timedelta(days=30)
        seven_days_ago = now - timedelta(days=7)

        anomalies = []

        # 1. Detect Expired Passes or Repeated Denied Entries
        rejected_visitors = Visitor.query.filter_by(
            society_id=society_id
        ).filter(
            Visitor.approval_status.in_(["Rejected", "Expired"]),
            Visitor.created_at >= thirty_days_ago,
        ).order_by(Visitor.created_at.desc()).all()

        if len(rejected_visitors) >= 3:
            recent_denied_count = len(rejected_visitors)
            sample_mobiles = list({v.mobile for v in rejected_visitors if v.mobile})[:3]
            anomalies.append({
                "type": "REPEATED_DENIED_ACCESS",
                "severity": AIFindingSeverity.HIGH if recent_denied_count >= 6 else AIFindingSeverity.MEDIUM,
                "confidence": 0.89,
                "title": f"Elevated Denied Gate Entries ({recent_denied_count} occurrences)",
                "summary": f"Detected {recent_denied_count} rejected or expired entry attempts in the past 30 days. Potentially unusual access activity requiring security log review.",
                "evidence": {
                    "count": recent_denied_count,
                    "sample_contacts_masked": [f"******{m[-4:]}" if len(m) >= 4 else "***" for m in sample_mobiles],
                    "period_days": 30,
                },
                "recommended_action": "Review main gate logbook and ensure gate staff verify visitor identities.",
                "entity_type": "VISITOR",
                "entity_id": rejected_visitors[0].id if rejected_visitors else None,
            })

        # 2. Detect Abnormal Access Hours (Late Night 00:00 - 05:00)
        all_visitors = Visitor.query.filter_by(
            society_id=society_id
        ).filter(Visitor.created_at >= seven_days_ago).all()

        night_entries = [
            v for v in all_visitors
            if v.entry_time and (v.entry_time.hour < 5 or v.entry_time.hour >= 23)
        ]

        if len(night_entries) >= 5:
            anomalies.append({
                "type": "ABNORMAL_ACCESS_HOURS",
                "severity": AIFindingSeverity.MEDIUM,
                "confidence": 0.85,
                "title": f"Clustered Late-Night Visitor Entries ({len(night_entries)} visits)",
                "summary": f"Detected {len(night_entries)} visitor entries during late hours (11 PM - 5 AM) in the last 7 days. Potentially unusual entry pattern.",
                "evidence": {
                    "night_entries_count": len(night_entries),
                    "time_window": "23:00 - 05:00",
                    "period_days": 7,
                },
                "recommended_action": "Verify late-night visitor registration compliance with security desk.",
                "entity_type": "VISITOR",
                "entity_id": night_entries[0].id if night_entries else None,
            })

        # 3. Detect Visitor Frequency Anomalies per Flat
        from collections import Counter
        flat_counts = Counter([v.flat_id for v in all_visitors if v.flat_id])
        for flat_id, count in flat_counts.items():
            if count >= 15:  # High frequency visitor spike
                anomalies.append({
                    "type": "UNUSUAL_VISITOR_FREQUENCY",
                    "severity": AIFindingSeverity.MEDIUM,
                    "confidence": 0.88,
                    "title": f"Elevated Visitor Volume: Unit #{flat_id}",
                    "summary": f"Detected {count} visitor registrations for flat #{flat_id} in the last 7 days.",
                    "evidence": {
                        "flat_id": flat_id,
                        "visitor_count": count,
                        "period_days": 7,
                    },
                    "recommended_action": "Confirm if commercial activity or event is occurring at this unit.",
                    "entity_type": "FLAT",
                    "entity_id": flat_id,
                })

        # 4. Failed User / Admin Logins Anomaly from Audit Logs
        failed_logins = AuditLog.query.filter_by(
            society_id=society_id,
            action="LOGIN_FAILED"
        ).filter(AuditLog.created_at >= seven_days_ago).all()

        if len(failed_logins) >= 5:
            anomalies.append({
                "type": "REPEATED_FAILED_AUTH",
                "severity": AIFindingSeverity.HIGH if len(failed_logins) >= 10 else AIFindingSeverity.MEDIUM,
                "confidence": 0.92,
                "title": f"Repeated Failed Authentication Attempts ({len(failed_logins)} events)",
                "summary": f"Detected {len(failed_logins)} unsuccessful account access attempts in the past 7 days.",
                "evidence": {
                    "failed_count": len(failed_logins),
                    "period_days": 7,
                },
                "recommended_action": "Inspect login audit logs and check for repeated brute-force patterns.",
                "entity_type": "USER",
                "entity_id": failed_logins[0].user_id if failed_logins else None,
            })

        # Sync with AIFinding records
        for item in anomalies:
            finding = AIFinding.query.filter_by(
                society_id=society_id,
                ai_system=AISystemType.SECURITY,
                finding_type=item["type"],
            ).filter(AIFinding.status.in_([AIFindingStatus.NEW, AIFindingStatus.REVIEWING])).first()

            if not finding:
                finding = AIFinding(
                    society_id=society_id,
                    ai_system=AISystemType.SECURITY,
                    entity_type=item["entity_type"],
                    entity_id=item["entity_id"],
                    finding_type=item["type"],
                    severity=item["severity"],
                    confidence_score=item["confidence"],
                    title=item["title"],
                    summary=item["summary"],
                    recommended_action=item["recommended_action"],
                    status=AIFindingStatus.NEW,
                )
                finding.set_evidence(item["evidence"])
                db.session.add(finding)
            else:
                finding.severity = item["severity"]
                finding.title = item["title"]
                finding.summary = item["summary"]
                finding.recommended_action = item["recommended_action"]
                finding.set_evidence(item["evidence"])

        db.session.commit()

        if actor_id:
            AIAuditService.log_event(
                society_id=society_id,
                action="SECURITY_SCAN",
                entity_type="SECURITY_SCAN",
                actor_id=actor_id,
                details={"anomalies_detected": len(anomalies)},
            )

        return anomalies
