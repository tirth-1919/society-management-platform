from datetime import datetime
from app.models.tenant import db


class Staff(db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    full_name = db.Column(db.String(100), nullable=False)
    role_type = db.Column(
        db.String(50), nullable=False
    )  # Security, Cleaner, Electrician, Plumber, Gardener, Technician, Manager
    phone = db.Column(db.String(20), nullable=False)
    salary_amount = db.Column(db.Float, default=0.0)
    joining_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="Active")  # Active, On Leave, Terminated


class Vendor(db.Model):
    __tablename__ = "vendors"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    company_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    category = db.Column(
        db.String(50), nullable=False
    )  # Lift AMC, CCTV, Generator, Gardening, Waste Management
    contract_start = db.Column(db.Date, nullable=True)
    contract_end = db.Column(db.Date, nullable=True)
    contract_amount = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="Active")


class WorkOrder(db.Model):
    __tablename__ = "work_orders"

    id = db.Column(db.Integer, primary_key=True)
    work_order_number = db.Column(
        db.String(50), unique=True, nullable=False, index=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    priority = db.Column(db.String(20), default="Medium")

    assigned_staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    assigned_vendor_id = db.Column(
        db.Integer, db.ForeignKey("vendors.id"), nullable=True
    )
    estimated_cost = db.Column(db.Float, default=0.0)
    actual_cost = db.Column(db.Float, default=0.0)

    status = db.Column(
        db.String(30), default="Created", index=True
    )  # Created, Assigned, Accepted, In Progress, Completed, Verified, Closed
    completion_notes = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Asset(db.Model):
    __tablename__ = "assets"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    asset_name = db.Column(
        db.String(100), nullable=False
    )  # e.g. Elevator 1, Diesel Generator 100KVA, CCTV NVR
    category = db.Column(
        db.String(50), nullable=False
    )  # Lift, CCTV, Generator, Water Pump, Fire Equipment, Solar
    location = db.Column(db.String(100), nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    purchase_cost = db.Column(db.Float, default=0.0)
    warranty_expiry = db.Column(db.Date, nullable=True)
    vendor_id = db.Column(db.Integer, db.ForeignKey("vendors.id"), nullable=True)

    last_service_date = db.Column(db.Date, nullable=True)
    next_service_due = db.Column(db.Date, nullable=True)
    status = db.Column(
        db.String(30), default="Operational"
    )  # Operational, Maintenance Required, Under Repair, Retired


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    item_name = db.Column(
        db.String(100), nullable=False
    )  # LED Bulb 18W, Phenyl 5L, Wire Roll 2.5mm
    category = db.Column(
        db.String(50), nullable=False
    )  # Electrical, Cleaning, Plumbing, Spare Parts, Office
    unit = db.Column(db.String(20), default="Pcs")  # Pcs, Litres, Kg, Boxes, Meters
    current_stock = db.Column(db.Integer, default=0)
    minimum_threshold = db.Column(db.Integer, default=5)
    unit_cost = db.Column(db.Float, default=0.0)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class InventoryTransaction(db.Model):
    __tablename__ = "inventory_transactions"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    item_id = db.Column(
        db.Integer, db.ForeignKey("inventory_items.id"), nullable=False, index=True
    )
    transaction_type = db.Column(
        db.String(20), nullable=False
    )  # IN, OUT, ADJUSTMENT, RETURN
    quantity = db.Column(db.Integer, nullable=False)
    performed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    notes = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    item = db.relationship("InventoryItem", backref="transactions", lazy=True)



