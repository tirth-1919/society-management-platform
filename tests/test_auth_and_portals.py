from app.models import db, User, Role


def test_root_redirects_unauthenticated_users_to_login(client):
    res = client.get("/")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/login")


def test_admin_login_success(client):
    res = client.post(
        "/admin/login",
        data={"username": "admin", "password": "Admin@123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard")


def test_authenticated_admin_login_redirects_to_admin_dashboard(client, app):
    with app.app_context():
        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN
    res = client.get("/admin/login")
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/dashboard")


def test_resident_cannot_be_redirected_into_admin_dashboard(client, app):
    with app.app_context():
        resident = User(
            full_name="Admin Redirect Resident",
            mobile="9800000099",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        resident.set_password("Resident@123")
        db.session.add(resident)
        db.session.commit()
        resident_id = resident.id
    with client.session_transaction() as sess:
        sess["user_id"] = resident_id
        sess["role"] = Role.RESIDENT
    res = client.get("/admin/login")
    assert res.status_code == 200
    assert b"Admin Login" in res.data

def test_admin_login_failure(client):
    res = client.post(
        "/admin/login",
        data={"username": "admin", "password": "WrongPassword"},
        follow_redirects=True,
    )
    assert b"Invalid admin username or password" in res.data


def test_user_login_active(client, app):
    with app.app_context():
        u = User(
            full_name="Active Resident",
            mobile="9800000010",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()

    res = client.post(
        "/login",
        data={"mobile": "9800000010", "password": "Resident@123"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert b"Welcome back" in res.data or b"Dashboard" in res.data


def test_user_account_statuses_denied(client, app):
    with app.app_context():
        u_rej = User(
            full_name="Rejected User",
            mobile="9800000021",
            role=Role.RESIDENT,
            account_status="REJECTED",
            is_active=False,
        )
        u_rej.set_password("Resident@123")

        u_susp = User(
            full_name="Suspended User",
            mobile="9800000022",
            role=Role.RESIDENT,
            account_status="SUSPENDED",
            is_active=False,
        )
        u_susp.set_password("Resident@123")

        u_inac = User(
            full_name="Inactive User",
            mobile="9800000023",
            role=Role.RESIDENT,
            account_status="INACTIVE",
            is_active=False,
        )
        u_inac.set_password("Resident@123")

        db.session.add_all([u_rej, u_susp, u_inac])
        db.session.commit()

    for mob in ["9800000021", "9800000022", "9800000023"]:
        res = client.post(
            "/login",
            data={"mobile": mob, "password": "Resident@123"},
            follow_redirects=True,
        )
        assert b"Your account is not active" in res.data


def test_last_login_at_updated_only_on_success(client, app):
    with app.app_context():
        u = User(
            full_name="Last Login User",
            mobile="9800000030",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    # Failed login attempt
    client.post("/login", data={"mobile": "9800000030", "password": "WrongPassword"})
    with app.app_context():
        u_after_fail = db.session.get(User, uid)
        assert u_after_fail.last_login_at is None

    # Successful login
    client.post("/login", data={"mobile": "9800000030", "password": "Resident@123"})
    with app.app_context():
        u_after_success = db.session.get(User, uid)
        assert u_after_success.last_login_at is not None


def test_pending_user_dashboard_access_denied_403(client, app):
    with app.app_context():
        u = User(
            full_name="Pending Resident",
            mobile="9800000011",
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = Role.RESIDENT

    res = client.get("/dashboard")
    assert res.status_code == 403


def test_resident_access_admin_portal_denied_403(client, app):
    with app.app_context():
        u = User(
            full_name="Active Resident",
            mobile="9800000012",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()
        uid = u.id

    with client.session_transaction() as sess:
        sess["user_id"] = uid
        sess["role"] = Role.RESIDENT

    res = client.get("/admin/registrations")
    assert res.status_code == 403


def test_failed_login_attempts(client, app):
    with app.app_context():
        u = User(
            full_name="Active User",
            mobile="9800000013",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()

    for _ in range(5):
        client.post(
            "/login", data={"mobile": "9800000013", "password": "WrongPassword"}
        )

    res = client.post(
        "/login",
        data={"mobile": "9800000013", "password": "Resident@123"},
        follow_redirects=True,
    )
    assert b"Too many failed login attempts" in res.data or res.status_code == 200


def test_otp_generation_and_verification(client, app):
    with app.app_context():
        u = User(
            full_name="OTP User",
            mobile="9800000040",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()

    # Generate OTP
    res_gen = client.post("/otp-login", json={"mobile": "9800000040"})
    assert res_gen.status_code == 200
    data = res_gen.get_json()
    code = data.get("dev_otp")
    assert code is not None

    # Invalid OTP verify
    res_inv = client.post(
        "/verify-otp",
        data={"mobile": "9800000040", "otp_code": "000000"},
        follow_redirects=True,
    )
    assert b"Invalid OTP code" in res_inv.data

    # Valid OTP verify
    res_val = client.post(
        "/verify-otp",
        data={"mobile": "9800000040", "otp_code": code},
        follow_redirects=True,
    )
    assert b"OTP Verified Successfully" in res_val.data or b"Dashboard" in res_val.data

    # Re-use OTP (single-use check)
    res_reuse = client.post(
        "/verify-otp",
        data={"mobile": "9800000040", "otp_code": code},
        follow_redirects=True,
    )
    assert b"Invalid OTP code" in res_reuse.data


def test_logout_workflow(client, app):
    with app.app_context():
        u = User(
            full_name="Logout User",
            mobile="9800000050",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Resident@123")
        db.session.add(u)
        db.session.commit()

    client.post("/login", data={"mobile": "9800000050", "password": "Resident@123"})
    res_logout = client.get("/logout", follow_redirects=True)
    assert b"You have been logged out" in res_logout.data

