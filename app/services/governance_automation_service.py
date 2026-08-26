from app.models import (
    Building,
    Flat,
    MaintenanceBill,
)


class GovernanceAutomationService:
    """
    Implements Phase 32 Multi-Wing & Multi-Block Governance Automation:
    - Wing & Block performance breakdown (Occupancy, Total Billed, Collection %)
    - Inter-wing collection benchmark ranking
    - Zonal maintenance dispatch coordination
    """

    @staticmethod
    def get_wing_governance_report(society_id):
        """Generates comprehensive wing-by-wing governance and collection summary."""
        wings = Building.query.filter_by(society_id=society_id).all()
        wing_reports = []

        for w in wings:
            flats = Flat.query.filter_by(society_id=society_id, building_id=w.id).all()
            flat_ids = [f.id for f in flats]
            occupied = sum(1 for f in flats if f.occupancy_status == "Occupied")

            bills = MaintenanceBill.query.filter_by(society_id=society_id).filter(
                MaintenanceBill.flat_id.in_(flat_ids)
            ).all() if flat_ids else []

            billed = sum(b.total_amount for b in bills)
            collected = sum(b.amount_paid for b in bills)
            efficiency = round((collected / billed * 100), 1) if billed > 0 else 100.0

            wing_reports.append({
                "wing_id": w.id,
                "wing_name": w.name,
                "total_flats": len(flats),
                "occupied_flats": occupied,
                "total_billed": round(billed, 2),
                "total_collected": round(collected, 2),
                "collection_efficiency": efficiency,
            })

        # Rank from highest collection efficiency to lowest
        wing_reports.sort(key=lambda x: x["collection_efficiency"], reverse=True)
        return {
            "society_id": society_id,
            "total_wings": len(wings),
            "wings": wing_reports,
        }
