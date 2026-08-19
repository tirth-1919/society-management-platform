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


def test_resident_bill_detail_and_receipts_working(client, app):
    with app.app_context():
        user, resident = _resident(app)
        bill = MaintenanceBill(
            bill_number="MB-TEST-001",
            society_id=user.society_id,
            flat_id=resident.flat_id,
            resident_id=resident.id,
            billing_month="2026-08",
            base_amount=2000,
            total_amount=2000,
            remaining_amount=2000,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()
        bill_id, user_id, society_id = bill.id, user.id, user.society_id

    _login(client, type("SessionUser", (), {"id": user_id, "society_id": society_id})())

    # 1. Bills page renders without BuildError
    res_bills = client.get("/resident/bills")
    assert res_bills.status_code == 200
    assert b"MB-TEST-001" in res_bills.data

    # 2. Bill detail page renders properly
    res_detail = client.get(f"/resident/bills/{bill_id}")
    assert res_detail.status_code == 200
    assert b"MB-TEST-001" in res_detail.data

    # 3. Receipts page renders without BuildError
    res_receipts = client.get("/resident/receipts")
    assert res_receipts.status_code == 200

    # 4. Another resident cannot view this bill detail (404)
    with app.app_context():
        other_user = User(
            full_name="Other Resident",
            mobile="9777088888",
            society_id=society_id,
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        other_user.set_password("Pass@123")
        db.session.add(other_user)
        db.session.flush()
        other_resident = Resident(
            society_id=society_id,
            flat_id=1,
            user_id=other_user.id,
            full_name=other_user.full_name,
            mobile=other_user.mobile,
            is_primary=True,
        )
        db.session.add(other_resident)
        db.session.commit()
        other_user_id = other_user.id

    _login(client, type("SessionUser", (), {"id": other_user_id, "society_id": society_id})())
    res_unauth = client.get(f"/resident/bills/{bill_id}")
    assert res_unauth.status_code == 404


