from app.models import db, Society, Building, Flat, RegistrationRequest, User, Role, Resident
from app.services.tenant_service import TenantService

EXPECTED_BLOCKS = ["Block A", "Block B", "Block C", "Block D", "Block E", "Block F"]

EXPECTED_FLATS = [
    "101", "102", "103", "104",
    "201", "202", "203", "204",
    "301", "302", "303", "304",
    "401", "402", "403", "404",
    "501", "502", "503", "504",
    "601", "602", "603", "604",
    "701", "702", "703", "704",
    "801", "802", "803", "804",
    "901", "902", "903", "904",
    "1001", "1002", "1003", "1004",
    "1101", "1102", "1103", "1104",
]


def test_ensure_default_blocks_and_flats_seeds_all_6_blocks_and_44_flats_each(app):
    with app.app_context():
        society = Society.query.first()
        TenantService.ensure_default_blocks_and_flats(society.id)

        buildings = Building.query.filter_by(society_id=society.id).all()
        building_names = [b.name for b in buildings]

        for block_name in EXPECTED_BLOCKS:
            assert block_name in building_names

        for block_name in EXPECTED_BLOCKS:
            b = Building.query.filter_by(society_id=society.id, name=block_name).first()
            flats = (
                Flat.query.filter_by(society_id=society.id, building_id=b.id)
                .order_by(Flat.floor_number.asc(), Flat.flat_number.asc())
                .all()
            )
            flat_numbers = [f.flat_number for f in flats]
            assert len(flat_numbers) == 44
            for expected_f in EXPECTED_FLATS:
                assert expected_f in flat_numbers


def test_api_buildings_and_api_flats_cascade(client, app):
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)

    # 1. Fetch buildings (Blocks A to F)
    res = client.get(f"/api/buildings?society_id={society_id}")
    assert res.status_code == 200
    data = res.get_json()
    b_names = [b["name"] for b in data["buildings"]]
    for block_name in EXPECTED_BLOCKS:
        assert block_name in b_names

    # 2. Fetch flats for Block A
    block_a = next(b for b in data["buildings"] if b["name"] == "Block A")
    res_a = client.get(f"/api/flats?building_id={block_a['id']}")
    assert res_a.status_code == 200
    flats_a = [f["flat_number"] for f in res_a.get_json()["flats"]]
    assert len(flats_a) == 44
    assert flats_a[0] == "101"
    assert flats_a[-1] == "1104"
    assert flats_a == EXPECTED_FLATS

    # 3. Fetch flats for Block F
    block_f = next(b for b in data["buildings"] if b["name"] == "Block F")
    res_f = client.get(f"/api/flats?building_id={block_f['id']}")
    assert res_f.status_code == 200
    flats_f = [f["flat_number"] for f in res_f.get_json()["flats"]]
    assert len(flats_f) == 44
    assert flats_f[0] == "101"
    assert flats_f[-1] == "1104"
    assert flats_f == EXPECTED_FLATS


