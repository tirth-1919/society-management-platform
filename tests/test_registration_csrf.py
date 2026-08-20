import re
from app.models import Block, Building, Flat, RegistrationRequest, Role, Society, User, db

def _setup_request(app):
    society = Society.query.first()
    admin = User(
        username="csrf_admin",
        full_name="CSRF Admin",
        mobile="9112345678",
        email="csrf_admin@test.com",
        society_id=society.id,
        role=Role.SOCIETY_ADMIN,
        account_status="ACTIVE",
        is_active=True,
    )
    admin.set_password("Admin@123")
    applicant = User(
        full_name="CSRF Applicant",
        mobile="9812345678",
        email="csrf_applicant@test.com",
        society_id=society.id,
        role=Role.RESIDENT,
        account_status="PENDING_APPROVAL",
        is_active=False,
    )
    applicant.set_password("Password@123")
    db.session.add_all([admin, applicant])
    db.session.commit()
    building = Building.query.filter_by(society_id=society.id).first()
    block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
    flat = Flat.query.filter_by(
        society_id=society.id, building_id=building.id, block_id=block.id
    ).first()
    req = RegistrationRequest(
        user_id=applicant.id, society_id=society.id, building_id=building.id,
        block_id=block.id, flat_id=flat.id, full_name=applicant.full_name,
        mobile=applicant.mobile, email=applicant.email, occupancy_type="OWNER",
        status="PENDING_APPROVAL",
    )
    db.session.add(req)
    db.session.commit()
    return admin.id, admin.society_id, req.id

def _login(client, admin_id, society_id):
    with client.session_transaction() as session:
        session["user_id"] = admin_id
        session["society_id"] = society_id
        session["role"] = Role.SOCIETY_ADMIN

def _token(client):
    html = client.get("/admin/registrations").get_data(as_text=True)
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, "CSRF token missing from admin form"
    return match.group(1)

def test_approval_and_rejection_require_csrf(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        admin_id, admin_society_id, req_id = _setup_request(app)
    _login(client, admin_id, admin_society_id)
    assert client.post(f"/admin/registrations/{req_id}/approve").status_code == 400
    assert client.post(f"/admin/registrations/{req_id}/reject", data={"rejection_reason": "No"}).status_code == 400
    with app.app_context():
        assert db.session.get(RegistrationRequest, req_id).status == "PENDING_APPROVAL"


def test_valid_csrf_token_allows_approval(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        admin_id, admin_society_id, req_id = _setup_request(app)
    _login(client, admin_id, admin_society_id)
    token = _token(client)
    response = client.post(f"/admin/registrations/{req_id}/approve", data={"csrf_token": token})
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(RegistrationRequest, req_id).status == "APPROVED"


def test_valid_csrf_token_allows_rejection(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    with app.app_context():
        admin_id, admin_society_id, req_id = _setup_request(app)
    _login(client, admin_id, admin_society_id)
    token = _token(client)
    response = client.post(
        f"/admin/registrations/{req_id}/reject",
        data={"csrf_token": token, "rejection_reason": "Documents incomplete"},
    )
    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(RegistrationRequest, req_id).status == "REJECTED"
