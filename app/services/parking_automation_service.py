from app.models import (
    db,
    ParkingSlot,
    Vehicle,
    Complaint,
    WorkOrder,
)
from app.services.notification_service import NotificationService
from app.utils import utcnow
from datetime import timedelta
from sqlalchemy import func
import secrets


class ParkingAutomationService:
    """
    Implements Phase 7 Parking Automation (Features 101–110):
    101. Parking allocation conflict detection
    102. Duplicate parking-slot detection
    103. Expired parking allocation detection
    104. Parking renewal reminder
    105. Parking availability report
    106. Unauthorized-parking complaint detection
    107. Parking violation task
    108. Resident parking notification
    109. Monthly parking report
    110. Vacant parking detection
    """

    @staticmethod
    def detect_allocation_conflicts(society_id):
        """Feature 101: Detects parking allocation conflicts (e.g. flat assigned multiple slots or unassigned vehicles)."""
        conflicts = []
        # 1. Flat assigned to multiple car slots
        q = db.session.query(
            ParkingSlot.flat_id,
            func.count(ParkingSlot.id).label("slot_count")
        ).filter(
            ParkingSlot.society_id == society_id,
            ParkingSlot.flat_id.isnot(None),
            ParkingSlot.slot_type == "Car"
        ).group_by(ParkingSlot.flat_id).having(func.count(ParkingSlot.id) > 1).all()

        for c in q:
            conflicts.append({"flat_id": c.flat_id, "slot_count": c.slot_count, "conflict_type": "MULTIPLE_CAR_SLOTS"})

        # 2. Vehicles without valid parking slot
        unallocated_vehicles = Vehicle.query.filter_by(society_id=society_id).filter(
            (Vehicle.parking_slot_id.is_(None)) | (Vehicle.parking_slot_id == 0)
        ).all()
        for v in unallocated_vehicles:
            conflicts.append({"vehicle_number": v.vehicle_number, "flat_id": v.flat_id, "conflict_type": "UNALLOCATED_VEHICLE"})

        return conflicts

    @staticmethod
    def detect_duplicate_slots(society_id):
        """Feature 102: Identifies duplicate parking slot numbers."""
        q = db.session.query(
            ParkingSlot.slot_number,
            func.count(ParkingSlot.id).label("count")
        ).filter(ParkingSlot.society_id == society_id).group_by(ParkingSlot.slot_number).having(func.count(ParkingSlot.id) > 1).all()

        return [{"slot_number": d.slot_number, "duplicate_count": d.count} for d in q]

    @staticmethod
    def get_parking_availability_report(society_id):
        """Feature 105: Returns total, allocated, vacant, and reserved parking slots."""
        slots = ParkingSlot.query.filter_by(society_id=society_id).all()
        total = len(slots)
        allocated = sum(1 for s in slots if s.status == "Allocated" or s.flat_id)
        vacant = sum(1 for s in slots if s.status in ["Available", "Vacant"] and not s.flat_id)
        reserved = sum(1 for s in slots if s.status == "Reserved")

        return {
            "society_id": society_id,
            "total_slots": total,
            "allocated_slots": allocated,
            "vacant_slots": vacant,
            "reserved_slots": reserved,
            "occupancy_rate": round((allocated / total * 100), 1) if total > 0 else 0.0,
        }

    @staticmethod
    def detect_vacant_slots(society_id):
        """Feature 110: Returns all unallocated vacant parking slots."""
        vacant = ParkingSlot.query.filter_by(society_id=society_id).filter(
            (ParkingSlot.flat_id.is_(None)) | (ParkingSlot.status.in_(["Available", "Vacant"]))
        ).all()
        return [
            {"slot_id": s.id, "slot_number": s.slot_number, "location": s.location_block, "type": s.slot_type}
            for s in vacant
        ]

    @staticmethod
    def process_parking_violations(society_id):
        """
        Features 106 & 107:
        Identifies unauthorized parking complaints and automatically creates security violation tasks.
        """
        complaints = Complaint.query.filter_by(society_id=society_id).filter(
            Complaint.status.in_(["Submitted", "Assigned"]),
            (Complaint.category.ilike("%Parking%")) | (Complaint.title.ilike("%Parking%"))
        ).all()

        tasks_created = 0
        for c in complaints:
            existing = WorkOrder.query.filter_by(society_id=society_id, category="Parking").filter(
                WorkOrder.description.contains(f"Ticket #{c.ticket_number}")
            ).first()

            if not existing:
                wo = WorkOrder(
                    work_order_number=f"WO-PRK-{society_id}-{secrets.token_hex(2).upper()}",
                    society_id=society_id,
                    title=f"Parking Violation: {c.title}",
                    description=f"Resolve parking complaint Ticket #{c.ticket_number}: {c.description}. Verify vehicle permit with security.",
                    category="Parking",
                    priority="High",
                    status="Assigned",
                    due_date=utcnow().date() + timedelta(days=1),
                )
                db.session.add(wo)
                tasks_created += 1

        db.session.commit()
        return {"parking_complaints_count": len(complaints), "violation_tasks_created": tasks_created}

    @staticmethod
    def send_parking_notification(resident_user, slot_number, vehicle_number):
        """Feature 108: Sends parking slot allocation notification to resident."""
        NotificationService.send_notification(
            recipient=resident_user.mobile or resident_user.email or "N/A",
            message=f"Parking Allocation Confirmed: Slot #{slot_number} is assigned to your vehicle {vehicle_number}. Please ensure parking within marked bay.",
            channel="In-App",
            society_id=resident_user.society_id,
            user_id=resident_user.id,
            category="General",
        )
        return True

    @staticmethod
    def generate_monthly_parking_report(society_id):
        """Feature 109: Generates comprehensive monthly parking report."""
        avail = ParkingAutomationService.get_parking_availability_report(society_id)
        conflicts = ParkingAutomationService.detect_allocation_conflicts(society_id)
        vehicles_count = Vehicle.query.filter_by(society_id=society_id).count()

        return {
            "society_id": society_id,
            "availability": avail,
            "registered_vehicles": vehicles_count,
            "allocation_conflicts_count": len(conflicts),
            "conflicts": conflicts,
            "month": utcnow().strftime("%Y-%m"),
        }