def test_registration_with_block_a_flat_101(client, app):
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)
        b_a = Building.query.filter_by(society_id=society_id, name="Block A").first()
        b_a_id = b_a.id
        f_101 = Flat.query.filter_by(society_id=society_id, building_id=b_a.id, flat_number="101").first()
        assert f_101 is not None
        f_101_id = f_101.id

    res = client.post(
        "/register",
        data={
            "full_name": "Resident Block A",
            "mobile": "9900000101",
            "email": "block_a_101@test.com",
            "society_id": str(society_id),
            "building_id": str(b_a_id),
            "flat_id": str(f_101_id),
            "occupancy_type": "OWNER",
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    with app.app_context():
        req = RegistrationRequest.query.filter_by(mobile="9900000101").first()
        assert req is not None
        assert req.flat_id == f_101_id
        assert req.building_id == b_a_id


def test_registration_with_block_f_flat_1104(client, app):
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)
        b_f = Building.query.filter_by(society_id=society_id, name="Block F").first()
        b_f_id = b_f.id
        f_1104 = Flat.query.filter_by(society_id=society_id, building_id=b_f.id, flat_number="1104").first()
        assert f_1104 is not None
        f_1104_id = f_1104.id

    res = client.post(
        "/register",
        data={
            "full_name": "Resident Block F",
            "mobile": "9900001104",
            "email": "block_f_1104@test.com",
            "society_id": str(society_id),
            "building_id": str(b_f_id),
            "flat_id": str(f_1104_id),
            "occupancy_type": "OWNER",
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200
    with app.app_context():
        req = RegistrationRequest.query.filter_by(mobile="9900001104").first()
        assert req is not None
        assert req.flat_id == f_1104_id
        assert req.building_id == b_f_id


def test_registration_page_renders_block_selection_and_no_generic_wing(client, app):
    res = client.get("/register")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert "Select Wing" not in html
    assert "Location Selection (Block → Flat Number)" in html
    assert "Select Block" in html
    assert "Select Flat Number" in html


def test_full_scenario_block_a_flat_101_registration_approval_login_dashboard(client, app):
    """
    Scenario 13:
    Register: Name: Test Resident, Email: test@example.com, Mobile: 9811000101, Block: A, Flat: 101
    -> Status: PENDING_APPROVAL
    -> Admin sees all submitted details (Name, Email, Mobile, Block A, Flat 101, timestamp, status)
    -> Before approval: login attempt is blocked
    -> Admin approves registration -> status becomes ACTIVE / APPROVED
    -> Login succeeds -> User reaches Resident Dashboard -> Dashboard shows Block A, Flat 101
    """
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)
        block_a = Building.query.filter_by(society_id=society_id, name="Block A").first()
        flat_101 = Flat.query.filter_by(society_id=society_id, building_id=block_a.id, flat_number="101").first()
        assert flat_101 is not None

        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id

    # 1. Register user
    res_reg = client.post(
        "/register",
        data={
            "full_name": "Test Resident",
            "mobile": "9811000101",
            "email": "test@example.com",
            "society_id": str(society_id),
            "building_id": str(block_a.id),
            "flat_id": str(flat_101.id),
            "occupancy_type": "OWNER",
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert res_reg.status_code == 200

    with app.app_context():
        req = RegistrationRequest.query.filter_by(mobile="9811000101").first()
        assert req is not None
        assert req.status == "PENDING_APPROVAL"
        assert req.full_name == "Test Resident"
        assert req.email == "test@example.com"
        assert req.flat_id == flat_101.id
        assert req.building_id == block_a.id
        reg_id = req.id

        user = db.session.get(User, req.user_id)
        assert user.account_status == "PENDING_APPROVAL"
        assert user.is_active is False

    # 2. Admin opens registration detail & list pages, verifies details
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN
        sess["society_id"] = society_id

    res_admin_list = client.get("/admin/registrations")
    assert res_admin_list.status_code == 200
    html_admin_list = res_admin_list.data.decode("utf-8")
    assert "Test Resident" in html_admin_list
    assert "9811000101" in html_admin_list
    assert "Block A" in html_admin_list

    res_admin_detail = client.get(f"/admin/registrations/{reg_id}")
    assert res_admin_detail.status_code == 200
    html_detail = res_admin_detail.data.decode("utf-8")
    assert "Test Resident" in html_detail
    assert "test@example.com" in html_detail
    assert "9811000101" in html_detail
    assert "Block A" in html_detail
    assert "101" in html_detail
    assert "PENDING_APPROVAL" in html_detail

    # 3. Before approval: Attempt login with registered user -> MUST BE BLOCKED
    with client.session_transaction() as sess:
        sess.clear()

    res_login_pending = client.post(
        "/login",
        data={"mobile": "9811000101", "password": "Password@123"},
        follow_redirects=True,
    )
    assert res_login_pending.status_code == 200
    html_pending = res_login_pending.data.decode("utf-8")
    # Must not access resident dashboard; shows pending message/page
    assert "Registration Pending Approval" in html_pending or "pending" in html_pending.lower()
    with client.session_transaction() as sess:
        assert sess.get("user_id") is None or sess.get("role") != Role.RESIDENT

    # 4. Admin approves registration
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN
        sess["society_id"] = society_id

    res_approve = client.post(f"/admin/registrations/{reg_id}/approve", follow_redirects=True)
    assert res_approve.status_code == 200

    with app.app_context():
        req_approved = db.session.get(RegistrationRequest, reg_id)
        assert req_approved.status == "APPROVED"
        assert req_approved.approved_at is not None

        user_approved = db.session.get(User, req_approved.user_id)
        assert user_approved.account_status == "ACTIVE"
        assert user_approved.is_active is True
        assert user_approved.full_name == "Test Resident"
        assert user_approved.email == "test@example.com"
        assert user_approved.mobile == "9811000101"

        resident = Resident.query.filter_by(user_id=user_approved.id).first()
        assert resident is not None
        assert resident.occupancy_status == "Active"
        assert resident.flat_id == flat_101.id
        assert resident.full_name == "Test Resident"
        assert resident.email == "test@example.com"
        assert resident.mobile == "9811000101"
        assert resident.flat.flat_number == "101"
        assert resident.flat.building.name == "Block A"

    # 5. Login after approval -> MUST SUCCEED and open Resident Dashboard
    with client.session_transaction() as sess:
        sess.clear()

    res_login_active = client.post(
        "/login",
        data={"mobile": "9811000101", "password": "Password@123"},
        follow_redirects=True,
    )
    assert res_login_active.status_code == 200
    html_dashboard = res_login_active.data.decode("utf-8")
    assert "Test Resident" in html_dashboard
    assert "101" in html_dashboard
    assert "Block A" in html_dashboard

    # 6. Check Resident Profile page
    res_profile = client.get("/resident/profile")
    assert res_profile.status_code == 200
    html_profile = res_profile.data.decode("utf-8")
    assert "Test Resident" in html_profile
    assert "101" in html_profile
    assert "Block A" in html_profile


def test_full_scenario_block_f_flat_1104_registration_approval_login_dashboard(client, app):
    """
    Scenario 14:
    Register: Name: Second Resident, Email: second@example.com, Mobile: 9811001104, Block: F, Flat: 1104
    -> Registration saves correctly
    -> Admin sees Block F, Flat 1104
    -> Approve -> User becomes ACTIVE
    -> User logs in -> Resident data shows Block F, Flat 1104
    """
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)
        block_f = Building.query.filter_by(society_id=society_id, name="Block F").first()
        flat_1104 = Flat.query.filter_by(society_id=society_id, building_id=block_f.id, flat_number="1104").first()
        assert flat_1104 is not None

        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id

    # 1. Register
    res_reg = client.post(
        "/register",
        data={
            "full_name": "Second Resident",
            "mobile": "9811001104",
            "email": "second@example.com",
            "society_id": str(society_id),
            "building_id": str(block_f.id),
            "flat_id": str(flat_1104.id),
            "occupancy_type": "OWNER",
            "password": "Password@123",
        },
        follow_redirects=True,
    )
    assert res_reg.status_code == 200

    with app.app_context():
        req = RegistrationRequest.query.filter_by(mobile="9811001104").first()
        assert req is not None
        assert req.status == "PENDING_APPROVAL"
        assert req.flat_id == flat_1104.id
        assert req.building_id == block_f.id
        reg_id = req.id

    # 2. Admin sees Block F, Flat 1104
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN
        sess["society_id"] = society_id

    res_admin_detail = client.get(f"/admin/registrations/{reg_id}")
    assert res_admin_detail.status_code == 200
    html_detail = res_admin_detail.data.decode("utf-8")
    assert "Second Resident" in html_detail
    assert "Block F" in html_detail
    assert "1104" in html_detail

    # 3. Approve
    res_approve = client.post(f"/admin/registrations/{reg_id}/approve", follow_redirects=True)
    assert res_approve.status_code == 200

    with app.app_context():
        u = User.query.filter_by(mobile="9811001104").first()
        assert u.account_status == "ACTIVE"
        assert u.is_active is True
        res_obj = Resident.query.filter_by(user_id=u.id).first()
        assert res_obj.flat.flat_number == "1104"
        assert res_obj.flat.building.name == "Block F"

    # 4. User logs in
    with client.session_transaction() as sess:
        sess.clear()

    res_login = client.post(
        "/login",
        data={"mobile": "9811001104", "password": "Password@123"},
        follow_redirects=True,
    )
    assert res_login.status_code == 200
    html_dash = res_login.data.decode("utf-8")
    assert "Second Resident" in html_dash
    assert "1104" in html_dash
    assert "Block F" in html_dash


def test_invalid_block_flat_combination_rejected(client, app):
    """Mismatched block and flat combination must be rejected server-side."""
    with app.app_context():
        society = Society.query.first()
        society_id = society.id
        TenantService.ensure_default_blocks_and_flats(society_id)
        block_a = Building.query.filter_by(society_id=society_id, name="Block A").first()
        block_f = Building.query.filter_by(society_id=society_id, name="Block F").first()
        # Flat 1104 belongs to Block F
        flat_f_1104 = Flat.query.filter_by(society_id=society_id, building_id=block_f.id, flat_number="1104").first()

    # Submit Block A ID with Flat belonging to Block F
    res = client.post(
        "/register",
        data={
            "full_name": "Mismatch Tester",
            "mobile": "9811009999",
            "email": "mismatch@example.com",
            "society_id": str(society_id),
            "building_id": str(block_a.id),
            "flat_id": str(flat_f_1104.id),
            "occupancy_type": "OWNER",
            "password": "Password@123",
        },
    )
    # Must be rejected (403 Forbidden hierarchy mismatch)
    assert res.status_code == 403
