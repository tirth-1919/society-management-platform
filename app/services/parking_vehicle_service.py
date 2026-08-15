from app.models import db, ParkingSlot, Vehicle


class ParkingVehicleService:
    @staticmethod
    def register_vehicle(
        society_id,
        flat_id,
        vehicle_number,
        vehicle_type="Car",
        brand_model=None,
        color=None,
        resident_id=None,
        slot_id=None,
    ):
        """Registers a vehicle ensuring vehicle number uniqueness."""
        existing = Vehicle.query.filter_by(vehicle_number=vehicle_number).first()
        if existing:
            raise ValueError(f"Vehicle number {vehicle_number} is already registered")

        vehicle = Vehicle(
            society_id=society_id,
            flat_id=flat_id,
            resident_id=resident_id,
            vehicle_number=vehicle_number,
            vehicle_type=vehicle_type,
            brand_model=brand_model,
            color=color,
            parking_slot_id=slot_id,
        )
        db.session.add(vehicle)
        db.session.commit()
        return vehicle

    @staticmethod
    def allocate_parking_slot(slot_id, flat_id):
        """Allocates a parking slot to a flat, preventing double allocation."""
        slot = db.session.get(ParkingSlot, slot_id)
        if not slot:
            raise ValueError("Parking slot not found")

        if slot.flat_id and slot.flat_id != flat_id:
            raise ValueError(
                f"Parking slot {slot.slot_number} is already allocated to flat ID {slot.flat_id}"
            )

        slot.flat_id = flat_id
        slot.status = "Allocated"
        db.session.commit()
        return slot

