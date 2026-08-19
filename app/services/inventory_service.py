from app.models import db, InventoryItem, InventoryTransaction


class InventoryService:
    @staticmethod
    def process_stock_transaction(
        item_id, society_id, transaction_type, quantity, user_id=None, notes=None
    ):
        """
        Executes stock changes atomically.
        Prevents negative stock on OUT transactions.
        """
        item = (
            InventoryItem.query.filter_by(id=item_id, society_id=society_id)
            .with_for_update()
            .first()
        )
        if not item:
            raise ValueError("Inventory item not found")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than 0")

        if transaction_type == "OUT":
            if item.current_stock < quantity:
                raise ValueError(
                    f"Insufficient stock! Available: {item.current_stock}, Requested OUT: {quantity}"
                )
            item.current_stock -= quantity
        elif transaction_type in ["IN", "RETURN"]:
            item.current_stock += quantity
        elif transaction_type == "ADJUSTMENT":
            item.current_stock = quantity  # Set directly
        else:
            raise ValueError(f"Invalid transaction type {transaction_type}")

        txn = InventoryTransaction(
            society_id=society_id,
            item_id=item.id,
            transaction_type=transaction_type,
            quantity=quantity,
            performed_by_id=user_id,
            notes=notes,
        )
        db.session.add(txn)
        db.session.commit()
        return item
