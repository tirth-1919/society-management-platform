from datetime import date
import pytest
from app.models import (
    db,
    User,
    Role,
    Society,
    Flat,
    Resident,
    MaintenanceBill,
)
from app.services.payment_service import PaymentService


@pytest.fixture
def setup_cash_data(app):
    with app.app_context():
        society = Society.query.filter_by(registration_number="REG-001").first()
        flat = Flat.query.filter_by(society_id=society.id).first()

        user = User(
            full_name="Cash Resident",
            mobile="9811122233",
            email="cashres@test.com",
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

        admin_user = User(
            full_name="Cash Admin",
            mobile="9811199999",
            email="cashadmin@test.com",
            role=Role.SOCIETY_ADMIN,
            account_status="ACTIVE",
            is_active=True,
            society_id=society.id,
        )
        admin_user.set_password("Admin@123")
        db.session.add(admin_user)
        db.session.flush()

        bill = MaintenanceBill(
            bill_number="BILL-CTS-202603-01",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-03",
            base_amount=1500.0,
            late_fee=0.0,
            total_amount=1500.0,
            amount_paid=0.0,
            remaining_amount=1500.0,
            due_date=date(2026, 3, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        return {
            "society_id": society.id,
            "resident_id": resident.id,
            "user_id": user.id,
            "admin_user_id": admin_user.id,
            "bill_id": bill.id,
        }


def test_cash_payment_submission_and_approval(app, setup_cash_data):
    with app.app_context():
        data = setup_cash_data
        # 1. Submit cash payment
        payment = PaymentService.submit_cash_payment(
            bill_id=data["bill_id"],
            society_id=data["society_id"],
            resident_id=data["resident_id"],
            amount_paid=1500.0,
            notes="Cash given at society office",
        )
        assert payment.id is not None
        assert payment.status == "pending"
        assert payment.payment_method == "Cash"

        # Bill remains untouched while pending
        bill = db.session.get(MaintenanceBill, data["bill_id"])
        assert bill.remaining_amount == 1500.0
        assert bill.status == "Pending"

        # 2. Admin approves cash payment
        approved_payment = PaymentService.approve_cash_payment(
            payment_id=payment.id,
            admin_user_id=data["admin_user_id"],
            admin_notes="Verified against cash drawer",
        )
        assert approved_payment.status == "captured"
        assert approved_payment.verified_at is not None

        # Bill is now paid
        bill = db.session.get(MaintenanceBill, data["bill_id"])
        assert bill.amount_paid == 1500.0
        assert bill.remaining_amount == 0.0
        assert bill.status == "Paid"


def test_cash_payment_rejection(app, setup_cash_data):
    with app.app_context():
        data = setup_cash_data
        # 1. Submit cash payment
        payment = PaymentService.submit_cash_payment(
            bill_id=data["bill_id"],
            society_id=data["society_id"],
            resident_id=data["resident_id"],
            amount_paid=1000.0,
            notes="Pending cash check",
        )
        assert payment.status == "pending"

        # 2. Admin rejects cash payment
        rejected_payment = PaymentService.reject_cash_payment(
            payment_id=payment.id,
            admin_user_id=data["admin_user_id"],
            rejection_reason="Counterfeit currency detected",
        )
        assert rejected_payment.status == "rejected"
        assert rejected_payment.failure_reason == "Counterfeit currency detected"

        # Bill dues remain unaffected
        bill = db.session.get(MaintenanceBill, data["bill_id"])
        assert bill.amount_paid == 0.0
        assert bill.remaining_amount == 1500.0
        assert bill.status == "Pending"
