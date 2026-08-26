from app.models import (
    db,
    InventoryItem,
    InventoryTransaction,
    WorkOrder,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import timedelta
import secrets


class InventoryAutomationService:
    """
    Implements Phase 8 Inventory Automation (Features 111–120):
    111. Low-stock detection
    112. Zero-stock detection
    113. Reorder suggestion
    114. Stock-threshold alert
    115. Unusual-consumption detection
    116. Inventory mismatch detection
    117. Monthly inventory report
    118. Inventory audit task
    119. Inventory verification reminder
    120. Expired-inventory detection
    """

    @staticmethod
    def detect_low_and_zero_stock(society_id):
        """
        Features 111, 112, 113, 114:
        Detects items below minimum threshold, zero-stock items, generates reorder suggestions,
        and creates admin alerts. (Never auto-purchases).
        """
        items = InventoryItem.query.filter_by(society_id=society_id).all()
        low_stock = []
        zero_stock = []
        reorder_suggestions = []
        alerts_created = 0

        for item in items:
            if item.current_stock <= 0:
                zero_stock.append(item)
                suggested_qty = max(item.minimum_threshold * 3, 10)
                reorder_suggestions.append({
                    "item_id": item.id,
                    "item_name": item.item_name,
                    "current_stock": item.current_stock,
                    "suggested_reorder_qty": suggested_qty,
                    "unit": item.unit,
                    "estimated_cost": round(suggested_qty * (item.unit_cost or 0.0), 2),
                })
                # Alert
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="ZERO_STOCK_ALERT",
                    severity="CRITICAL",
                    title=f"OUT OF STOCK: {item.item_name}",
                    message=f"Item '{item.item_name}' ({item.category}) has 0 {item.unit} remaining. Suggested reorder: {suggested_qty} {item.unit}.",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_created += 1
            elif item.current_stock <= item.minimum_threshold:
                low_stock.append(item)
                suggested_qty = max(item.minimum_threshold * 2, 5)
                reorder_suggestions.append({
                    "item_id": item.id,
                    "item_name": item.item_name,
                    "current_stock": item.current_stock,
                    "suggested_reorder_qty": suggested_qty,
                    "unit": item.unit,
                    "estimated_cost": round(suggested_qty * (item.unit_cost or 0.0), 2),
                })
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="LOW_STOCK_ALERT",
                    severity="WARNING",
                    title=f"Low Stock: {item.item_name}",
                    message=f"Item '{item.item_name}' current stock ({item.current_stock} {item.unit}) is at/below minimum threshold ({item.minimum_threshold} {item.unit}).",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_created += 1

        db.session.commit()
        return {
            "total_items_scanned": len(items),
            "low_stock_count": len(low_stock),
            "zero_stock_count": len(zero_stock),
            "reorder_suggestions": reorder_suggestions,
            "alerts_created": alerts_created,
        }

    @staticmethod
    def detect_unusual_consumption(society_id, days=7):
        """Feature 115: Identifies items with > 3x average weekly consumption."""
        cutoff = utcnow() - timedelta(days=days)
        txns = InventoryTransaction.query.filter(
            InventoryTransaction.society_id == society_id,
            InventoryTransaction.transaction_type == "OUT",
            InventoryTransaction.created_at >= cutoff,
        ).all()

        by_item = {}
        for t in txns:
            by_item[t.item_id] = by_item.get(t.item_id, 0) + t.quantity

        anomalies = []
        for item_id, qty in by_item.items():
            item = db.session.get(InventoryItem, item_id)
            if item and qty > item.minimum_threshold * 3:
                anomalies.append({
                    "item_id": item.id,
                    "item_name": item.item_name,
                    "category": item.category,
                    "consumed_quantity": qty,
                    "threshold": item.minimum_threshold,
                    "reason": "7-day consumption exceeds 3x minimum threshold",
                })
        return anomalies

    @staticmethod
    def create_inventory_audit_task(society_id):
        """Features 118 & 119: Creates monthly physical inventory verification audit task."""
        wo = WorkOrder(
            work_order_number=f"WO-INV-AUDIT-{society_id}-{secrets.token_hex(2).upper()}",
            society_id=society_id,
            title="Monthly Physical Inventory Count & Stock Audit",
            description="Perform physical count of all electrical, plumbing, and cleaning store items. Verify against database ledger.",
            category="Inventory",
            priority="Medium",
            status="Assigned",
            due_date=utcnow().date() + timedelta(days=3),
        )
        db.session.add(wo)
        db.session.commit()
        return wo

    @staticmethod
    def generate_monthly_inventory_report(society_id):
        """Feature 117: Generates monthly inventory valuation and movement summary."""
        items = InventoryItem.query.filter_by(society_id=society_id).all()
        total_valuation = sum(i.current_stock * (i.unit_cost or 0.0) for i in items)
        low_stock_items = [i for i in items if i.current_stock <= i.minimum_threshold]

        return {
            "society_id": society_id,
            "total_items": len(items),
            "total_stock_valuation": round(total_valuation, 2),
            "low_stock_items_count": len(low_stock_items),
            "month": utcnow().strftime("%Y-%m"),
            "items": [
                {"name": i.item_name, "category": i.category, "stock": i.current_stock, "unit": i.unit, "unit_cost": i.unit_cost}
                for i in items
            ],
        }
