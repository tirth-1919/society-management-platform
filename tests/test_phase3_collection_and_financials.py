import pytest
from datetime import timedelta
from app import create_app
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
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.accounting_service import AccountingService
from app.services.property_lifecycle_service import PropertyLifecycleService
from app.utils import utcnow


@pytest.fixture
def app_ctx():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        # Seed test society, building, block, flat
        soc = Society(
            name="Phase3 Test Society",
            code="P3S",
            registration_number="REG-P3S-001",
            address="123 ERP Street",
            city="Vadodara",
            state="Gujarat",
            pincode="390001",
            email="p3s@society.com",
            phone="9876543210",
        )
        db.session.add(soc)
        db.session.commit()

        bld = Building(society_id=soc.id, name="Wing A")
        db.session.add(bld)
        db.session.commit()

        blk = Block(society_id=soc.id, building_id=bld.id, name="Block A")
        db.session.add(blk)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=bld.id,
            block_id=blk.id,
            flat_number="101",
            floor_number=1,
            area_sqft=1200.0,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        user = User(
            username="res_phase3",
            email="res_phase3@example.com",
            full_name="Phase3 Resident",
            mobile="9876543210",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            society_id=soc.id,
        )
        user.set_password("Pass123!")
        db.session.add(user)
        db.session.commit()

        res = Resident(
            society_id=soc.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name="Phase3 Resident",
            mobile="9876543210",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
            move_in_date=utcnow().date(),
        )
        db.session.add(res)
        db.session.commit()

        admin_user = User(
            username="admin_phase3",
            email="admin_phase3@example.com",
            full_name="Phase3 Admin",
            mobile="9876543211",
            role=Role.SOCIETY_ADMIN,
            account_status="ACTIVE",
            society_id=soc.id,
        )
        admin_user.set_password("AdminPass123!")
        db.session.add(admin_user)
        db.session.commit()

        yield {
            "society": soc,
            "building": bld,
            "block": blk,
            "flat": flat,
            "user": user,
            "resident": res,
            "admin": admin_user,
        }
        db.session.remove()
        db.drop_all()


def test_5_tier_aging_buckets_calculation(app_ctx):
    soc = app_ctx["society"]
    flat = app_ctx["flat"]
    res = app_ctx["resident"]
    today = utcnow().date()

    # Create bills at different aging points
    b1 = MaintenanceBill(
        bill_number="BILL-P3-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-01",
        base_amount=2000.0,
        total_amount=2000.0,
        remaining_amount=2000.0,
        due_date=today - timedelta(days=95),  # 90+ days
        status="Overdue",
    )
    b2 = MaintenanceBill(
        bill_number="BILL-P3-02",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-02",
        base_amount=2000.0,
        total_amount=2000.0,
        remaining_amount=2000.0,
        due_date=today - timedelta(days=45),  # 31-60 days
        status="Overdue",
    )
    b3 = MaintenanceBill(
        bill_number="BILL-P3-03",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-03",
        base_amount=2000.0,
        total_amount=2000.0,
        remaining_amount=2000.0,
        due_date=today + timedelta(days=10),  # Current (future due date)
        status="Pending",
    )
    db.session.add_all([b1, b2, b3])
    db.session.commit()

    buckets = BillingService.get_aging_buckets_summary(soc.id, as_of=today)
    assert buckets["current"]["amount"] == 2000.0
    assert buckets["bucket_31_60"]["amount"] == 2000.0
    assert buckets["bucket_90_plus"]["amount"] == 2000.0
    assert buckets["total_outstanding_amount"] == 4000.0  # overdue total


def test_defaulter_risk_scoring(app_ctx):
    soc = app_ctx["society"]
    flat = app_ctx["flat"]
    res = app_ctx["resident"]
    today = utcnow().date()

    bill = MaintenanceBill(
        bill_number="BILL-RISK-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2025-10",
        base_amount=5000.0,
        total_amount=5000.0,
        remaining_amount=5000.0,
        due_date=today - timedelta(days=100),  # 100 days overdue => CRITICAL
        status="Overdue",
    )
    db.session.add(bill)
    db.session.commit()

    defaulters = BillingService.get_defaulters_list(soc.id, as_of=today)
    assert len(defaulters) == 1
    d = defaulters[0]
    assert d["risk_level"] == "CRITICAL"
    assert d["stage"] == "CRITICAL"
    assert "Legal Notice" in d["next_action"]


