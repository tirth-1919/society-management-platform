from datetime import date
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    User,
    Role,
    Resident,
    MaintenanceBill,
)
from app.services.registration_service import (
    RegistrationService,
    MaintenanceSummaryService,
)
from app.services.billing_service import BillingService


def test_wing_block_flat_hierarchy_valid(app):
    with app.app_context():
        s = Society.query.first()
        wing = Building.query.filter_by(society_id=s.id).first()
        blk = Block.query.filter_by(building_id=wing.id).first()
        flat = Flat.query.filter_by(block_id=blk.id).first()

        # Validate hierarchy pass
        s_res, w_res, b_res, f_res = RegistrationService.validate_hierarchy(
            s.id, wing.id, blk.id, flat.id
        )
        assert s_res.id == s.id
        assert w_res.id == wing.id
        assert b_res.id == blk.id
        assert f_res.id == flat.id


def test_invalid_wing_block_flat_relationship_returns_403(app, client):
    with app.app_context():
        s1 = Society.query.filter_by(name="Society 1").first()
        s2 = Society.query.filter_by(name="Society 2").first()

        wing1 = Building.query.filter_by(society_id=s1.id).first()
        wing2 = Building.query.filter_by(society_id=s2.id).first()

        blk1 = Block.query.filter_by(building_id=wing1.id).first()
        blk2 = Block.query.filter_by(building_id=wing2.id).first()

        Flat.query.filter_by(block_id=blk1.id).first()
        flat2 = Flat.query.filter_by(block_id=blk2.id).first()

        # Mismatched Flat (belonging to blk2/s2) submitted with blk1/wing1/s1
        res = client.post(
            "/register",
            data={
                "full_name": "Tamper User",
                "mobile": "9888877771",
                "email": "tamper@test.com",
                "society_id": s1.id,
                "building_id": wing1.id,
                "block_id": blk1.id,
                "flat_id": flat2.id,  # tampered flat!
                "occupancy_type": "OWNER",
                "password": "Password@123",
            },
        )
        assert res.status_code == 403


def test_maintenance_dues_calculation_0_1_2_3_unpaid_months(app):
    with app.app_context():
        flat = Flat.query.first()

        # 0 unpaid months
        dues0 = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues0["pending_months"] == 0
        assert dues0["maintenance_due"] == 0
        assert dues0["late_fee"] == 0
        assert dues0["total_due"] == 0

        # 1 unpaid month: Maintenance = ₹1,500, Late Fee = ₹500, Total = ₹2,000
        b1 = MaintenanceBill(
            bill_number="BILL-TEST-1",
            society_id=flat.society_id,
            flat_id=flat.id,
            billing_month="2026-01",
            base_amount=1500.0,
            total_amount=2000.0,
            remaining_amount=2000.0,
            amount_paid=0.0,
            due_date=date(2026, 1, 10),
            status="Pending",
        )
        db.session.add(b1)
        db.session.commit()

        dues1 = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues1["pending_months"] == 1
        assert dues1["maintenance_due"] == 1500.0
        assert dues1["late_fee"] == 500.0
        assert dues1["total_due"] == 2000.0

        # 2 unpaid months: Maintenance = ₹3,000, Late Fee = ₹1,000, Total = ₹4,000
        b2 = MaintenanceBill(
            bill_number="BILL-TEST-2",
            society_id=flat.society_id,
            flat_id=flat.id,
            billing_month="2026-02",
            base_amount=1500.0,
            total_amount=2000.0,
            remaining_amount=2000.0,
            amount_paid=0.0,
            due_date=date(2026, 2, 10),
            status="Pending",
        )
        db.session.add(b2)
        db.session.commit()

        dues2 = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues2["pending_months"] == 2
        assert dues2["maintenance_due"] == 3000.0
        assert dues2["late_fee"] == 1000.0
        assert dues2["total_due"] == 4000.0

        # 3 unpaid months: Maintenance = ₹4,500, Late Fee = ₹1,500, Total = ₹6,000
        b3 = MaintenanceBill(
            bill_number="BILL-TEST-3",
            society_id=flat.society_id,
            flat_id=flat.id,
            billing_month="2026-03",
            base_amount=1500.0,
            total_amount=2000.0,
            remaining_amount=2000.0,
            amount_paid=0.0,
            due_date=date(2026, 3, 10),
            status="Pending",
        )
        db.session.add(b3)
        db.session.commit()

        dues3 = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues3["pending_months"] == 3
        assert dues3["maintenance_due"] == 4500.0
        assert dues3["late_fee"] == 1500.0
        assert dues3["total_due"] == 6000.0


