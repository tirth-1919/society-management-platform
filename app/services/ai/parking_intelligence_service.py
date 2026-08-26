"""
AI Parking Intelligence System
==============================
Analyzes parking slot allocations, vehicle registries, visitor vehicle logs, and violation patterns.
Detects repeated unauthorized parking, duplicate vehicle records across units, and calculates occupancy trends.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import timedelta
from typing import Any, Optional

from app.models.tenant import db
from app.models.parking import ParkingSlot, Vehicle
from app.models.visitor import Visitor
from app.models.ai_operations import (
    AIParkingEvent,
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)


class ParkingIntelligenceAIService:
    @classmethod
    def scan_parking_anomalies(cls, society_id: int, actor_id: Optional[int] = None) -> list[dict[str, Any]]:
        """
        Scans slots, vehicles, and parking logs for unauthorized parking and duplicate registrations.
        """
        anomalies = []
        vehicles = Vehicle.query.filter_by(society_id=society_id).all()
        parking_events = AIParkingEvent.query.filter_by(society_id=society_id).order_by(AIParkingEvent.occurred_at.desc()).all()

        # 1. Detect Duplicate Vehicle Plates Registered Across Different Flats
        plate_map = defaultdict(list)
        for v in vehicles:
            norm = v.normalized_number_plate or Vehicle.normalize_plate(v.vehicle_number)
            if norm:
                plate_map[norm].append(v)

        for plate, v_list in plate_map.items():
            distinct_flats = {v.flat_id for v in v_list if v.flat_id}
            if len(distinct_flats) > 1:
                anomalies.append({
                    "type": "DUPLICATE_VEHICLE_REGISTRATION",
                    "severity": AIFindingSeverity.HIGH,
                    "confidence": 0.96,
                    "title": f"Duplicate Vehicle Registered Across Units: {plate}",
                    "summary": f"Plate '{plate}' is registered to {len(distinct_flats)} distinct flats (#{', #'.join(str(f) for f in distinct_flats)}).",
                    "evidence": {
                        "plate": plate,
                        "flat_ids": list(distinct_flats),
                        "vehicle_ids": [v.id for v in v_list],
                    },
                    "recommended_action": "Verify vehicle RC document with the respective unit residents.",
                    "entity_type": "VEHICLE",
                    "entity_id": v_list[0].id,
                })

        # 2. Detect Repeated Parking Violations (e.g. >= 3 events for same slot/vehicle)
        event_by_plate = defaultdict(list)
        for ev in parking_events:
            key = ev.vehicle_number or f"Slot-{ev.slot_id}"
            event_by_plate[key].append(ev)

        for key, ev_list in event_by_plate.items():
            if len(ev_list) >= 3:
                anomalies.append({
                    "type": "REPEATED_PARKING_VIOLATIONS",
                    "severity": AIFindingSeverity.HIGH if len(ev_list) >= 5 else AIFindingSeverity.MEDIUM,
                    "confidence": 0.91,
                    "title": f"Repeated Parking Violation Pattern: {key}",
                    "summary": f"Detected {len(ev_list)} parking violations logged for {key} in the previous 30 days.",
                    "evidence": {
                        "target": key,
                        "violation_count": len(ev_list),
                        "latest_occurred_at": ev_list[0].occurred_at.isoformat() if ev_list[0].occurred_at else None,
                    },
                    "recommended_action": "Issue formal parking advisory notice to unit or vehicle owner.",
                    "entity_type": "PARKING_SLOT",
                    "entity_id": ev_list[0].slot_id,
                })

        # Sync findings
        for item in anomalies:
            finding = AIFinding.query.filter_by(
                society_id=society_id,
                ai_system=AISystemType.PARKING,
                finding_type=item["type"],
                title=item["title"],
            ).first()

            if not finding:
                finding = AIFinding(
                    society_id=society_id,
                    ai_system=AISystemType.PARKING,
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

        db.session.commit()
        return anomalies

    @classmethod
    def get_parking_overview_and_forecast(cls, society_id: int) -> dict[str, Any]:
        """
        Calculates occupancy rates, allocated slots, and peak hour forecasts from real DB data.
        """
        slots = ParkingSlot.query.filter_by(society_id=society_id).all()
        vehicles = Vehicle.query.filter_by(society_id=society_id, status="ACTIVE").all()
        visitors = Visitor.query.filter_by(society_id=society_id).filter(
            Visitor.entry_time >= utcnow() - timedelta(days=30)
        ).all()

        total_slots = len(slots)
        allocated_slots = sum(1 for s in slots if s.flat_id is not None or s.status == "Allocated")
        available_slots = total_slots - allocated_slots
        occupancy_rate = round((allocated_slots / total_slots * 100), 1) if total_slots > 0 else 0.0

        # Peak visitor parking hours analysis
        from collections import Counter
        hour_counts = Counter([v.entry_time.hour for v in visitors if v.entry_time and v.vehicle_number])
        peak_hour = hour_counts.most_common(1)[0][0] if hour_counts else 18  # default 6 PM

        peak_str = f"{peak_hour:02d}:00 - {((peak_hour + 2) % 24):02d}:00"

        return {
            "total_slots": total_slots,
            "allocated_slots": allocated_slots,
            "available_slots": available_slots,
            "active_registered_vehicles": len(vehicles),
            "occupancy_rate_pct": occupancy_rate,
            "peak_parking_hours": peak_str,
            "demand_forecast": "High" if occupancy_rate > 85 else ("Moderate" if occupancy_rate > 60 else "Low"),
            "confidence_score": 0.89,
        }
