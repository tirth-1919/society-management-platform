from datetime import date
from app.models import (
    db,
    Society,
    User,
    Role,
    Resident,
    MaintenanceBill,
    MaintenanceConfig,
    Payment,
)
from app.services.billing_service import BillingService


def setup_society_and_resident(mobile, flat_idx=0, start_month="2026-01"):
    society = Society.query.first()
    building = society.buildings[0] if society.buildings else None
    if not building:
        from app.models import Building
        building = Building(society_id=society.id, name="Tower A")
        db.session.add(building)
        db.session.flush()

    from app.models import Flat
    flat = Flat(
        society_id=society.id,
        building_id=building.id,
        flat_number=f"F-{mobile[-4:]}",
        floor=1,
    )
    db.session.add(flat)
    db.session.flush()

    user = User(
        full_name=f"Ledger Resident {mobile}",
        mobile=mobile,
        society_id=society.id,
        role=Role.RESIDENT,
        account_status="ACTIVE",
        is_active=True,
    )
    user.set_password("Pass@123")
    db.session.add(user)
    db.session.flush()

    resident = Resident(
        society_id=society.id,
        flat_id=flat.id,
        user_id=user.id,
        full_name=user.full_name,
        mobile=user.mobile,
        resident_type="Owner",
        occupancy_status="Active",
        is_primary=True,
        advance_balance=0.0,
    )
    db.session.add(resident)
    db.session.flush()

    config = MaintenanceConfig.query.filter_by(society_id=society.id).first()
    if not config:
        config = MaintenanceConfig(
            society_id=society.id,
            fixed_monthly_rate=1500.0,
            due_day_of_month=10,
            grace_period_days=3,
            late_fee_per_month=500.0,
        )
        db.session.add(config)
    db.session.commit()
    return society, flat, user, resident


def test_deterministic_multi_month_payment_allocation(app):
    with app.app_context():
        society, flat, user, resident = setup_society_and_resident("9700000001", flat_idx=0)

        # Create 3 bills: Month 1 = 2000, Month 2 = 2000, Month 3 = 2000
        b1 = MaintenanceBill(
            bill_number="BILL-DET-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-01",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=2000,
            amount_paid=0,
            due_date=date(2026, 1, 10),
            status="Overdue",
        )
        b2 = MaintenanceBill(
            bill_number="BILL-DET-02",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-02",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=2000,
            amount_paid=0,
            due_date=date(2026, 2, 10),
            status="Overdue",
        )
        b3 = MaintenanceBill(
            bill_number="BILL-DET-03",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-03",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=2000,
            amount_paid=0,
            due_date=date(2026, 3, 10),
            status="Pending",
        )
        db.session.add_all([b1, b2, b3])
        db.session.commit()

        # Pay 5000 INR
        result = BillingService.allocate_multi_month_payment(
            resident_id=resident.id,
            society_id=society.id,
            payment_amount=5000.0,
        )

        assert result["total_paid"] == 5000.0
        assert result["total_allocated"] == 5000.0
        assert result["unallocated_balance"] == 0.0
        assert len(result["allocations"]) == 3

        # Allocation: Month 1 = 2000, Month 2 = 2000, Month 3 = 1000
        assert result["allocations"][0]["allocated_amount"] == 2000.0
        assert result["allocations"][0]["remaining_on_bill"] == 0.0
        assert result["allocations"][0]["status"] == "Paid"

        assert result["allocations"][1]["allocated_amount"] == 2000.0
        assert result["allocations"][1]["remaining_on_bill"] == 0.0
        assert result["allocations"][1]["status"] == "Paid"

        assert result["allocations"][2]["allocated_amount"] == 1000.0
        assert result["allocations"][2]["remaining_on_bill"] == 1000.0
        assert result["allocations"][2]["status"] == "Partially Paid"


