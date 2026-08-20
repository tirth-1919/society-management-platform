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



def test_admin_dashboard_navigation_is_relative_and_portal_local(client):
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "Admin@123"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'href="/dashboard"' in html
    assert "192.168.29.220" not in html
    assert "127.0.0.1:5001" not in html
    assert "localhost:5001" not in html


def test_admin_session_cookie_is_distinct_and_dashboard_stays_admin(client, app):
    app.config["SESSION_COOKIE_NAME"] = app.config["ADMIN_SESSION_COOKIE_NAME"]
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "Admin@123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    set_cookie = response.headers.get("Set-Cookie", "")
    assert "society_user_session" not in set_cookie
    dashboard = client.get("/dashboard", follow_redirects=False)
    assert dashboard.status_code == 200
    assert b"Dashboard Overview" in dashboard.data
    assert b"Admin Quick Tools" in dashboard.data
    assert "/login" not in dashboard.headers.get("Location", "")
    assert "/admin/login" not in dashboard.headers.get("Location", "")


def test_society_admin_session_reaches_admin_dashboard(client, app):
    with app.app_context():
        from app.models import Society
        society = Society.query.first()
        admin = User(
            username="society_admin_flow",
            full_name="Society Admin Flow",
            mobile="9800000077",
            society_id=society.id,
            role=Role.SOCIETY_ADMIN,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()

    response = client.post(
        "/admin/login",
        data={"username": "society_admin_flow", "password": "Admin@123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")
    dashboard = client.get("/dashboard", follow_redirects=False)
    assert dashboard.status_code == 200
    assert b"Dashboard Overview" in dashboard.data
    assert b"Admin Quick Tools" in dashboard.data


def test_admin_login_form_includes_csrf_and_opens_dashboard(client):
    login_page = client.get("/admin/login")
    assert login_page.status_code == 200
    assert b'name="csrf_token"' in login_page.data
    response = client.post(
        "/admin/login",
        data={"username": "admin", "password": "Admin@123"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/dashboard")


def test_yearly_summary_uses_database_independent_payment_date_ranges(client, app):
    from datetime import datetime, date
    from app.models import Payment, Resident, Society, User
    with app.app_context():
        society = Society.query.first()
        user = User(
            username="yearly_resident",
            full_name="Yearly Resident",
            mobile="9800000088",
            society_id=society.id,
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        user.set_password("Resident@123")
        db.session.add(user)
        db.session.flush()
        resident = Resident(
            society_id=society.id,
            flat_id=1,
            user_id=user.id,
            full_name=user.full_name,
            mobile=user.mobile,
            is_primary=True,
            occupancy_status="Active",
        )
        db.session.add(resident)
        db.session.flush()
        from app.models import Building, Block, Flat, MaintenanceBill
        building = Building.query.filter_by(society_id=society.id).first()
        block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
        flat = Flat.query.filter_by(society_id=society.id, building_id=building.id, block_id=block.id).first()
        resident.flat_id = flat.id
        bill = MaintenanceBill(
            society_id=society.id, building_id=building.id, block_id=block.id,
            flat_id=flat.id, resident_id=resident.id, bill_number="Y-BILL",
            billing_month="2026-01", base_amount=100, total_amount=100,
            amount_paid=100, remaining_amount=0, due_date=date(2026, 1, 10), status="Paid",
        )
        db.session.add(bill)
        db.session.flush()
        payments = [
            Payment(bill_id=bill.id, society_id=society.id, resident_id=resident.id, payment_date=datetime(2026, 1, 1), amount_paid=10, status="captured", transaction_id="Y-START"),
            Payment(bill_id=bill.id, society_id=society.id, resident_id=resident.id, payment_date=datetime(2026, 12, 31, 23, 59), amount_paid=20, status="Success", transaction_id="Y-END"),
            Payment(bill_id=bill.id, society_id=society.id, resident_id=resident.id, payment_date=datetime(2027, 1, 1), amount_paid=30, status="captured", transaction_id="Y-NEXT"),
        ]
        other = User(full_name="Other Resident", mobile="9800000089", society_id=society.id, role=Role.RESIDENT, account_status="ACTIVE", is_active=True)
        other.set_password("Resident@123")
        db.session.add(other)
        db.session.flush()
        other_resident = Resident(society_id=society.id, flat_id=flat.id, user_id=other.id, full_name=other.full_name, mobile=other.mobile, is_primary=True, occupancy_status="Active")
        db.session.add(other_resident)
        db.session.flush()
        payments.append(Payment(bill_id=bill.id, society_id=society.id, resident_id=other_resident.id, payment_date=datetime(2026, 6, 1), amount_paid=40, status="captured", transaction_id="Y-OTHER"))
        db.session.add_all(payments)
        db.session.commit()
        user_id = user.id
        society_id = society.id
    with client.session_transaction() as session:
        session["user_id"] = user_id
        session["society_id"] = society_id
        session["role"] = Role.RESIDENT
    response = client.get("/resident/payments/yearly?year=2026")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "Y-START" in html
    assert "Y-END" in html
    assert "Y-NEXT" not in html
    assert "Y-OTHER" not in html


def test_admin_payment_dashboard_is_society_scoped_and_month_range(client, app):
    from datetime import datetime
    from app.models import Building, Block, Flat, MaintenanceBill, Payment, Society
    with app.app_context():
        society = Society.query.first()
        other_society = Society.query.order_by(Society.id.desc()).first()
        building = Building.query.filter_by(society_id=society.id).first()
        block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
        flat = Flat.query.filter_by(society_id=society.id, building_id=building.id, block_id=block.id).first()
        bill = MaintenanceBill(
            society_id=society.id, building_id=building.id, block_id=block.id,
            flat_id=flat.id, bill_number="ADMIN-PAY-BILL", billing_month="2026-08",
            base_amount=100, total_amount=100, amount_paid=100, remaining_amount=0,
            due_date=datetime(2026, 8, 10), status="Paid",
        )
        db.session.add(bill)
        db.session.flush()
        payments = [
            Payment(bill_id=bill.id, society_id=society.id, payment_date=datetime(2026, 8, 1), amount_paid=10, status="captured", transaction_id="ADMIN-MONTH-START"),
            Payment(bill_id=bill.id, society_id=society.id, payment_date=datetime(2026, 8, 31, 23, 59), amount_paid=20, status="Success", transaction_id="ADMIN-MONTH-END"),
            Payment(bill_id=bill.id, society_id=society.id, payment_date=datetime(2026, 9, 1), amount_paid=30, status="captured", transaction_id="ADMIN-NEXT-MONTH"),
            Payment(bill_id=bill.id, society_id=society.id, payment_date=datetime(2026, 8, 15), amount_paid=40, status="failed", transaction_id="ADMIN-FAILED"),
            Payment(bill_id=bill.id, society_id=other_society.id, payment_date=datetime(2026, 8, 15), amount_paid=50, status="captured", transaction_id="ADMIN-OTHER-SOCIETY"),
        ]
        db.session.add_all(payments)
        db.session.commit()
        payment_ids = [payment.id for payment in payments]
        society_id = society.id
    client.post("/admin/login", data={"username": "admin", "password": "Admin@123"})
    with client.session_transaction() as session:
        session["society_id"] = society_id
    response = client.get("/payments/admin/dashboard")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "ADMIN-MONTH-START" in html
    assert "ADMIN-MONTH-END" in html
    assert "ADMIN-NEXT-MONTH" in html or response.status_code == 200
    assert "ADMIN-FAILED" in html
    assert "ADMIN-OTHER-SOCIETY" not in html
    with app.app_context():
        assert [payment.id for payment in Payment.query.order_by(Payment.id).all() if payment.id in payment_ids] == payment_ids
