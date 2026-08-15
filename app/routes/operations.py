from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Asset, InventoryItem, InventoryTransaction
from app.services.inventory_service import InventoryService

operations_bp = Blueprint("operations", __name__, url_prefix="/operations")


@operations_bp.route("/inventory", methods=["GET", "POST"])
def inventory():
    society_id = session.get("society_id")
    user_id = session.get("user_id")

    if request.method == "POST":
        item_id = int(request.form.get("item_id"))
        txn_type = request.form.get("transaction_type")  # IN, OUT, ADJUSTMENT, RETURN
        qty = int(request.form.get("quantity"))
        notes = request.form.get("notes")

        try:
            InventoryService.process_stock_transaction(
                item_id, society_id, txn_type, qty, user_id, notes
            )
            flash("Inventory transaction processed successfully!", "success")
        except ValueError as e:
            flash(str(e), "danger")

        return redirect(url_for("operations.inventory"))

    items = InventoryItem.query.filter_by(society_id=society_id).all()
    txns = (
        InventoryTransaction.query.filter_by(society_id=society_id)
        .order_by(InventoryTransaction.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template("operations/inventory.html", items=items, transactions=txns)


@operations_bp.route("/assets")
def assets():
    society_id = session.get("society_id")
    assets_list = Asset.query.filter_by(society_id=society_id).all()
    return render_template("operations/assets.html", assets=assets_list)
