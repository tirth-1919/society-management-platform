from datetime import datetime
from app.models import Block, Building, NotificationLog, Notice, Resident, Role, Society, User, db

def _resident_setup(app, suffix=""):
    society = Society.query.first()
    building = Building.query.filter_by(society_id=society.id).first()
    block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
    flat = block.flats[0]
    user = User(full_name=f"Notice Resident{suffix}", mobile=f"980000006{6 if not suffix else 7}", society_id=society.id, role=Role.RESIDENT, account_status="ACTIVE", is_active=True)
    user.set_password("Resident@123")
    db.session.add(user)
    db.session.flush()
    resident = Resident(society_id=society.id, flat_id=flat.id, user_id=user.id, full_name=user.full_name, mobile=user.mobile, is_primary=True, occupancy_status="Active")
    db.session.add(resident)
    db.session.commit()
    return user.id, resident.id, society.id

def _login(client, user_id, society_id):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["society_id"] = society_id
        session["role"] = Role.RESIDENT

def test_announcements_use_notice_created_at(client, app):
    with app.app_context():
        user_id, _resident_id, society_id = _resident_setup(app)
        society = db.session.get(Society, society_id)
        user = db.session.get(User, user_id)
        notice = Notice(society_id=society.id, title="Water Notice", content="Water supply update", created_at=datetime(2026, 8, 20), notice_type="Water")
        db.session.add(notice)
        db.session.commit()
    _login(client, user_id, society_id)
    response = client.get("/resident/announcements")
    assert response.status_code == 200
    assert b"Water Notice" in response.data
    assert b"20 Aug 2026" in response.data
    assert b"publish_date" not in response.data

def test_announcements_are_society_scoped(client, app):
    with app.app_context():
        user_id, _resident_id, society_id = _resident_setup(app)
        other = Society.query.order_by(Society.id.desc()).first()
        if other.id == society_id:
            other = Society.query.filter(Society.id != society_id).first()
        db.session.add(Notice(society_id=other.id, title="Other Society Notice", content="Hidden", created_at=datetime(2026, 8, 20)))
        db.session.commit()
    _login(client, user_id, society_id)
    response = client.get("/resident/announcements")
    assert response.status_code == 200
    assert b"Other Society Notice" not in response.data

def test_notification_read_posts_require_and_accept_csrf(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        user_id, _resident_id, society_id = _resident_setup(app)
        society = db.session.get(Society, society_id)
        user = db.session.get(User, user_id)
        notification = NotificationLog(user_id=user.id, society_id=society.id, recipient_mobile_or_email=user.mobile, channel="In-App", notification_type="PAYMENT_SUCCESS", subject="Paid", message="Payment received")
        db.session.add(notification)
        db.session.commit()
        notification_id = notification.id
    _login(client, user_id, society_id)
    page = client.get("/resident/notifications")
    import re
    token = re.search(rb'name="csrf_token" value="([^"]+)"', page.data).group(1).decode()
    assert client.post(f"/resident/notifications/{notification_id}/read").status_code == 400
    assert client.post("/resident/notifications/mark-all-read").status_code == 400
    assert client.post(f"/resident/notifications/{notification_id}/read", data={"csrf_token": token}).status_code == 302
    assert client.post("/resident/notifications/mark-all-read", data={"csrf_token": token}).status_code == 302
    with app.app_context():
        assert db.session.get(NotificationLog, notification_id).read_at is not None

def test_resident_cannot_mark_another_residents_notification_read(client, app):
    with app.app_context():
        user_id, _resident_id, society_id = _resident_setup(app)
        other_id, _other_resident_id, _ = _resident_setup(app, " Other")
        other = db.session.get(User, other_id)
        notification = NotificationLog(user_id=other.id, society_id=society_id, recipient_mobile_or_email=other.mobile, channel="In-App", notification_type="PAYMENT_SUCCESS", message="Private")
        db.session.add(notification)
        db.session.commit()
        notification_id = notification.id
    _login(client, user_id, society_id)
    assert client.post(f"/resident/notifications/{notification_id}/read").status_code == 404
