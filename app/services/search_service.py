from app.models import Resident, Flat, MaintenanceBill, Complaint, Visitor, Vehicle


class SearchService:
    @staticmethod
    def global_search(society_id, query_str):
        """
        Global search engine filtering residents, flats, bills, complaints, visitors, and vehicles
        strictly scoped to the active society_id.
        """
        if not query_str or len(query_str.strip()) < 2:
            return {
                "residents": [],
                "flats": [],
                "bills": [],
                "complaints": [],
                "visitors": [],
                "vehicles": [],
            }

        term = f"%{query_str.strip()}%"

        residents = (
            Resident.query.filter_by(society_id=society_id)
            .filter((Resident.full_name.ilike(term)) | (Resident.mobile.ilike(term)))
            .limit(10)
            .all()
        )

        flats = (
            Flat.query.filter_by(society_id=society_id)
            .filter(Flat.flat_number.ilike(term))
            .limit(10)
            .all()
        )

        bills = (
            MaintenanceBill.query.filter_by(society_id=society_id)
            .filter(
                (MaintenanceBill.bill_number.ilike(term))
                | (MaintenanceBill.billing_month.ilike(term))
            )
            .limit(10)
            .all()
        )

        complaints = (
            Complaint.query.filter_by(society_id=society_id)
            .filter(
                (Complaint.ticket_number.ilike(term)) | (Complaint.title.ilike(term))
            )
            .limit(10)
            .all()
        )

        visitors = (
            Visitor.query.filter_by(society_id=society_id)
            .filter((Visitor.visitor_name.ilike(term)) | (Visitor.mobile.ilike(term)))
            .limit(10)
            .all()
        )

        vehicles = (
            Vehicle.query.filter_by(society_id=society_id)
            .filter(Vehicle.vehicle_number.ilike(term))
            .limit(10)
            .all()
        )

        return {
            "residents": [
                {"id": r.id, "name": r.full_name, "mobile": r.mobile} for r in residents
            ],
            "flats": [
                {"id": f.id, "flat_number": f.flat_number, "floor": f.floor_number}
                for f in flats
            ],
            "bills": [
                {
                    "id": b.id,
                    "bill_number": b.bill_number,
                    "month": b.billing_month,
                    "amount": b.total_amount,
                    "status": b.status,
                }
                for b in bills
            ],
            "complaints": [
                {
                    "id": c.id,
                    "ticket": c.ticket_number,
                    "title": c.title,
                    "status": c.status,
                }
                for c in complaints
            ],
            "visitors": [
                {"id": v.id, "name": v.visitor_name, "purpose": v.purpose}
                for v in visitors
            ],
            "vehicles": [
                {"id": v.id, "vehicle_number": v.vehicle_number, "type": v.vehicle_type}
                for v in vehicles
            ],
        }
