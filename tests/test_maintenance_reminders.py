from datetime import date

from app.models import (
    db,
    Society,
    User,
    Role,
    Resident,
    MaintenanceBill,
    MaintenanceConfig,
    NotificationLog,
)
from app.services.notification_service import NotificationService


def reminder_fixture(
    society,
    flat,
    mobile,
    billing_month="2026-08",
    due_date=date(2026, 8, 10),
    status="Pending",
):
    user = User(
        full_name="Reminder Resident",
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
    db.session.flush()
    config = MaintenanceConfig(
        society_id=society.id,
        fixed_monthly_rate=1500,
        due_day_of_month=10,
        grace_period_days=3,
        late_fee_per_month=500,
    )
    bill = MaintenanceBill(
        bill_number=f"REM-{mobile}-{billing_month}",
        society_id=society.id,
        flat_id=flat.id,
        resident_id=resident.id,
        billing_month=billing_month,
        base_amount=1500,
        total_amount=1500,
        remaining_amount=0 if status == "Paid" else 1500,
        amount_paid=1500 if status == "Paid" else 0,
        due_date=due_date,
        status=status,
    )
    db.session.add_all([config, bill])
    db.session.commit()
    return user, bill


def test_upcoming_reminder_generated_and_linked_to_database_user(app):
    with app.app_context():
        society = Society.query.first()
        user, bill = reminder_fixture(society, society.flats[0], "9876500001")
        sent = NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 8))
        log = NotificationLog.query.filter_by(
            user_id=user.id,
            billing_month=bill.billing_month,
            notification_type="DUE_REMINDER",
        ).one()
        assert len(sent) == 1
        assert log.recipient_mobile_or_email == "9876500001"
        assert log.status == "Sent"
        assert "due on 10 August 2026" in log.message


def test_upcoming_reminder_not_sent_before_window(app):
    with app.app_context():
        society = Society.query.first()
        user, bill = reminder_fixture(society, society.flats[0], "9876500002")
        assert (
            NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 6)) == []
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month=bill.billing_month,
                notification_type="DUE_REMINDER",
            ).count()
            == 0
        )


def test_upcoming_duplicate_is_prevented(app):
    with app.app_context():
        society = Society.query.first()
        user, bill = reminder_fixture(society, society.flats[0], "9876500003")
        NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 8))
        NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 8))
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month=bill.billing_month,
                notification_type="DUE_REMINDER",
            ).count()
            == 1
        )


def test_overdue_reminder_calculates_late_fee_and_duplicate_is_prevented(app):
    with app.app_context():
        society = Society.query.first()
        user, bill = reminder_fixture(
            society,
            society.flats[0],
            "9876500004",
            billing_month="2026-07",
            due_date=date(2026, 7, 10),
        )
        sent = NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 11))
        NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 11))
        log = NotificationLog.query.filter_by(
            user_id=user.id,
            billing_month=bill.billing_month,
            notification_type="OVERDUE_REMINDER",
        ).one()
        assert len(sent) == 2
        assert "Maintenance: ₹1,500" in log.message
        assert "Late fee: ₹500" in log.message
        assert "Total due: ₹2,000" in log.message
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month=bill.billing_month,
                notification_type="OVERDUE_REMINDER",
            ).count()
            == 1
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month=bill.billing_month,
                notification_type="LATE_FEE_NOTICE",
            ).count()
            == 1
        )


def test_paid_month_has_no_overdue_reminder(app):
    with app.app_context():
        society = Society.query.first()
        user, bill = reminder_fixture(
            society, society.flats[0], "9876500005", status="Paid"
        )
        assert (
            NotificationService.send_maintenance_reminders(as_of=date(2026, 8, 11))
            == []
        )
        assert (
            NotificationLog.query.filter_by(
                user_id=user.id,
                billing_month=bill.billing_month,
                notification_type="OVERDUE_REMINDER",
            ).count()
            == 0
        )