def test_overpayment_creates_advance_credit(app):
    with app.app_context():
        society, flat, user, resident = setup_society_and_resident("9700000002", flat_idx=1)

        b1 = MaintenanceBill(
            bill_number="BILL-OVER-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-04",
            base_amount=1500,
            late_fee=0,
            total_amount=1500,
            remaining_amount=1500,
            amount_paid=0,
            due_date=date(2026, 4, 10),
            status="Pending",
        )
        db.session.add(b1)
        db.session.commit()

        # Pay 2500 for a 1500 bill -> 1000 advance credit
        result = BillingService.allocate_multi_month_payment(
            resident_id=resident.id,
            society_id=society.id,
            payment_amount=2500.0,
        )

        assert result["total_paid"] == 2500.0
        assert result["total_allocated"] == 1500.0
        assert result["unallocated_balance"] == 1000.0
        assert result["advance_credited"] == 1000.0

        refreshed_resident = db.session.get(Resident, resident.id)
        assert refreshed_resident.advance_balance == 1000.0


def test_advance_credit_automatically_offsets_new_bill(app):
    with app.app_context():
        society, flat, user, resident = setup_society_and_resident("9700000003", flat_idx=2)
        resident.advance_balance = 1000.0
        db.session.commit()

        # Generate bill for 2026-05 (1500 INR)
        bill = BillingService.ensure_bill_for_flat(
            flat_id=flat.id,
            society_id=society.id,
            billing_month="2026-05",
            resident_id=resident.id,
        )

        assert bill.total_amount == 1500.0
        assert bill.amount_paid == 1000.0
        assert bill.remaining_amount == 500.0
        assert bill.status == "Partially Paid"

        refreshed_resident = db.session.get(Resident, resident.id)
        assert refreshed_resident.advance_balance == 0.0


def test_resident_ledger_financial_statement(app):
    from datetime import datetime
    with app.app_context():
        society, flat, user, resident = setup_society_and_resident("9700000004", flat_idx=3)

        b1 = MaintenanceBill(
            bill_number="BILL-LEDGER-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-06",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=0,
            amount_paid=2000,
            due_date=date(2026, 6, 10),
            status="Paid",
        )
        db.session.add(b1)
        db.session.flush()

        p1 = Payment(
            society_id=society.id,
            resident_id=resident.id,
            flat_id=flat.id,
            bill_id=b1.id,
            amount_paid=2000,
            payment_method="UPI",
            status="captured",
            transaction_id="TXN-LEDGER-01",
            payment_date=datetime(2026, 6, 12, 14, 30),
        )
        db.session.add(p1)
        db.session.commit()

        ledger = BillingService.get_resident_ledger(
            resident_id=resident.id,
            society_id=society.id,
        )

        assert ledger["total_debits"] == 2000.0  # 1500 base + 500 late fee
        assert ledger["total_credits"] == 2000.0  # 2000 payment
        assert ledger["closing_balance"] == 0.0
        assert ledger["status"] == "Clear"
        assert len(ledger["entries"]) == 3  # Maintenance debit, Late fee debit, Payment credit


def test_defaulters_list_and_filters(app):
    with app.app_context():
        society, flat, user, resident = setup_society_and_resident("9700000005", flat_idx=4)

        b1 = MaintenanceBill(
            bill_number="BILL-DEF-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-05",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=2000,
            amount_paid=0,
            due_date=date(2026, 5, 10),
            status="Overdue",
        )
        b2 = MaintenanceBill(
            bill_number="BILL-DEF-02",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-06",
            base_amount=1500,
            late_fee=500,
            total_amount=2000,
            remaining_amount=2000,
            amount_paid=0,
            due_date=date(2026, 6, 10),
            status="Overdue",
        )
        db.session.add_all([b1, b2])
        db.session.commit()

        # Query defaulters as of 2026-07-01
        defaulters = BillingService.get_defaulters_list(
            society_id=society.id,
            as_of=date(2026, 7, 1),
        )

        resident_def = next((d for d in defaulters if d["resident_id"] == resident.id), None)
        assert resident_def is not None
        assert resident_def["pending_months_count"] == 2
        assert resident_def["maintenance_due"] == 3000.0
        assert resident_def["late_fees_due"] == 1000.0
        assert resident_def["total_outstanding"] == 4000.0
        assert resident_def["days_overdue"] > 0

        # Filter by min_amount = 5000 -> should exclude this resident
        filtered = BillingService.get_defaulters_list(
            society_id=society.id,
            min_amount=5000.0,
            as_of=date(2026, 7, 1),
        )
        assert not any(d["resident_id"] == resident.id for d in filtered)
