from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from app.models import (
    Asset,
    InventoryItem,
    InventoryTransaction,
    Vendor,
    ParkingSlot,
    Flat,
    User,
    Role,
    db,
)
from app.services.inventory_service import InventoryService
from app.services.tenant_service import TenantService

operations_bp = Blueprint("operations", __name__, url_prefix="/operations")


@operations_bp.before_request
def admin_only_guard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("admin.admin_login"))
    user = db.session.get(User, user_id)
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        abort(403, description="Admin access required")
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)



@operations_bp.route("/inventory", methods=["GET", "POST"])
def inventory():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    user_id = user.id

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
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    assets_list = Asset.query.filter_by(society_id=society_id).all()
    vendors = Vendor.query.filter_by(society_id=society_id).all()
    return render_template("operations/assets.html", assets=assets_list, vendors=vendors)


@operations_bp.route("/assets/create", methods=["POST"])
def create_asset():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    name = request.form.get("asset_name", "").strip()
    category = request.form.get("category", "General").strip()
    location = request.form.get("location", "").strip()
    cost = float(request.form.get("purchase_cost", 0.0) or 0.0)
    vendor_id = request.form.get("vendor_id", type=int)

    if not name:
        flash("Asset name is required.", "danger")
        return redirect(url_for("operations.assets"))

    asset = Asset(
        society_id=society_id,
        asset_name=name,
        category=category,
        location=location,
        purchase_cost=cost,
        vendor_id=vendor_id if vendor_id else None,
        status="Operational",
    )
    db.session.add(asset)
    db.session.commit()
    flash(f"Asset '{name}' added successfully.", "success")
    return redirect(url_for("operations.assets"))


@operations_bp.route("/vendors")
def vendors():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    vendors_list = Vendor.query.filter_by(society_id=society_id).all()
    return render_template("operations/vendors.html", vendors=vendors_list)


@operations_bp.route("/vendors/create", methods=["POST"])
def create_vendor():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    company = request.form.get("company_name", "").strip()
    contact = request.form.get("contact_person", "").strip()
    phone = request.form.get("phone", "").strip()
    email = request.form.get("email", "").strip()
    category = request.form.get("category", "AMC").strip()
    amount = float(request.form.get("contract_amount", 0.0) or 0.0)

    if not company or not phone:
        flash("Company name and phone number are required.", "danger")
        return redirect(url_for("operations.vendors"))

    v = Vendor(
        society_id=society_id,
        company_name=company,
        contact_person=contact,
        phone=phone,
        email=email if email else None,
        category=category,
        contract_amount=amount,
        status="Active",
    )
    db.session.add(v)
    db.session.commit()
    flash(f"Vendor '{company}' added to directory.", "success")
    return redirect(url_for("operations.vendors"))


@operations_bp.route("/parking")
def parking():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    slots = ParkingSlot.query.filter_by(society_id=society_id).all()
    flats = Flat.query.filter_by(society_id=society_id).all()
    total_slots = len(slots)
    allocated_slots = sum(1 for s in slots if s.status == "Allocated")
    available_slots = total_slots - allocated_slots

    return render_template(
        "operations/parking.html",
        slots=slots,
        flats=flats,
        total_slots=total_slots,
        allocated_slots=allocated_slots,
        available_slots=available_slots,
    )


@operations_bp.route("/parking/allocate", methods=["POST"])
def allocate_parking():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    slot_id = request.form.get("slot_id", type=int)
    flat_id = request.form.get("flat_id", type=int)

    slot = ParkingSlot.query.filter_by(id=slot_id, society_id=society_id).first_or_404()
    if flat_id:
        flat = Flat.query.filter_by(id=flat_id, society_id=society_id).first_or_404()
        slot.allocated_flat_id = flat.id
        slot.status = "Allocated"
        flash(f"Parking slot {slot.slot_number} allocated to Flat {flat.flat_number}.", "success")
    else:
        slot.allocated_flat_id = None
        slot.status = "Available"
        flash(f"Parking slot {slot.slot_number} marked available.", "info")

    db.session.commit()
    return redirect(url_for("operations.parking"))

