import pytest
from datetime import date
from app.models import (
    db,
    User,
    Role,
    Society,
    Flat,
    Resident,
    MaintenanceBill,
)
from app.services.billing_service import BillingService


@pytest.fixture
def setup_allocation_data(app):
    with app.app_context():
        society = Society.query.filter_by(registration_number="REG-001").first()
        flat = Flat.query.filter_by(society_id=society.id).first()

        user = User(
            full_name="Alloc Resident",
            mobile="9822233344",
            email="allocres@test.com",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
            society_id=society.id,
        )
        user.set_password("Resident@123")
        db.session.add(user)
        db.session.flush()

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name=user.full_name,
            mobile=user.mobile,
            resident_type="Owner",
            is_primary=True,
        )
        db.session.add(resident)
        db.session.flush()

        # Create 3 unpaid bills: Jan (2000), Feb (2000), Mar (2000)
        b1 = MaintenanceBill(
            bill_number="BILL-ALS-202601-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-01",
            base_amount=1500.0,
            late_fee=500.0,
            total_amount=2000.0,
            amount_paid=0.0,
            remaining_amount=2000.0,
            due_date=date(2026, 1, 10),
            status="Overdue",
        )
        b2 = MaintenanceBill(
            bill_number="BILL-ALS-202602-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-02",
            base_amount=1500.0,
            late_fee=500.0,
            total_amount=2000.0,
            amount_paid=0.0,
            remaining_amount=2000.0,
            due_date=date(2026, 2, 10),
            status="Overdue",
        )
        b3 = MaintenanceBill(
            bill_number="BILL-ALS-202603-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-03",
            base_amount=1500.0,
            late_fee=500.0,
            total_amount=2000.0,
            amount_paid=0.0,
            remaining_amount=2000.0,
            due_date=date(2026, 3, 10),
            status="Overdue",
        )
        db.session.add_all([b1, b2, b3])
        db.session.commit()

        return {
            "society_id": society.id,
            "resident_id": resident.id,
            "b1_id": b1.id,
            "b2_id": b2.id,
            "b3_id": b3.id,
        }


def test_fifo_payment_allocation(app, setup_allocation_data):
    with app.app_context():
        data = setup_allocation_data
        # Resident owes 3 months x 2000 = 6000
        # Resident pays 5000
        result = BillingService.allocate_multi_month_payment(
            resident_id=data["resident_id"],
            society_id=data["society_id"],
            payment_amount=5000.0,
        )

        assert result["total_paid"] == 5000.0
        assert result["total_allocated"] == 5000.0
        assert result["unallocated_balance"] == 0.0
        assert len(result["allocations"]) == 3

        # Month 1 (Jan): 2000 fully paid
        b1 = db.session.get(MaintenanceBill, data["b1_id"])
        assert b1.amount_paid == 2000.0
        assert b1.remaining_amount == 0.0
        assert b1.status == "Paid"

        # Month 2 (Feb): 2000 fully paid
        b2 = db.session.get(MaintenanceBill, data["b2_id"])
        assert b2.amount_paid == 2000.0
        assert b2.remaining_amount == 0.0
        assert b2.status == "Paid"

        # Month 3 (Mar): 1000 partially paid (1000 remaining)
        b3 = db.session.get(MaintenanceBill, data["b3_id"])
        assert b3.amount_paid == 1000.0
        assert b3.remaining_amount == 1000.0
        assert b3.status == "Partially Paid"
