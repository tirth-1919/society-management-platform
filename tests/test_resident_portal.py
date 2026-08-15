from datetime import date

from app.models import db, MaintenanceBill, NotificationLog, Resident, Role, User


def _resident(app):
    society = __import__("app.models", fromlist=["Society"]).Society.query.first()
    flat = society.flats[0]
    user = User(
        full_name="Portal Resident",
        mobile="9777012345",
        email="portal@example.com",
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
        email=user.email,
        is_primary=True,
    )
    db.session.add(resident)
    db.session.commit()
    return user, resident


def _login(client, user):
    with client.session_transaction() as session:
        session["user_id"] = user.id
        session["society_id"] = user.society_id
        session["role"] = Role.RESIDENT


def test_resident_profile_and_notification_are_scoped(client, app):
    with app.app_context():
        user, resident = _resident(app)
        notification = NotificationLog(
            society_id=user.society_id,
            user_id=user.id,
            recipient_mobile_or_email=user.mobile,
            channel="In-App",
            notification_type="ACCOUNT_UPDATE",
            message="Profile updated.",
        )
        db.session.add(notification)
        db.session.commit()
        notification_id, user_id, society_id = notification.id, user.id, user.society_id
    _login(client, type("SessionUser", (), {"id": user_id, "society_id": society_id})())
    assert client.get("/resident/profile").status_code == 200
    assert (
        client.post(
            "/resident/profile",
            data={"full_name": "Updated Resident", "email": "updated@example.com"},
        ).status_code
        == 302
    )
    assert (
        client.post(f"/resident/notifications/{notification_id}/read").status_code
        == 302
    )
    with app.app_context():
        assert db.session.get(User, user_id).full_name == "Updated Resident"
        assert db.session.get(NotificationLog, notification_id).read_at is not None


def test_resident_cannot_access_previous_occupants_bill_or_receipt(client, app):
    with app.app_context():
        user, resident = _resident(app)
        old_user = User(
            full_name="Old Occupant",
            mobile="9777099999",
            society_id=user.society_id,
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        old_user.set_password("Pass@123")
        db.session.add(old_user)
        db.session.flush()
        old_resident = Resident(
            society_id=user.society_id,
            flat_id=resident.flat_id,
            user_id=old_user.id,
            full_name=old_user.full_name,
            mobile=old_user.mobile,
            is_primary=True,
        )
        db.session.add(old_resident)
        db.session.flush()
        bill = MaintenanceBill(
            bill_number="OLD-PORTAL-BILL",
            society_id=user.society_id,
            flat_id=resident.flat_id,
            resident_id=old_resident.id,
            billing_month="2026-08",
            base_amount=1500,
            total_amount=1500,
            remaining_amount=1500,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()
        bill_id, user_id, society_id = bill.id, user.id, user.society_id
    _login(client, type("SessionUser", (), {"id": user_id, "society_id": society_id})())
    assert client.get("/payments/bills").status_code == 200
    assert client.get(f"/payments/pay/{bill_id}").status_code == 403