def test_successful_payment_removes_month_from_dues(app):
    with app.app_context():
        flat = Flat.query.first()

        # Create 3 unpaid bills
        for i, month in enumerate(["2026-01", "2026-02", "2026-03"], 1):
            b = MaintenanceBill(
                bill_number=f"BILL-PAYTEST-{i}",
                society_id=flat.society_id,
                flat_id=flat.id,
                billing_month=month,
                base_amount=1500.0,
                total_amount=2000.0,
                remaining_amount=2000.0,
                amount_paid=0.0,
                due_date=date(2026, i, 10),
                status="Pending",
            )
            db.session.add(b)
        db.session.commit()

        # 3 unpaid months initially
        dues_before = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues_before["pending_months"] == 3
        assert dues_before["total_due"] == 6000.0

        # Pay 1st month bill
        b1 = MaintenanceBill.query.filter_by(
            flat_id=flat.id, billing_month="2026-01"
        ).first()
        BillingService.apply_partial_payment(b1.id, b1.remaining_amount)
        assert b1.status == "Paid"

        # Check updated dues: 2 unpaid months left = ₹4,000
        dues_after = MaintenanceSummaryService.calculate_dues(flat.id)
        assert dues_after["pending_months"] == 2
        assert dues_after["maintenance_due"] == 3000.0
        assert dues_after["late_fee"] == 1000.0
        assert dues_after["total_due"] == 4000.0


def test_frontend_cannot_manipulate_total_amount(app, client):
    with app.app_context():
        # Register and approve resident
        s = Society.query.first()
        wing = Building.query.filter_by(society_id=s.id).first()
        blk = Block.query.filter_by(building_id=wing.id).first()
        flat = Flat.query.filter_by(block_id=blk.id).first()

        user = User(
            full_name="Pay User",
            mobile="9777766665",
            email="pay@test.com",
            society_id=s.id,
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        user.set_password("Pass@123")
        db.session.add(user)
        db.session.commit()

        res_obj = Resident(
            society_id=s.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name=user.full_name,
            mobile=user.mobile,
            resident_type="Owner",
            occupancy_status="Active",
        )
        db.session.add(res_obj)
        db.session.commit()

        # Create bill for flat
        bill = MaintenanceBill(
            bill_number="BILL-TAMPER-1",
            society_id=s.id,
            flat_id=flat.id,
            billing_month="2026-04",
            base_amount=1500.0,
            total_amount=2000.0,
            remaining_amount=2000.0,
            amount_paid=0.0,
            due_date=date(2026, 4, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        # Login resident
        with client.session_transaction() as sess:
            sess["user_id"] = user.id
            sess["society_id"] = s.id
            sess["role"] = user.role

        # Attempt to post tampered lower amount (e.g. ₹10) to payment endpoint
        client.post(
            f"/payments/pay/{bill.id}",
            data={
                "amount": 10.0,  # Attempted frontend manipulation
                "payment_method": "UPI",
            },
        )

        # Bill total and remaining must be determined server-side from bill object, not client input
        bill_refreshed = db.session.get(MaintenanceBill, bill.id)
        assert (
            bill_refreshed.amount_paid == 2000.0
        )  # Full bill amount paid via server enforcement
        assert bill_refreshed.remaining_amount == 0.0
        assert bill_refreshed.status == "Paid"