def test_payment_dispute_lifecycle(app_ctx):
    soc = app_ctx["society"]
    res = app_ctx["resident"]
    admin = app_ctx["admin"]

    # File dispute
    dispute = PaymentService.create_payment_dispute(
        society_id=soc.id,
        resident_id=res.id,
        claimed_amount=2500.0,
        transaction_id="TX12345678",
        evidence_notes="Paid via UPI on 10th",
    )
    assert dispute.status == "OPEN"
    assert dispute.claimed_amount == 2500.0

    # Resolve dispute
    resolved = PaymentService.resolve_payment_dispute(
        dispute_id=dispute.id,
        admin_user_id=admin.id,
        status="VERIFIED",
        admin_notes="Bank statement verified",
    )
    assert resolved.status == "VERIFIED"
    assert resolved.admin_notes == "Bank statement verified"


def test_defaulter_followup_workflow(app_ctx):
    soc = app_ctx["society"]
    flat = app_ctx["flat"]
    res = app_ctx["resident"]
    admin = app_ctx["admin"]

    followup = PaymentService.create_defaulter_followup(
        society_id=soc.id,
        resident_id=res.id,
        flat_id=flat.id,
        reason="Promised cash payment by Friday",
        due_date=utcnow().date() + timedelta(days=3),
        priority="High",
        assigned_admin_id=admin.id,
    )
    assert followup.status == "OPEN"

    updated = PaymentService.update_defaulter_followup_status(
        followup_id=followup.id,
        status="COMPLETED",
        notes="Cash payment received in office",
    )
    assert updated.status == "COMPLETED"


def test_resident_financial_statement_generation(app_ctx):
    soc = app_ctx["society"]
    flat = app_ctx["flat"]
    res = app_ctx["resident"]

    bill = MaintenanceBill(
        bill_number="BILL-STMT-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-03",
        base_amount=3000.0,
        total_amount=3000.0,
        remaining_amount=3000.0,
        due_date=utcnow().date(),
        status="Pending",
    )
    db.session.add(bill)
    db.session.commit()

    stmt = BillingService.get_resident_financial_statement(res.id, soc.id)
    assert stmt is not None
    assert stmt["total_billed"] == 3000.0
    assert stmt["total_paid"] == 0.0
    assert stmt["closing_balance"] == 3000.0
    assert len(stmt["entries"]) == 1


def test_collection_analytics_and_forecast(app_ctx):
    soc = app_ctx["society"]
    blk = app_ctx["block"]

    # Block analysis
    stats = AccountingService.get_collection_by_block(soc.id)
    assert len(stats) == 1
    assert stats[0]["block_name"] == blk.name

    # Forecast
    forecast = AccountingService.get_collection_forecast(soc.id)
    assert "projected_month_end_collection" in forecast
    assert forecast["confidence"] == "High (Rule-based historical baseline)"

    # Checklist
    checklist = AccountingService.get_month_end_checklist(soc.id)
    assert "ready_to_close" in checklist


def test_property_occupancy_financial_isolation(app_ctx):
    soc = app_ctx["society"]
    flat = app_ctx["flat"]
    res_a = app_ctx["resident"]
    admin = app_ctx["admin"]

    # Resident A gets a bill
    bill_a = MaintenanceBill(
        bill_number="BILL-ISO-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res_a.id,
        billing_month="2026-01",
        base_amount=1500.0,
        total_amount=1500.0,
        remaining_amount=1500.0,
        due_date=utcnow().date(),
        status="Pending",
    )
    db.session.add(bill_a)
    db.session.commit()

    # Move out Resident A
    PropertyLifecycleService.record_move_out(res_a.id, reason="Lease expired", admin_user=admin)
    assert res_a.occupancy_status == "Moved Out"
    assert flat.occupancy_status == "Vacant"

    # Resident B moves in
    user_b = User(
        username="res_b_iso",
        email="res_b@example.com",
        full_name="Resident B",
        mobile="9876543999",
        role=Role.RESIDENT,
        account_status="ACTIVE",
        society_id=soc.id,
    )
    user_b.set_password("Pass123!")
    db.session.add(user_b)
    db.session.commit()

    res_b = Resident(
        society_id=soc.id,
        flat_id=flat.id,
        user_id=user_b.id,
        full_name="Resident B",
        mobile="9876543999",
        resident_type="Tenant",
        occupancy_status="Active",
        is_primary=True,
        move_in_date=utcnow().date(),
    )
    db.session.add(res_b)
    flat.occupancy_status = "Occupied"
    db.session.commit()

    # Resident B's financial statement must NOT contain Resident A's unpaid bill
    stmt_b = BillingService.get_resident_financial_statement(res_b.id, soc.id)
    assert stmt_b["total_billed"] == 0.0
    assert stmt_b["closing_balance"] == 0.0

    # Resident A's financial statement still retains their bill
    stmt_a = BillingService.get_resident_financial_statement(res_a.id, soc.id)
    assert stmt_a["total_billed"] == 1500.0
    assert stmt_a["closing_balance"] == 1500.0
