"""
AI Audit Logging Service
========================
Standardized audit logging for all AI Operations events:
- AI Analysis Run started/completed
- AI Finding generated, reviewed, dismissed, confirmed, action taken
- Investigation case created, updated, status transition
- Document verification, duplicate resolution actions
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional
from flask import request
from app.models.tenant import db
from app.models.user import AuditLog
from app.models.ai_operations import AIFindingFeedback
from app.utils import utcnow

logger = logging.getLogger(__name__)


class AIAuditService:
    @staticmethod
    def log_event(
        society_id: int,
        action: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        actor_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
        ip_address: Optional[str] = None,
    ) -> Optional[AuditLog]:
        try:
            ip = ip_address
            if not ip:
                try:
                    ip = request.remote_addr if request else "127.0.0.1"
                except Exception:
                    ip = "127.0.0.1"

            detail_payload = {
                "ai_audit": True,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "timestamp": utcnow().isoformat(),
                **(details or {}),
            }

            audit = AuditLog(
                society_id=society_id,
                user_id=actor_id,
                action=f"AI_{action.upper()}",
                details=json.dumps(detail_payload, default=str),
                ip_address=ip,
            )
            db.session.add(audit)
            db.session.commit()
            return audit
        except Exception as e:
            logger.error(f"Failed to record AI audit log: {e}")
            db.session.rollback()
            return None

    @staticmethod
    def record_feedback(
        society_id: int,
        finding_id: int,
        user_id: int,
        decision: str,
        feedback_notes: Optional[str] = None,
    ) -> Optional[AIFindingFeedback]:
        try:
            fb = AIFindingFeedback(
                society_id=society_id,
                finding_id=finding_id,
                user_id=user_id,
                decision=decision,
                feedback_notes=feedback_notes,
            )
            db.session.add(fb)
            db.session.commit()

            AIAuditService.log_event(
                society_id=society_id,
                action="FINDING_FEEDBACK",
                entity_type="AI_FINDING",
                entity_id=finding_id,
                actor_id=user_id,
                details={"decision": decision, "notes": feedback_notes},
            )
            return fb
        except Exception as e:
            logger.error(f"Failed to record finding feedback: {e}")
            db.session.rollback()
            return None
