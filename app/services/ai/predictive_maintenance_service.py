"""
AI Predictive Maintenance System
================================
Analyzes physical assets (lifts, generators, pumps, CCTV, fire equipment),
work order failure history, service intervals, asset age, and vendor track records.
Calculates failure risk probabilities and recommends preventive maintenance work orders.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any, Optional

from app.models.tenant import db
from app.models.operations import Asset, WorkOrder
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.services.ai.ai_audit_service import AIAuditService
from app.utils import utcnow

logger = logging.getLogger(__name__)


class PredictiveMaintenanceAIService:
    @classmethod
    def analyze_asset_risk(cls, asset: Asset, society_id: int) -> dict[str, Any]:
        """
        Calculates failure risk, priority, confidence, and preventive recommendations
        based strictly on real persisted asset and work order records.
        """
        now = utcnow().date()
        work_orders = WorkOrder.query.filter_by(
            society_id=society_id
        ).filter(
            (WorkOrder.title.ilike(f"%{asset.asset_name}%")) |
            (WorkOrder.description.ilike(f"%{asset.asset_name}%")) |
            (WorkOrder.category == asset.category)
        ).order_by(WorkOrder.created_at.desc()).all()

        total_wo_count = len(work_orders)
        recent_cutoff = now - timedelta(days=90)
        recent_failures = [
            wo for wo in work_orders
            if wo.created_at and wo.created_at.date() >= recent_cutoff
        ]
        recent_fail_count = len(recent_failures)

        reasons = []
        base_risk = 15.0

        # Check service overdue
        days_overdue = 0
        if asset.next_service_due:
            if asset.next_service_due < now:
                days_overdue = (now - asset.next_service_due).days
                base_risk += min(45.0, 20.0 + (days_overdue * 0.5))
                reasons.append(f"Service overdue by {days_overdue} days (due {asset.next_service_due})")
            else:
                days_until = (asset.next_service_due - now).days
                if days_until <= 7:
                    base_risk += 15.0
                    reasons.append(f"Scheduled service due within {days_until} days")
        elif not asset.last_service_date:
            base_risk += 20.0
            reasons.append("No previous service record logged on file")

        # Failure frequency impact
        if recent_fail_count >= 3:
            base_risk += 35.0
            reasons.append(f"{recent_fail_count} work orders/repairs in the previous 90 days")
        elif recent_fail_count >= 1:
            base_risk += 15.0
            reasons.append(f"{recent_fail_count} recent repair order(s) recorded")

        # Current asset status impact
        if asset.status in ["Maintenance Required", "Under Repair"]:
            base_risk += 30.0
            reasons.append(f"Asset is currently flagged as '{asset.status}'")

        # Calculate asset age
        asset_age_years = 0.0
        if asset.purchase_date:
            asset_age_days = (now - asset.purchase_date).days
            asset_age_years = round(asset_age_days / 365.25, 1)
            if asset_age_years > 5:
                base_risk += min(15.0, asset_age_years * 1.5)
                reasons.append(f"Operating age is {asset_age_years} years")

        # Bounding risk score between 5% and 98%
        risk_score = min(98.0, max(5.0, base_risk))
        failure_prob = round(risk_score, 1)

        # Priority calculation
        if risk_score >= 75.0 or asset.status == "Maintenance Required":
            priority = AIFindingSeverity.HIGH if risk_score < 90.0 else AIFindingSeverity.CRITICAL
            rec_action = f"Schedule immediate preventive inspection and service for {asset.asset_name}."
        elif risk_score >= 45.0:
            priority = AIFindingSeverity.MEDIUM
            rec_action = f"Plan scheduled maintenance review for {asset.asset_name} within next 14 days."
        else:
            priority = AIFindingSeverity.LOW
            rec_action = f"Asset {asset.asset_name} operating within normal operational parameters."

        if not reasons:
            reasons.append("Routine operational telemetry and service schedule are currently on track.")

        # Data sufficiency check
        has_sufficient_data = bool(asset.purchase_date or asset.last_service_date or total_wo_count > 0)
        confidence = 0.92 if (total_wo_count >= 2 and asset.last_service_date) else (0.80 if has_sufficient_data else 0.55)

        return {
            "asset_id": asset.id,
            "asset_name": asset.asset_name,
            "category": asset.category,
            "location": asset.location or "Common Area",
            "status": asset.status,
            "risk_score": failure_prob,
            "failure_probability": failure_prob,
            "maintenance_priority": priority,
            "confidence": confidence,
            "confidence_percent": int(round(confidence * 100)),
            "reasons": reasons,
            "recommended_action": rec_action,
            "recent_failures_count": recent_fail_count,
            "total_work_orders": total_wo_count,
            "last_service_date": asset.last_service_date.isoformat() if asset.last_service_date else None,
            "next_service_due": asset.next_service_due.isoformat() if asset.next_service_due else None,
            "has_sufficient_data": has_sufficient_data,
            "data_sufficiency_note": None if has_sufficient_data else "Insufficient historical records for high-confidence forecast.",
        }


    @classmethod
    def run_society_maintenance_analysis(
        cls, society_id: int, actor_id: Optional[int] = None
    ) -> list[dict[str, Any]]:
        """
        Scans all assets for the society, updates risk scores, and generates/updates AIFinding records.
        """
        assets = Asset.query.filter_by(society_id=society_id).all()
        results = []

        for asset in assets:
            analysis = cls.analyze_asset_risk(asset, society_id)
            results.append(analysis)

            # Generate finding if medium, high, or critical risk
            if analysis["maintenance_priority"] in [AIFindingSeverity.HIGH, AIFindingSeverity.CRITICAL, AIFindingSeverity.MEDIUM]:
                finding = AIFinding.query.filter_by(
                    society_id=society_id,
                    ai_system=AISystemType.MAINTENANCE,
                    entity_type="ASSET",
                    entity_id=asset.id,
                ).filter(AIFinding.status.in_([AIFindingStatus.NEW, AIFindingStatus.REVIEWING, AIFindingStatus.ACTION_REQUIRED])).first()

                title = f"High Failure Risk Detected: {asset.asset_name}" if analysis["maintenance_priority"] != AIFindingSeverity.MEDIUM else f"Preventive Service Needed: {asset.asset_name}"
                summary = f"{asset.asset_name} ({asset.category}) has an estimated failure probability of {analysis['failure_probability']}%. Key reasons: {'; '.join(analysis['reasons'][:2])}."

                if not finding:
                    finding = AIFinding(
                        society_id=society_id,
                        ai_system=AISystemType.MAINTENANCE,
                        entity_type="ASSET",
                        entity_id=asset.id,
                        finding_type="HIGH_FAILURE_RISK",
                        severity=analysis["maintenance_priority"],
                        confidence_score=analysis["confidence"],
                        title=title,
                        summary=summary,
                        recommended_action=analysis["recommended_action"],
                        status=AIFindingStatus.NEW,
                    )
                    finding.set_evidence(analysis)
                    db.session.add(finding)
                else:
                    finding.severity = analysis["maintenance_priority"]
                    finding.confidence_score = analysis["confidence"]
                    finding.title = title
                    finding.summary = summary
                    finding.recommended_action = analysis["recommended_action"]
                    finding.set_evidence(analysis)

        db.session.commit()

        if actor_id:
            AIAuditService.log_event(
                society_id=society_id,
                action="MAINTENANCE_SCAN",
                entity_type="MAINTENANCE_SCAN",
                actor_id=actor_id,
                details={"assets_scanned": len(assets), "high_risk_count": sum(1 for r in results if r['risk_score'] >= 50)},
            )

        return results

    @classmethod
    def create_work_order_from_finding(
        cls, finding_id: int, society_id: int, actor_id: int, vendor_id: Optional[int] = None, notes: Optional[str] = None
    ) -> Optional[WorkOrder]:
        """
        Workflow: Converts an AI Maintenance Finding into a real WorkOrder task and assigns technician/vendor.
        """
        finding = AIFinding.query.filter_by(id=finding_id, society_id=society_id).first()
        if not finding or finding.entity_type != "ASSET":
            return None

        asset = Asset.query.filter_by(id=finding.entity_id, society_id=society_id).first()
        if not asset:
            return None

        import uuid
        wo_num = f"WO-AI-{uuid.uuid4().hex[:6].upper()}"
        wo = WorkOrder(
            work_order_number=wo_num,
            society_id=society_id,
            title=f"AI Preventive Maintenance: {asset.asset_name}",
            description=f"Generated from AI Finding #{finding.id}.\n{finding.summary}\nRecommended: {finding.recommended_action}\nNotes: {notes or 'Initiated from AI Operations Center'}",
            category=asset.category,
            priority=finding.severity.capitalize() if finding.severity else "High",
            assigned_vendor_id=vendor_id or asset.vendor_id,
            status="Assigned" if (vendor_id or asset.vendor_id) else "Created",
            due_date=utcnow().date() + timedelta(days=3 if finding.severity == AIFindingSeverity.CRITICAL else 7),
        )
        db.session.add(wo)

        finding.status = AIFindingStatus.ACTION_REQUIRED
        finding.action_taken = f"Created Work Order #{wo_num}"
        finding.reviewed_by_id = actor_id
        finding.reviewed_at = utcnow()
        db.session.commit()

        AIAuditService.log_event(
            society_id=society_id,
            action="CREATE_WORK_ORDER",
            entity_type="WORK_ORDER",
            entity_id=wo.id,
            actor_id=actor_id,
            details={"work_order_number": wo_num, "finding_id": finding.id, "asset_id": asset.id},
        )

        return wo
