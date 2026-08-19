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
    AccountLedger,
)
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.accounting_service import AccountingService
from app.services.automation_service import AutomationService
from app.services.notification_service import NotificationService
from app.services.society_health_service import SocietyHealthService
from app.services.property_lifecycle_service import PropertyLifecycleService
from app.utils import utcnow


@pytest.fixture
def phase4_ctx():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with app.app_context():
        db.create_all()
        # Seed test society
        soc = Society(
            name="Phase4 Master Society",
            code="P4S",
            registration_number="REG-P4S-999",
            address="999 Automation Way",
            city="Vadodara",
            state="Gujarat",
            pincode="390001",
            email="p4s@society.com",
            phone="9876543000",
        )
        db.session.add(soc)
        db.session.commit()

        bld = Building(society_id=soc.id, name="Wing B")
        db.session.add(bld)
        db.session.commit()

        blk = Block(society_id=soc.id, building_id=bld.id, name="Block B")
        db.session.add(blk)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=bld.id,
            block_id=blk.id,
            flat_number="202",
            floor_number=2,
            area_sqft=1400.0,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        user = User(
            username="res_phase4",
            email="res_phase4@example.com",
            full_name="Phase4 Resident",
            mobile="9876543001",
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
            full_name="Phase4 Resident",
            mobile="9876543001",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
            move_in_date=utcnow().date(),
        )
        db.session.add(res)
        db.session.commit()

        admin_user = User(
            username="admin_phase4",
            email="admin_phase4@example.com",
            full_name="Phase4 Admin",
            mobile="9876543002",
            role=Role.SOCIETY_ADMIN,
            account_status="ACTIVE",
            society_id=soc.id,
        )
        admin_user.set_password("AdminPass123!")
        db.session.add(admin_user)
        db.session.commit()

        yield {
            "app": app,
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


def test_defaulter_recovery_job_execution(phase4_ctx):
    soc = phase4_ctx["society"]
    flat = phase4_ctx["flat"]
    res = phase4_ctx["resident"]
    admin = phase4_ctx["admin"]
    today = utcnow().date()

    # Create severe overdue bill to trigger recovery job
    bill = MaintenanceBill(
        bill_number="BILL-P4-RECOVERY",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2025-11",
        base_amount=4000.0,
        total_amount=4000.0,
        remaining_amount=4000.0,
        due_date=today - timedelta(days=70),
        status="Overdue",
    )
    db.session.add(bill)
    db.session.commit()

    # Execute recovery automation job
    result = AutomationService.execute_job(
        action_type="PROCESS_DEFAULTER_RECOVERY",
        society_id=soc.id,
        executed_by=admin,
        trigger_source="ADMIN_MANUAL",
    )
    assert result["success"] is True
    assert result["stats"]["scanned"] >= 1

    # Verify duplicate execution is locked
    locked_res = AutomationService.execute_job(
        action_type="PROCESS_DEFAULTER_RECOVERY",
        society_id=soc.id,
        executed_by=admin,
    )
    assert locked_res["status"] == "LOCKED"


def test_reminder_cooldown_enforcement(phase4_ctx):
    user = phase4_ctx["user"]
    month = "2026-01"

    # Send first notification
    log1 = NotificationService.send_billing_notification(
        user=user,
        billing_month=month,
        notification_type="OVERDUE_REMINDER",
        message="First reminder message",
        cooldown_hours=24,
    )
    assert log1 is not None

    # Immediate second send should be suppressed by 24h cooldown
    log2 = NotificationService.send_billing_notification(
        user=user,
        billing_month=month,
        notification_type="OVERDUE_REMINDER",
        message="Duplicate reminder message",
        cooldown_hours=24,
    )
    assert log2 is None


def test_fifo_payment_allocation_and_defaulter_clearance(phase4_ctx):
    soc = phase4_ctx["society"]
    flat = phase4_ctx["flat"]
    res = phase4_ctx["resident"]
    admin = phase4_ctx["admin"]
    today = utcnow().date()

    b1 = MaintenanceBill(
        bill_number="BILL-FIFO-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-01",
        base_amount=1000.0,
        total_amount=1000.0,
        remaining_amount=1000.0,
        due_date=today - timedelta(days=40),
        status="Overdue",
    )
    b2 = MaintenanceBill(
        bill_number="BILL-FIFO-02",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-02",
        base_amount=1000.0,
        total_amount=1000.0,
        remaining_amount=1000.0,
        due_date=today - timedelta(days=10),
        status="Overdue",
    )
    db.session.add_all([b1, b2])
    db.session.commit()

    # Cash payment of ₹1500 submitted & approved (Partial settlement of b2)
    pmt = PaymentService.submit_cash_payment(
        bill_id=b1.id,
        society_id=soc.id,
        resident_id=res.id,
        amount_paid=1500.0,
        notes="Partial settlement",
    )
    PaymentService.approve_cash_payment(pmt.id, admin.id)

    db.session.refresh(b1)
    db.session.refresh(b2)
    assert b1.remaining_amount == 0.0
    assert b1.status == "Paid"
    assert b2.remaining_amount == 500.0
    assert b2.status == "Partially Paid"


def test_end_to_end_collection_recovery_flow(phase4_ctx):
    soc = phase4_ctx["society"]
    flat = phase4_ctx["flat"]
    res = phase4_ctx["resident"]
    admin = phase4_ctx["admin"]
    today = utcnow().date()

    bill = MaintenanceBill(
        bill_number="BILL-E2E-01",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res.id,
        billing_month="2026-03",
        base_amount=2500.0,
        total_amount=2500.0,
        remaining_amount=2500.0,
        due_date=today - timedelta(days=15),
        status="Overdue",
    )
    db.session.add(bill)
    db.session.commit()

    # Step 1: Verify Defaulters List detects account
    defaulters = BillingService.get_defaulters_list(soc.id)
    assert len(defaulters) == 1

    # Step 2: Full Cash Settlement
    pmt = PaymentService.submit_cash_payment(
        bill_id=bill.id,
        society_id=soc.id,
        resident_id=res.id,
        amount_paid=2500.0,
        notes="Full E2E settlement",
    )
    PaymentService.approve_cash_payment(pmt.id, admin.id)

    # Step 3: Verify Outstanding clears & Defaulters List is empty
    defaulters_after = BillingService.get_defaulters_list(soc.id)
    assert len(defaulters_after) == 0

    # Step 4: Verify General Ledger CREDIT entry exists
    ledger_entries = AccountLedger.query.filter_by(society_id=soc.id, entry_type="CREDIT").all()
    assert len(ledger_entries) >= 1


def test_occupancy_move_in_out_financial_isolation(phase4_ctx):
    soc = phase4_ctx["society"]
    flat = phase4_ctx["flat"]
    res_a = phase4_ctx["resident"]
    admin = phase4_ctx["admin"]

    # Resident A gets a bill
    bill_a = MaintenanceBill(
        bill_number="BILL-ISO-A",
        society_id=soc.id,
        flat_id=flat.id,
        resident_id=res_a.id,
        billing_month="2026-01",
        base_amount=1800.0,
        total_amount=1800.0,
        remaining_amount=1800.0,
        due_date=utcnow().date(),
        status="Pending",
    )
    db.session.add(bill_a)
    db.session.commit()

    # Move out Resident A
    PropertyLifecycleService.record_move_out(res_a.id, reason="Moved away", admin_user=admin)
    assert flat.occupancy_status == "Vacant"

    # New Resident B moves into same flat B-202
    user_b = User(
        username="res_b_clean",
        email="res_b_clean@example.com",
        full_name="Clean Resident B",
        mobile="9876543888",
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
        full_name="Clean Resident B",
        mobile="9876543888",
        resident_type="Tenant",
        occupancy_status="Active",
        is_primary=True,
        move_in_date=utcnow().date(),
    )
    db.session.add(res_b)
    flat.occupancy_status = "Occupied"
    db.session.commit()

    # Resident B's financial statement must NOT inherit Resident A's bill
    stmt_b = BillingService.get_resident_financial_statement(res_b.id, soc.id)
    assert stmt_b["total_billed"] == 0.0
    assert stmt_b["closing_balance"] == 0.0


def test_financial_period_close_and_adjustment_workflow(phase4_ctx):
    soc = phase4_ctx["society"]
    admin = phase4_ctx["admin"]

    # Month-end checklist
    checklist = AccountingService.get_month_end_checklist(soc.id)
    assert "ready_to_close" in checklist

    # Create controlled financial adjustment
    adj = AccountingService.create_ledger_adjustment(
        society_id=soc.id,
        account_head="Maintenance Adjustment",
        entry_type="CREDIT",
        amount=500.0,
        narration="Audit correction for fee discrepancy",
        user_id=admin.id,
    )
    assert adj.amount == 500.0
    assert adj.entry_type == "CREDIT"


def test_data_quality_scan_and_operational_health(phase4_ctx):
    soc = phase4_ctx["society"]

    # Data quality scan
    dq = SocietyHealthService.run_data_quality_scan(soc.id)
    assert "issues_found" in dq

    # Executive daily brief with 9-queue structure
    brief = SocietyHealthService.get_admin_daily_brief(soc.id)
    assert "action_required" in brief
    assert "active_residents" in brief
