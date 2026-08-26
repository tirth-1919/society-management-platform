from app.models import (
    Resident,
    Document,
)


class TenantLeaseAutomationService:
    """
    Implements Phase 23 Tenant & Lease Management Automation:
    - Tenant ratio & occupancy breakdown
    - Police verification tracking
    - Lease expiry monitoring
    - Owner-tenant communication relays
    """

    @staticmethod
    def get_tenancy_breakdown_report(society_id):
        """Calculates society occupancy ratio: Owners vs Tenants."""
        all_active = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").all()
        owners = sum(1 for r in all_active if r.resident_type in ["Owner", "OWNER"])
        tenants = sum(1 for r in all_active if r.resident_type in ["Tenant", "TENANT"])
        total = len(all_active)

        return {
            "society_id": society_id,
            "total_active_residents": total,
            "owners_count": owners,
            "tenants_count": tenants,
            "tenant_percentage": round((tenants / total * 100), 1) if total > 0 else 0.0,
            "owner_percentage": round((owners / total * 100), 1) if total > 0 else 0.0,
        }

    @staticmethod
    def audit_tenant_police_verifications(society_id):
        """Scans active tenant residents for missing police verification documents."""
        tenants = Resident.query.filter_by(society_id=society_id, occupancy_status="Active").filter(
            Resident.resident_type.in_(["Tenant", "TENANT"])
        ).all()

        unverified = []
        for t in tenants:
            # Check if police verification document exists in Document vault
            doc = Document.query.filter_by(society_id=society_id).filter(
                (Document.title.ilike(f"%{t.full_name}%")) & (Document.title.ilike("%Police%"))
            ).first()

            if not doc:
                unverified.append({
                    "resident_id": t.id,
                    "resident_name": t.full_name,
                    "flat_number": t.flat.flat_number if t.flat else "-",
                    "mobile": t.mobile,
                    "verification_status": "MISSING_POLICE_VERIFICATION",
                })
        return unverified
