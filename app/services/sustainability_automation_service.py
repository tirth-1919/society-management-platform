from app.models import (
    Asset,
    ExpenseVoucher,
)


class SustainabilityAutomationService:
    """
    Implements Phase 25 Green Society & Sustainability Automation:
    - Solar energy asset monitoring
    - Green initiatives expenditure tracking
    - Society Green Index score calculation (0-100)
    - Eco-friendly recommendations
    """

    @staticmethod
    def calculate_green_society_score(society_id):
        """Calculates society environmental sustainability score based on green assets & initiatives."""
        assets = Asset.query.filter_by(society_id=society_id).all()
        categories = [a.category.lower() for a in assets]

        has_solar = any("solar" in c for c in categories)
        has_rainwater = any("rain" in c or "water" in c for c in categories)
        has_waste_mgmt = any("waste" in c or "compost" in c for c in categories)

        score = 50  # Baseline
        if has_solar:
            score += 20
        if has_rainwater:
            score += 15
        if has_waste_mgmt:
            score += 15

        score = min(100, score)

        # Green expenditures
        green_vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).filter(
            (ExpenseVoucher.category.ilike("%Garden%")) |
            (ExpenseVoucher.category.ilike("%Solar%")) |
            (ExpenseVoucher.category.ilike("%Waste%"))
        ).all()
        green_spent = sum(v.amount for v in green_vouchers)

        return {
            "society_id": society_id,
            "green_score": score,
            "tier": "GOLD ECO-SOCIETY" if score >= 85 else ("SILVER GREEN" if score >= 65 else "BRONZE INITIATIVE"),
            "has_solar": has_solar,
            "has_rainwater_harvesting": has_rainwater,
            "has_waste_management": has_waste_mgmt,
            "total_green_expenditure": round(green_spent, 2),
        }
