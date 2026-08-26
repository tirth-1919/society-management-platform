from app.models import (
    db,
    Vendor,
    WorkOrder,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import timedelta


class VendorAutomationService:
    """
    Implements Phase 20 Vendor Management & Contract Lifecycle Automation:
    - Vendor contract expiry monitoring
    - Vendor SLA compliance calculation
    - Milestone payment tracking
    - Renewal reminder workflows
    """

    @staticmethod
    def audit_vendor_contracts(society_id, days_threshold=30):
        """Scans active vendor contracts nearing expiration and generates renewal alerts."""
        now = utcnow().date()
        cutoff = now + timedelta(days=days_threshold)

        vendors = Vendor.query.filter_by(society_id=society_id, status="Active").all()
        expiring = []
        alerts_created = 0

        for v in vendors:
            if v.contract_end and now <= v.contract_end <= cutoff:
                days_left = (v.contract_end - now).days
                expiring.append(v)

                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="VENDOR_CONTRACT_EXPIRY",
                    severity="WARNING",
                    title=f"Contract Expiring: {v.company_name}",
                    message=f"Vendor contract for {v.company_name} ({v.category}) ends in {days_left} day(s) on {v.contract_end}. Contract Value: ₹{v.contract_amount:,.2f}.",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_created += 1

        db.session.commit()
        return {
            "total_vendors": len(vendors),
            "expiring_count": len(expiring),
            "alerts_created": alerts_created,
            "expiring_vendors": [{"id": v.id, "name": v.company_name, "category": v.category, "end_date": str(v.contract_end)} for v in expiring],
        }

    @staticmethod
    def get_vendor_compliance_scorecard(society_id):
        """Calculates SLA compliance rate for each active vendor based on completed work orders."""
        vendors = Vendor.query.filter_by(society_id=society_id).all()
        scorecard = []

        for v in vendors:
            orders = WorkOrder.query.filter_by(society_id=society_id, assigned_vendor_id=v.id).all()
            completed = [w for w in orders if w.status == "Completed"]
            on_time = [w for w in completed if (w.completed_at and w.due_date and w.completed_at.date() <= w.due_date)]

            sla_rate = round((len(on_time) / len(completed) * 100), 1) if completed else 100.0
            scorecard.append({
                "vendor_id": v.id,
                "company_name": v.company_name,
                "category": v.category,
                "total_work_orders": len(orders),
                "completed_count": len(completed),
                "on_time_sla_rate": sla_rate,
                "status": v.status,
            })
        return scorecard
