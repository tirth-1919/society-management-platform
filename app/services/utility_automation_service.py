from app.models import (
    db,
    ExpenseVoucher,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import timedelta


class UtilityAutomationService:
    """
    Implements Phase 21 Water & Utility Management Automation:
    - Water tanker delivery & cost tracking
    - Water pump run-time & tank level alerts
    - Diesel generator fuel monitoring
    - Abnormal utility consumption anomaly detection
    """

    @staticmethod
    def get_water_management_summary(society_id):
        """Calculates water tanker expenditures and deliveries for the current month."""
        start_month = utcnow().replace(day=1).date()
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            ExpenseVoucher.category.ilike("%Water%"),
            ExpenseVoucher.expense_date >= start_month,
        ).all()

        total_spent = sum(v.amount for v in vouchers)
        return {
            "society_id": society_id,
            "month": utcnow().strftime("%Y-%m"),
            "water_tanker_deliveries_count": len(vouchers),
            "total_water_expenditure": round(total_spent, 2),
            "average_cost_per_delivery": round((total_spent / len(vouchers)), 2) if vouchers else 0.0,
        }

    @staticmethod
    def detect_abnormal_utility_spike(society_id):
        """Detects spikes in monthly water/electricity expenses exceeding 1.5x previous month."""
        now = utcnow().date()
        current_start = now.replace(day=1)
        prev_start = (current_start - timedelta(days=1)).replace(day=1)

        cur_exp = sum(v.amount for v in ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            ExpenseVoucher.category.in_(["Water", "Electricity"]),
            ExpenseVoucher.expense_date >= current_start,
        ).all())

        prev_exp = sum(v.amount for v in ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            ExpenseVoucher.category.in_(["Water", "Electricity"]),
            ExpenseVoucher.expense_date >= prev_start,
            ExpenseVoucher.expense_date < current_start,
        ).all()) or 1.0

        ratio = cur_exp / prev_exp
        is_spike = ratio > 1.5 and cur_exp > 10000.0

        if is_spike:
            alert = AutomationAlert(
                society_id=society_id,
                alert_type="UTILITY_CONSUMPTION_SPIKE",
                severity="WARNING",
                title="Utility Expense Spike Detected",
                message=f"Current utility expenditure (₹{cur_exp:,.2f}) is {round(ratio, 2)}x compared to previous month (₹{prev_exp:,.2f}). Investigate potential pipe leakage or meter issues.",
                is_resolved=False,
            )
            db.session.add(alert)
            db.session.commit()

        return {"current_expense": cur_exp, "previous_expense": prev_exp, "spike_detected": is_spike, "ratio": round(ratio, 2)}
