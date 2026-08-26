from app.models import (
    db,
    Asset,
    Vendor,
    WorkOrder,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import timedelta
import secrets


class AssetAutomationService:
    """
    Implements Phase 9 Asset Automation (Features 121–130):
    121. Asset warranty tracking
    122. Warranty-expiry reminder
    123. AMC-expiry reminder
    124. Pre-expiry maintenance task
    125. Overdue asset-maintenance detection
    126. Asset maintenance schedule
    127. Asset depreciation reminder if supported by existing accounting design
    128. Missing asset information detection
    129. Annual asset audit
    130. Asset health report
    """

    @staticmethod
    def scan_expiries_and_service_due(society_id, days_threshold=30):
        """
        Features 121, 122, 123, 124, 125:
        Scans asset warranty expiries, vendor AMC expiries, overdue services,
        and generates pre-expiry maintenance work orders.
        """
        now = utcnow().date()
        cutoff = now + timedelta(days=days_threshold)

        assets = Asset.query.filter_by(society_id=society_id).all()
        vendors = Vendor.query.filter_by(society_id=society_id, status="Active").all()

        expiring_warranties = []
        expiring_amcs = []
        overdue_services = []
        tasks_created = 0
        alerts_created = 0

        # 1. Asset warranty & service scan
        for a in assets:
            # Overdue service check (Feature 125)
            if a.next_service_due and a.next_service_due < now:
                overdue_services.append(a)
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="ASSET_SERVICE_OVERDUE",
                    severity="CRITICAL",
                    title=f"Service Overdue: {a.asset_name}",
                    message=f"Asset '{a.asset_name}' ({a.category}) service was due on {a.next_service_due}. Immediate preventive service required.",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_created += 1

            # Warranty expiry check (Feature 122 & 124)
            if a.warranty_expiry and now <= a.warranty_expiry <= cutoff:
                expiring_warranties.append(a)
                # Create pre-expiry inspection task (Feature 124)
                existing_wo = WorkOrder.query.filter_by(society_id=society_id, category=a.category).filter(
                    WorkOrder.description.contains(f"pre-expiry inspection for {a.asset_name}")
                ).first()
                if not existing_wo:
                    wo = WorkOrder(
                        work_order_number=f"WO-EXP-{society_id}-{secrets.token_hex(2).upper()}",
                        society_id=society_id,
                        title=f"Warranty Pre-Expiry Inspection: {a.asset_name}",
                        description=f"Conduct pre-expiry inspection for {a.asset_name} before warranty expires on {a.warranty_expiry}.",
                        category=a.category,
                        priority="High",
                        status="Assigned",
                        due_date=a.warranty_expiry,
                    )
                    db.session.add(wo)
                    tasks_created += 1

        # 2. Vendor AMC expiry scan (Feature 123)
        for v in vendors:
            if v.contract_end and now <= v.contract_end <= cutoff:
                expiring_amcs.append(v)
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="AMC_EXPIRING_SOON",
                    severity="WARNING",
                    title=f"AMC Contract Expiring: {v.company_name}",
                    message=f"AMC contract for {v.company_name} ({v.category}) expires on {v.contract_end}. Review renewal terms.",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_created += 1

        db.session.commit()
        return {
            "total_assets_scanned": len(assets),
            "expiring_warranties_count": len(expiring_warranties),
            "expiring_amcs_count": len(expiring_amcs),
            "overdue_services_count": len(overdue_services),
            "tasks_created": tasks_created,
            "alerts_created": alerts_created,
        }

    @staticmethod
    def get_asset_maintenance_schedule(society_id):
        """Feature 126: Generates forward maintenance schedule for all assets."""
        assets = Asset.query.filter_by(society_id=society_id).order_by(Asset.next_service_due.asc()).all()
        return [
            {
                "asset_id": a.id,
                "asset_name": a.asset_name,
                "category": a.category,
                "location": a.location or "-",
                "last_service_date": str(a.last_service_date) if a.last_service_date else "Never",
                "next_service_due": str(a.next_service_due) if a.next_service_due else "Not scheduled",
                "status": a.status,
            }
            for a in assets
        ]

    @staticmethod
    def calculate_asset_depreciation(society_id, useful_life_years=10):
        """
        Feature 127:
        Calculates straight-line asset depreciation and current book value.
        """
        assets = Asset.query.filter_by(society_id=society_id).all()
        now = utcnow().date()
        results = []

        for a in assets:
            cost = a.purchase_cost or 0.0
            if a.purchase_date and cost > 0:
                years_used = max(0, (now - a.purchase_date).days / 365.25)
                annual_dep = cost / useful_life_years
                accum_dep = min(cost, annual_dep * years_used)
                book_value = max(0.0, cost - accum_dep)
                results.append({
                    "asset_name": a.asset_name,
                    "purchase_cost": cost,
                    "purchase_date": str(a.purchase_date),
                    "annual_depreciation": round(annual_dep, 2),
                    "accumulated_depreciation": round(accum_dep, 2),
                    "current_book_value": round(book_value, 2),
                })
        return results

    @staticmethod
    def detect_missing_asset_info(society_id):
        """Feature 128: Finds asset records lacking critical location, vendor, or purchase info."""
        assets = Asset.query.filter_by(society_id=society_id).all()
        incomplete = []
        for a in assets:
            missing = []
            if not a.purchase_cost:
                missing.append("Purchase Cost")
            if not a.purchase_date:
                missing.append("Purchase Date")
            if not a.vendor_id:
                missing.append("Vendor Link")
            if not a.location:
                missing.append("Location/Room")

            if missing:
                incomplete.append({
                    "asset_id": a.id,
                    "asset_name": a.asset_name,
                    "missing_fields": missing,
                })
        return incomplete

    @staticmethod
    def generate_asset_health_report(society_id):
        """
        Features 129 & 130:
        Generates asset health index and audit summary.
        """
        assets = Asset.query.filter_by(society_id=society_id).all()
        total = len(assets)
        operational = sum(1 for a in assets if a.status == "Operational")
        under_repair = sum(1 for a in assets if a.status in ["Under Repair", "Maintenance Required"])
        health_score = round((operational / total * 100), 1) if total > 0 else 100.0

        return {
            "society_id": society_id,
            "total_assets": total,
            "operational_count": operational,
            "under_repair_count": under_repair,
            "asset_health_score": health_score,
            "status": "Healthy" if health_score >= 80 else "Maintenance Required",
        }
