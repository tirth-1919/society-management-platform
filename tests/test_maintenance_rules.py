from datetime import date

from app.config import Config
from app.models import (
    db,
    User,
    Role,
    Society,
    Resident,
    RegistrationRequest,
    MaintenanceBill,
    NotificationLog,
)
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.registration_service import (
    MaintenanceSummaryService,
    RegistrationService,
)


def make_resident(society, flat, mobile):
    user = User(
        full_name="Rule Test Resident",
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
    )
    db.session.add(resident)
    db.session.commit()
    return user, resident


def test_approval_month_creates_one_bill_and_is_stable(app):
    with app.app_context():
        society = Society.query.first()
        building = society.buildings[0]
        flat = building.flats[0]
        user = User(
            full_name="Approval Resident",
            mobile="9888800001",
            society_id=society.id,
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        user.set_password("Pass@123")
        db.session.add(user)
        db.session.flush()
        req = RegistrationRequest(
            user_id=user.id,
            society_id=society.id,
            building_id=building.id,
            flat_id=flat.id,
            full_name=user.full_name,
            mobile=user.mobile,
            status="PENDING_APPROVAL",
        )
        db.session.add(req)
        db.session.commit()
        admin = User.query.filter_by(username="admin").first()
        RegistrationService.approve_request(req.id, admin)
        db.session.refresh(user)
        assert user.maintenance_start_month == req.approved_at.strftime("%Y-%m")
        assert (
            MaintenanceBill.query.filter_by(
                flat_id=flat.id, billing_month=user.maintenance_start_month
            ).count()
            == 1
        )
        BillingService.ensure_bill_for_flat(
            society.id, flat.id, user.residents[0].id, user.maintenance_start_month
        )
        assert (
            MaintenanceBill.query.filter_by(
                flat_id=flat.id, billing_month=user.maintenance_start_month
            ).count()
            == 1
        )


def test_existing_history_counts_only_unpaid_and_overdue(app):
    with app.app_context():
        society = Society.query.first()
        flat = society.flats[0]
        user, resident = make_resident(society, flat, "9888800002")
        for month, status in (
            ("2026-06", "Paid"),
            ("2026-07", "Pending"),
            ("2026-08", "Pending"),
        ):
            db.session.add(
                MaintenanceBill(
                    bill_number=f"RULE-{month}",
                    society_id=society.id,
                    flat_id=flat.id,
                    resident_id=resident.id,
                    billing_month=month,
                    base_amount=1500,
                    total_amount=1500,
                    remaining_amount=1500 if status != "Paid" else 0,
                    amount_paid=0 if status != "Paid" else 1500,
                    due_date=date(int(month[:4]), int(month[5:]), 10),
                    status=status,
                )
            )
        db.session.commit()
        dues = MaintenanceSummaryService.calculate_dues(
            user_id=user.id, as_of=date(2026, 8, 20)
        )
        assert dues["pending_months"] == 1
        assert dues["maintenance_due"] == 3000
        assert dues["late_fee"] == 500
        assert dues["total_due"] == 3500


def test_no_history_uses_configured_start_without_creating_bills(app, monkeypatch):
    with app.app_context():
        society = Society.query.first()
        user, resident = make_resident(society, society.flats[0], "9888800003")
        monkeypatch.setattr(Config, "MAINTENANCE_DEFAULT_START_MONTH", "2026-07")
        dues = MaintenanceSummaryService.calculate_dues(
            user_id=user.id, as_of=date(2026, 8, 20)
        )
        assert dues["billing_months"] == ["2026-07", "2026-08"]
        assert dues["pending_months"] == 1
        assert dues["maintenance_due"] == 3000
        assert dues["late_fee"] == 500
        assert MaintenanceBill.query.filter_by(flat_id=resident.flat_id).count() == 0


def test_payment_confirmation_uses_database_mobile_and_is_idempotent(app):
    with app.app_context():
        society = Society.query.first()
        user, resident = make_resident(society, society.flats[0], "9888800004")
        bill = BillingService.ensure_bill_for_flat(
            society.id, resident.flat_id, resident.id, "2026-08"
        )
        payment = PaymentService.process_successful_payment(
            bill.id,
            society.id,
            resident.id,
            bill.remaining_amount,
            "RULE-TXN-1",
            idempotency_key="RULE-IDEM-1",
        )
        retry = PaymentService.process_successful_payment(
            bill.id,
            society.id,
            resident.id,
            bill.remaining_amount,
            "RULE-TXN-1",
            idempotency_key="RULE-IDEM-1",
        )
        assert payment.bill.status == "Paid"
        assert retry.id == payment.id
        log = NotificationLog.query.filter_by(
            user_id=user.id,
            notification_type="PAYMENT_SUCCESS",
            billing_month="2026-08",
        ).one()
        assert log.recipient_mobile_or_email == "9888800004"
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                notification_type="PAYMENT_SUCCESS",
                billing_month="2026-08",
            ).count()
            == 1
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                notification_type="BILL_GENERATED",
                billing_month="2026-08",
            ).count()
            == 1
        )
