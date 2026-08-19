<<<<<<< HEAD
from datetime import date
import pytest
=======
﻿from datetime import date
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
from app.models import (
    db,
    Society,
    User,
    Role,
    Resident,
    MaintenanceBill,
    NotificationLog,
)
from app.services.billing_service import BillingService
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.services.registration_service import MaintenanceSummaryService


def add_active_resident(society, flat, mobile, start_month="2026-08"):
    user = User(
        full_name="Acceptance Resident",
        mobile=mobile,
        society_id=society.id,
        role=Role.RESIDENT,
        account_status="ACTIVE",
        is_active=True,
        maintenance_start_month=start_month,
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
    )
    db.session.add(resident)
    db.session.commit()
    return user, resident


def test_repeated_resident_logins_do_not_create_duplicate_bills(client, app):
    with app.app_context():
        society = Society.query.first()
        user, resident = add_active_resident(society, society.flats[0], "9760000001")
        bill = BillingService.ensure_bill_for_flat(
            society.id, resident.flat_id, resident.id, "2026-08"
        )
        mobile, flat_id, bill_id = user.mobile, resident.flat_id, bill.id

    for _ in range(2):
        response = client.post(
            "/login", data={"mobile": mobile, "password": "Pass@123"}
        )
        assert response.status_code == 302
        client.get("/logout")

    with app.app_context():
        assert (
            MaintenanceBill.query.filter_by(
                flat_id=flat_id, billing_month="2026-08"
            ).count()
            == 1
        )
        assert db.session.get(MaintenanceBill, bill_id).total_amount == 1500


def test_next_month_scheduler_adds_only_the_next_standalone_cycle(app):
    with app.app_context():
        society = Society.query.first()
        user, resident = add_active_resident(society, society.flats[0], "9760000002")
        august = BillingService.generate_monthly_bills(society.id, "2026-08")
        assert len(august) == 1
        assert BillingService.generate_monthly_bills(society.id, "2026-08") == []
        september = BillingService.generate_monthly_bills(
            society.id, "2026-09", as_of=date(2026, 9, 1)
        )
        assert len(september) == 1
        assert september[0].base_amount == 1500
        assert september[0].previous_balance == 0
        assert september[0].late_fee == 0
        assert september[0].total_amount == 1500


def test_new_resident_does_not_receive_historical_or_future_pending_months(app):
    with app.app_context():
        society = Society.query.first()
        user, resident = add_active_resident(
            society, society.flats[0], "9760000005", "2026-08"
        )
        BillingService.ensure_bill_for_flat(
            society.id, resident.flat_id, resident.id, "2026-08"
        )
        bills = MaintenanceBill.query.filter_by(flat_id=resident.flat_id).all()
        assert [bill.billing_month for bill in bills] == ["2026-08"]


def test_new_resident_uses_own_august_bill_and_stays_paid_after_relogin(app):
    """A new occupancy must not inherit a previous resident's flat-level history."""
    with app.app_context():
        society = Society.query.first()
        flat = society.flats[0]
        old_user, old_resident = add_active_resident(
            society, flat, "9760000010", "2026-01"
        )
        old_bill = MaintenanceBill(
            bill_number="OLD-OCCUPANCY-2026-08",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=old_resident.id,
            billing_month="2026-08",
            base_amount=3675,
            total_amount=3675,
            remaining_amount=3675,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(old_bill)
        db.session.commit()

        user, resident = add_active_resident(society, flat, "9760000011", "2026-08")
        bill = BillingService.ensure_bill_for_flat(
            society.id, flat.id, resident.id, "2026-08"
        )
        assert (
            BillingService.ensure_bill_for_flat(
                society.id, flat.id, resident.id, "2026-08"
            ).id
            == bill.id
        )

        dues = MaintenanceSummaryService.calculate_dues(
            user_id=user.id, as_of=date(2026, 8, 20)
        )
        assert dues["current_month_maintenance"] == 1500
        assert dues["pending_months"] == 0
        assert dues["maintenance_due"] == 1500
        assert dues["late_fee"] == 0
        assert dues["total_due"] == 1500
        assert (
            MaintenanceBill.query.filter_by(
                resident_id=resident.id, billing_month="2026-08"
            ).count()
            == 1
        )

        PaymentService.process_successful_payment(
            bill.id,
            society.id,
            resident.id,
            bill.remaining_amount,
            "NEW-OCCUPANCY-TXN",
            idempotency_key="NEW-OCCUPANCY-IDEM",
        )
        dues_after_payment = MaintenanceSummaryService.calculate_dues(
            user_id=user.id, as_of=date(2026, 8, 21)
        )
        assert bill.status == "Paid"
        assert dues_after_payment["pending_months"] == 0
        assert dues_after_payment["maintenance_due"] == 0
        assert dues_after_payment["late_fee"] == 0
        assert dues_after_payment["total_due"] == 0


def test_future_billing_month_is_not_generated(app):
    with app.app_context():
        society = Society.query.first()
        _, resident = add_active_resident(
            society, society.flats[0], "9760000006", "2026-08"
        )
        try:
            BillingService.generate_monthly_bills(
                society.id, "2026-09", as_of=date(2026, 8, 11)
            )
        except ValueError as error:
            assert "Future billing months" in str(error)
        else:
            raise AssertionError("A future bill was generated")
        assert MaintenanceBill.query.filter_by(flat_id=resident.flat_id).count() == 0


def test_paid_month_stops_future_reminders_and_sends_one_confirmation(app):
    with app.app_context():
        society = Society.query.first()
        user, resident = add_active_resident(society, society.flats[0], "9760000003")
        bill = BillingService.ensure_bill_for_flat(
            society.id, resident.flat_id, resident.id, "2026-08"
        )
        PaymentService.process_successful_payment(
            bill.id,
            society.id,
            resident.id,
            bill.remaining_amount,
            "ACCEPT-TXN-1",
            idempotency_key="ACCEPT-IDEM-1",
        )
        assert (
            NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 20))
            == []
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month="2026-08",
                notification_type="OVERDUE_REMINDER",
            ).count()
            == 0
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month="2026-08",
                notification_type="PAYMENT_SUCCESS",
            ).count()
            == 1
        )


def test_cross_society_resident_cannot_open_another_societys_bill(client, app):
    with app.app_context():
        first, second = Society.query.order_by(Society.id).all()
        user, _ = add_active_resident(first, first.flats[0], "9760000004")
        bill = MaintenanceBill(
            bill_number="CROSS-SOCIETY-BILL",
            society_id=second.id,
            flat_id=second.flats[0].id,
            billing_month="2026-08",
            base_amount=1500,
            total_amount=1500,
            remaining_amount=1500,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()
        user_id, society_id, bill_id = user.id, first.id, bill.id

    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["society_id"] = society_id
        session["role"] = Role.RESIDENT
    assert client.get(f"/payments/pay/{bill_id}").status_code == 403


<<<<<<< HEAD
def test_generate_monthly_bills_requires_society_id(app):
    with app.app_context():
        with pytest.raises(ValueError, match="Society ID is required"):
            BillingService.generate_monthly_bills(None, "2026-08")
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
