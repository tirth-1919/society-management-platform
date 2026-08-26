"""
AI Society Digital Twin Service
===============================
Unified operational graph representation of the society.
Connects Spaces (Wings, Blocks, Flats, Facilities, Parking),
People (Residents, Staff, Vendors, Visitors), Assets (Lifts, Generators, Pumps),
and Operations (Bills, Payments, Complaints, Work Orders, Documents, Energy).
Provides cross-system correlation and full multi-tenant isolation.
"""

from __future__ import annotations

import logging
from typing import Any

from app.models.tenant import db, Society, Building, Flat
from app.models.resident import Resident
from app.models.parking import ParkingSlot, Vehicle
from app.models.operations import Asset, WorkOrder, Vendor
from app.models.facility import Facility
from app.models.complaint import Complaint
from app.models.billing import MaintenanceBill
from app.models.ai_operations import AIFinding, AIFindingStatus
from app.services.ai.predictive_maintenance_service import PredictiveMaintenanceAIService

logger = logging.getLogger(__name__)


class DigitalTwinAIService:
    @classmethod
    def get_society_overview_graph(cls, society_id: int) -> dict[str, Any]:
        """
        Builds the top-level digital twin graph topology and aggregate statistics.
        """
        society = db.session.get(Society, society_id)
        if not society:
            return {"error": "Society not found", "nodes_count": 0}

        buildings = Building.query.filter_by(society_id=society_id).all()
        flats = Flat.query.filter_by(society_id=society_id).all()
        residents = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").all()
        assets = Asset.query.filter_by(society_id=society_id).all()
        slots = ParkingSlot.query.filter_by(society_id=society_id).all()
        vehicles = Vehicle.query.filter_by(society_id=society_id, status="ACTIVE").all()
        facilities = Facility.query.filter_by(society_id=society_id).all()
        vendors = Vendor.query.filter_by(society_id=society_id).all()
        active_findings = AIFinding.query.filter_by(
            society_id=society_id
        ).filter(AIFinding.status.in_([AIFindingStatus.NEW, AIFindingStatus.REVIEWING, AIFindingStatus.ACTION_REQUIRED])).all()

        nodes = []
        links = []

        # Society root node
        nodes.append({
            "id": f"society_{society.id}",
            "label": society.name,
            "type": "SOCIETY",
            "group": "society",
            "icon": "fa-building",
        })

        # Wing / Building nodes
        for b in buildings:
            b_node_id = f"wing_{b.id}"
            nodes.append({
                "id": b_node_id,
                "label": b.name,
                "type": "WING",
                "group": "space",
                "meta": {"floors": b.floors_count, "flats": len(b.flats)},
            })
            links.append({"source": f"society_{society.id}", "target": b_node_id, "relation": "CONTAINS"})

        # Asset nodes
        for a in assets:
            a_node_id = f"asset_{a.id}"
            nodes.append({
                "id": a_node_id,
                "label": a.asset_name,
                "type": "ASSET",
                "group": "asset",
                "status": a.status,
                "meta": {"category": a.category, "location": a.location},
            })
            links.append({"source": f"society_{society.id}", "target": a_node_id, "relation": "HOUSES_ASSET"})

        return {
            "society": {
                "id": society.id,
                "name": society.name,
                "city": society.city,
            },
            "metrics": {
                "total_wings": len(buildings),
                "total_flats": len(flats),
                "active_residents": len(residents),
                "total_assets": len(assets),
                "parking_slots": len(slots),
                "registered_vehicles": len(vehicles),
                "facilities": len(facilities),
                "active_vendors": len(vendors),
                "active_ai_findings": len(active_findings),
            },
            "nodes": nodes,
            "links": links,
        }

    @classmethod
    def get_entity_detail_view(cls, entity_type: str, entity_id: int, society_id: int) -> dict[str, Any]:
        """
        Inspects deep relationships and cross-system correlation for a selected node in the Digital Twin.
        """
        entity_type_upper = entity_type.upper()

        if entity_type_upper in ["FLAT", "UNIT"]:
            flat = Flat.query.filter_by(id=entity_id, society_id=society_id).first()
            if not flat:
                return {"error": "Flat not found"}

            residents = Resident.query.filter_by(flat_id=flat.id, society_id=society_id).all()
            vehicles = Vehicle.query.filter_by(flat_id=flat.id, society_id=society_id).all()
            complaints = Complaint.query.filter_by(flat_id=flat.id, society_id=society_id).order_by(Complaint.created_at.desc()).limit(5).all()
            bills = MaintenanceBill.query.filter_by(flat_id=flat.id, society_id=society_id).order_by(MaintenanceBill.created_at.desc()).limit(5).all()
            parking_slot = ParkingSlot.query.filter_by(flat_id=flat.id, society_id=society_id).first()

            return {
                "type": "FLAT",
                "id": flat.id,
                "title": f"Flat {flat.flat_number}",
                "wing": flat.building.name if flat.building else "N/A",
                "floor": flat.floor_number,
                "area_sqft": flat.area_sqft,
                "occupancy_status": flat.occupancy_status,
                "residents": [{"id": r.id, "name": r.full_name, "type": r.resident_type, "status": r.occupancy_status} for r in residents],
                "vehicles": [{"id": v.id, "plate": v.vehicle_number, "model": v.brand_model or v.make} for v in vehicles],
                "parking_slot": parking_slot.slot_number if parking_slot else "None",
                "recent_complaints": [{"id": c.id, "ticket": c.ticket_number, "title": c.title, "status": c.status} for c in complaints],
                "recent_bills": [{"id": b.id, "month": b.billing_month, "amount": b.total_amount, "status": b.status} for b in bills],
            }

        elif entity_type_upper == "ASSET":
            asset = Asset.query.filter_by(id=entity_id, society_id=society_id).first()
            if not asset:
                return {"error": "Asset not found"}

            risk_analysis = PredictiveMaintenanceAIService.analyze_asset_risk(asset, society_id)
            work_orders = WorkOrder.query.filter_by(society_id=society_id).filter(
                (WorkOrder.title.ilike(f"%{asset.asset_name}%")) | (WorkOrder.category == asset.category)
            ).order_by(WorkOrder.created_at.desc()).limit(5).all()

            vendor = Vendor.query.filter_by(id=asset.vendor_id, society_id=society_id).first() if asset.vendor_id else None

            # Cross-system correlation: check related complaints
            related_complaints = Complaint.query.filter_by(society_id=society_id).filter(
                (Complaint.title.ilike(f"%{asset.asset_name}%")) | (Complaint.category == asset.category)
            ).order_by(Complaint.created_at.desc()).limit(5).all()

            return {
                "type": "ASSET",
                "id": asset.id,
                "title": asset.asset_name,
                "category": asset.category,
                "location": asset.location,
                "status": asset.status,
                "vendor_name": vendor.company_name if vendor else "Unassigned",
                "purchase_date": asset.purchase_date.isoformat() if asset.purchase_date else None,
                "last_service_date": asset.last_service_date.isoformat() if asset.last_service_date else None,
                "next_service_due": asset.next_service_due.isoformat() if asset.next_service_due else None,
                "ai_risk": risk_analysis,
                "recent_work_orders": [{"id": w.id, "number": w.work_order_number, "title": w.title, "status": w.status} for w in work_orders],
                "correlated_complaints": [{"id": c.id, "ticket": c.ticket_number, "title": c.title, "status": c.status} for c in related_complaints],
            }

        elif entity_type_upper == "VEHICLE":
            veh = Vehicle.query.filter_by(id=entity_id, society_id=society_id).first()
            if not veh:
                return {"error": "Vehicle not found"}

            return {
                "type": "VEHICLE",
                "id": veh.id,
                "title": veh.vehicle_number,
                "make_model": veh.brand_model or f"{veh.make or ''} {veh.model or ''}",
                "flat_number": veh.flat.flat_number if veh.flat else "N/A",
                "owner_name": veh.resident.full_name if veh.resident else "N/A",
                "parking_slot": veh.parking_slot_number or (veh.parking_slot_rel.slot_number if veh.parking_slot_rel else "Unallocated"),
                "status": veh.status,
            }

        return {"error": f"Unsupported entity type: {entity_type}"}
