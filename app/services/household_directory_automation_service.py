from app.models import (
    Flat,
    Resident,
    EmergencyContact,
    Dependent,
    Vehicle,
)


class HouseholdDirectoryAutomationService:
    """
    Implements Phase 29 Resident Directory & Household Member Automation:
    - Household profile aggregation (Primary resident, dependents, vehicles, emergency contacts)
    - Privacy-aware resident directory compiler
    - Primary contact synchronization
    """

    @staticmethod
    def get_unit_household_profile(flat_id, society_id):
        """Compiles complete household profile for a specific unit."""
        flat = Flat.query.filter_by(id=flat_id, society_id=society_id).first()
        if not flat:
            return None

        primary_resident = Resident.query.filter_by(flat_id=flat_id, society_id=society_id, is_primary=True).first()
        contacts = EmergencyContact.query.filter_by(resident_id=primary_resident.id).all() if primary_resident else []
        dependents = Dependent.query.filter_by(resident_id=primary_resident.id).all() if primary_resident else []
        vehicles = Vehicle.query.filter_by(flat_id=flat_id, society_id=society_id).all()

        return {
            "flat_id": flat.id,
            "flat_number": flat.flat_number,
            "occupancy_status": flat.occupancy_status,
            "primary_resident": {
                "id": primary_resident.id,
                "name": primary_resident.full_name,
                "type": primary_resident.resident_type,
                "mobile": primary_resident.mobile,
                "email": primary_resident.email,
            } if primary_resident else None,
            "emergency_contacts": [{"name": c.name, "relation": c.relation, "phone": c.phone} for c in contacts],
            "dependents": [{"name": d.name, "relation": d.relation, "age": d.age} for d in dependents],
            "vehicles": [{"number": v.vehicle_number, "type": v.vehicle_type, "model": v.brand_model} for v in vehicles],
        }

    @staticmethod
    def get_society_member_directory(society_id):
        """Generates privacy-safe resident directory list for verified community contacts."""
        residents = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").all()
        return [
            {
                "resident_id": r.id,
                "full_name": r.full_name,
                "flat_number": r.flat.flat_number if r.flat else "-",
                "building": r.flat.building.name if (r.flat and r.flat.building) else "-",
                "resident_type": r.resident_type,
            }
            for r in residents
        ]
