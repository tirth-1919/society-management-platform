import pytest
from app.models import (
    db,
    Block,
    Building,
    Flat,
    RegistrationRequest,
    Resident,
    Role,
    Society,
    User,
)


def _admin(app, society, suffix):
    user = User(
        username=f"admin_{suffix}",
        full_name=f"{society.name} Admin",
        mobile=f"91{suffix}000001",
        email=f"admin_{suffix}@test.com",
        society_id=society.id,
        role=Role.SOCIETY_ADMIN,
        account_status="ACTIVE",
        is_active=True,
    )
    user.set_password("Admin@123")
    db.session.add(user)
    db.session.commit()
    return user

def _resident_user(society, suffix, active=False):
    user = User(
        full_name=f"Applicant {suffix}",
        mobile=f"98{suffix}000001",
        email=f"applicant_{suffix}@test.com",
        society_id=society.id,
        role=Role.RESIDENT,
        account_status="ACTIVE" if active else "PENDING_APPROVAL",
        is_active=active,
    )
    user.set_password("Password@123")
    db.session.add(user)
    db.session.commit()
    return user

def _request(society, user, suffix):
    building = Building.query.filter_by(society_id=society.id).first()
    block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
    flat = Flat.query.filter_by(
        society_id=society.id, building_id=building.id, block_id=block.id
    ).first()
    req = RegistrationRequest(
        user_id=user.id,
        society_id=society.id,
        building_id=building.id,
        block_id=block.id,
        flat_id=flat.id,
        full_name=user.full_name,
        mobile=user.mobile,
        email=user.email,
        occupancy_type="OWNER",
        status="PENDING_APPROVAL",
    )
    db.session.add(req)
    db.session.commit()
    return req

def _login(client, user_id, society_id, role=Role.SOCIETY_ADMIN):
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["society_id"] = society_id
        session["role"] = role

def test_society_admin_sees_only_own_pending_requests(client, app):
    with app.app_context():
        s1, s2 = Society.query.order_by(Society.id).all()
        a1 = _admin(app, s1, "111")
        admin_id, admin_society_id = a1.id, a1.society_id
        r1 = _request(s1, _resident_user(s1, "111"), "111")
        r2 = _request(s2, _resident_user(s2, "222"), "222")
        r1_id, r2_id = r1.id, r2.id
    _login(client, admin_id, admin_society_id)
    response = client.get("/admin/registrations")
    html = response.get_data(as_text=True)
    assert response.status_code == 200
    assert f"#{r1_id}" in html
    assert f"#{r2_id}" not in html

def test_resident_cannot_access_or_approve_registration(client, app):
    with app.app_context():
        society = Society.query.first()
        resident = _resident_user(society, "333", active=True)
        req = _request(society, _resident_user(society, "334"), "334")
        req_id = req.id
        resident_id, resident_society_id = resident.id, resident.society_id
    _login(client, resident_id, resident_society_id, Role.RESIDENT)
    assert client.get("/admin/registrations").status_code in (302, 403)
    response = client.post(f"/admin/registrations/{req_id}/approve")
    assert response.status_code == 403
    with app.app_context():
        assert db.session.get(RegistrationRequest, req.id).status == "PENDING_APPROVAL"


def test_society_admin_approves_own_request_without_duplicates(client, app):
    with app.app_context():
        society = Society.query.first()
        admin = _admin(app, society, "444")
        applicant = _resident_user(society, "444")
        req = _request(society, applicant, "444")
        req_id, user_id, flat_id = req.id, applicant.id, req.flat_id
        society_id = society.id
        admin_id, admin_society_id = admin.id, admin.society_id
    _login(client, admin_id, admin_society_id)
    assert client.post(f"/admin/registrations/{req_id}/approve").status_code == 302
    assert client.post(f"/admin/registrations/{req_id}/approve").status_code == 302
    with app.app_context():
        saved = db.session.get(RegistrationRequest, req_id)
        assert saved.status == "APPROVED"
        assert saved.society_id == society_id
        assert saved.flat_id == flat_id
        assert User.query.filter_by(id=user_id).count() == 1
        assert Resident.query.filter_by(user_id=user_id).count() == 1

def test_society_admin_cannot_approve_or_reject_other_society(client, app):
    with app.app_context():
        s1, s2 = Society.query.order_by(Society.id).all()
        admin = _admin(app, s1, "555")
        req = _request(s2, _resident_user(s2, "555"), "555")
        req_id = req.id
        admin_id, admin_society_id = admin.id, admin.society_id
    _login(client, admin_id, admin_society_id)
    assert client.post(f"/admin/registrations/{req_id}/approve").status_code == 403
    assert client.post(
        f"/admin/registrations/{req_id}/reject",
        data={"rejection_reason": "Not this society"},
    ).status_code == 403
    with app.app_context():
        assert db.session.get(RegistrationRequest, req_id).status == "PENDING_APPROVAL"


def test_reject_own_request_and_rejection_is_idempotent(client, app):
    with app.app_context():
        society = Society.query.first()
        admin = _admin(app, society, "666")
        applicant = _resident_user(society, "666")
        req = _request(society, applicant, "666")
        req_id, user_id = req.id, applicant.id
        society_id = society.id
        admin_id, admin_society_id = admin.id, admin.society_id
    _login(client, admin_id, admin_society_id)
    data = {"rejection_reason": "Incomplete documents"}
    assert client.post(f"/admin/registrations/{req_id}/reject", data=data).status_code == 302
    assert client.post(f"/admin/registrations/{req_id}/reject", data=data).status_code == 302
    with app.app_context():
        saved = db.session.get(RegistrationRequest, req_id)
        assert saved.status == "REJECTED"
        assert saved.society_id == society_id
        assert Resident.query.filter_by(user_id=user_id).count() == 0
        assert db.session.get(User, user_id).is_active is False

def test_detail_page_and_actions_only_for_pending_requests(client, app):
    with app.app_context():
        society = Society.query.first()
        admin = _admin(app, society, "777")
        pending = _request(society, _resident_user(society, "777"), "777")
        approved = _request(society, _resident_user(society, "778"), "778")
        approved.status = "APPROVED"
        rejected = _request(society, _resident_user(society, "779"), "779")
        rejected.status = "REJECTED"
        db.session.commit()
        pending_id, approved_id, rejected_id = pending.id, approved.id, rejected.id
        admin_id, admin_society_id = admin.id, admin.society_id
    _login(client, admin_id, admin_society_id)
    detail = client.get(f"/admin/registrations/{pending_id}")
    assert detail.status_code == 200
    assert "Approve Registration" in detail.get_data(as_text=True)
    listing = client.get("/admin/registrations").get_data(as_text=True)
    assert "APPROVE" in listing
    assert f'id="approve-btn-{pending_id}"' in listing
    assert f"approve-btn-{approved_id}" not in listing
    assert f"approve-btn-{rejected_id}" not in listing

def test_registration_actions_are_post_only_and_forms_expose_csrf_hook(client, app):
    with app.app_context():
        society = Society.query.first()
        admin = _admin(app, society, "888")
        req = _request(society, _resident_user(society, "888"), "888")
        admin_id, admin_society_id = admin.id, admin.society_id
        req_id = req.id
    _login(client, admin_id, admin_society_id)
    assert client.get(f"/admin/registrations/{req_id}/approve").status_code == 405
    assert client.get(f"/admin/registrations/{req_id}/reject").status_code == 405
    html = client.get("/admin/registrations").get_data(as_text=True)
    if "csrf_token" in app.jinja_env.globals:
        assert 'name="csrf_token"' in html
