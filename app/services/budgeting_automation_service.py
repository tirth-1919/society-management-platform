from app.models import (
    ExpenseVoucher,
)
from app.utils import utcnow


class BudgetingAutomationService:
    """
    Implements Phase 31 Advanced Financial Analytics & Budgeting Automation:
    - Annual budget planning & category thresholds
    - Budget variance analysis (Budget vs Actual)
    - Sinking fund & reserve fund calculation models
    """

    DEFAULT_BUDGETS = {
        "Security": 30000.0,
        "Cleaning": 15000.0,
        "Electricity": 25000.0,
        "Water": 20000.0,
        "Lift": 15000.0,
        "Repairs": 20000.0,
        "Gardening": 8000.0,
    }

    @staticmethod
    def get_budget_variance_analysis(society_id, target_month=None):
        """Calculates budget variance (Budgeted vs Actual Spending) by category."""
        target_month = target_month or utcnow().strftime("%Y-%m")
        start_date = utcnow().date().replace(day=1)

        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            ExpenseVoucher.status.in_(["Approved", "Paid"]),
            ExpenseVoucher.expense_date >= start_date,
        ).all()

        actuals = {}
        for v in vouchers:
            actuals[v.category] = actuals.get(v.category, 0.0) + v.amount

        variance_report = []
        total_budget = 0.0
        total_actual = 0.0

        for cat, budgeted in BudgetingAutomationService.DEFAULT_BUDGETS.items():
            spent = actuals.get(cat, 0.0)
            diff = budgeted - spent
            pct_used = round((spent / budgeted * 100), 1) if budgeted > 0 else 0.0
            total_budget += budgeted
            total_actual += spent

            variance_report.append({
                "category": cat,
                "budgeted": budgeted,
                "actual_spent": round(spent, 2),
                "variance": round(diff, 2),
                "percentage_used": pct_used,
                "status": "OVER_BUDGET" if spent > budgeted else ("NEAR_LIMIT" if pct_used >= 85 else "WITHIN_BUDGET"),
            })

        return {
            "society_id": society_id,
            "month": target_month,
            "total_budget": round(total_budget, 2),
            "total_actual_spent": round(total_actual, 2),
            "net_budget_variance": round(total_budget - total_actual, 2),
            "categories": variance_report,
        }

    @staticmethod
    def calculate_sinking_fund_reserve(society_id, sinking_fund_rate_per_flat=250.0):
        """Calculates annual sinking fund allocation for long-term structural maintenance."""
        from app.models import Flat
        occupied_flats = Flat.query.filter_by(society_id=society_id, occupancy_status="Occupied").count()
        monthly_sinking = occupied_flats * sinking_fund_rate_per_flat
        annual_sinking = monthly_sinking * 12

        return {
            "society_id": society_id,
            "occupied_flats_count": occupied_flats,
            "rate_per_flat_monthly": sinking_fund_rate_per_flat,
            "monthly_reserve_accumulation": round(monthly_sinking, 2),
            "projected_annual_sinking_fund": round(annual_sinking, 2),
            "recommended_5_year_reserve": round(annual_sinking * 5, 2),
        }
