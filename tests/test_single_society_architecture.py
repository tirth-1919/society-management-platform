import pytest
from datetime import date
from app import create_app
from app.models import (
    db,
    User,
    Role,
    Society,
    Building,
    Block,
    Flat,
    Resident,
    Vehicle,
    Event,
)
from app.services.single_society_service import SingleSocietyService
from app.services.auth_service import AuthService


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SINGLE_SOCIETY_ID"] = "2"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()

        # Society 2 (Sunrise Heights)
        soc2 = Society(
            id=2,
            name="Sunrise Heights",
            registration_number="REG-SOC-001",
            address="100 SG Highway",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380054",
            email="contact@sunrise.com",
            phone="9876543201",
        )
        db.session.add(soc2)
        db.session.commit()

        # Wing & Block & Flats
        bld1 = Building(society_id=soc2.id, name="Block A")
        db.session.add(bld1)
        db.session.commit()

        blk1 = Block(society_id=soc2.id, building_id=bld1.id, name="Block A")
        db.session.add(blk1)
        db.session.commit()

        flat101 = Flat(society_id=soc2.id, building_id=bld1.id, block_id=blk1.id, flat_number="101")
        flat102 = Flat(society_id=soc2.id, building_id=bld1.id, block_id=blk1.id, flat_number="102")
        db.session.add_all([flat101, flat102])
        db.session.commit()

        # Operational Society Admin (Ramesh Sharma)
        admin = User(
            full_name="Ramesh Sharma",
            mobile="9100000001",
            email="admin@sunrise.com",
            role=Role.SOCIETY_ADMIN,
            society_id=soc2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("AdminPass@123")

        # Security Guard (Gate Security)
        guard = User(
            full_name="Gate Security",
            mobile="9700000001",
            email="guard@sunrise.com",
            role=Role.SECURITY,
            society_id=soc2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        guard.set_password("GuardPass@123")

        # Resident A (Amit Verma - Flat 101)
        res_a_user = User(
            full_name="Amit Verma",
            mobile="9800000001",
            email="amit@sunrise.com",
            role=Role.RESIDENT,
            society_id=soc2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_a_user.set_password("ResidentPass@123")

        # Resident B (Priya Mehta - Flat 102)
        res_b_user = User(
            full_name="Priya Mehta",
            mobile="9800000002",
            email="priya@sunrise.com",
            role=Role.RESIDENT,
            society_id=soc2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_b_user.set_password("ResidentPass@123")

        db.session.add_all([admin, guard, res_a_user, res_b_user])
        db.session.commit()

        r_a = Resident(society_id=soc2.id, flat_id=flat101.id, user_id=res_a_user.id, full_name="Amit Verma", mobile="9800000001", is_primary=True, occupancy_status="Active")
        r_b = Resident(society_id=soc2.id, flat_id=flat102.id, user_id=res_b_user.id, full_name="Priya Mehta", mobile="9800000002", is_primary=True, occupancy_status="Active")
        db.session.add_all([r_a, r_b])
        db.session.commit()

        yield app


@pytest.fixture
def client(app):
    return app.test_client()


# ============================================================
# 1. SINGLE SOCIETY RESOLUTION & CONFIGURATION
# ============================================================

def test_single_society_id_resolution(app):
    with app.app_context():
        assert SingleSocietyService.get_id() == 2
        soc = db.session.get(Society, 2)
        assert soc is not None
        assert soc.name == "Sunrise Heights"


# ============================================================
# 2. ADMIN LOGIN & PERMISSIONS (SOCIETY #2)
# ============================================================

def test_admin_login_and_society_context(client, app):
    with app.app_context():
        admin = User.query.filter_by(mobile="9100000001").first()
        admin_id = admin.id

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SOCIETY_ADMIN
        sess["society_id"] = 2

    # Admin dashboard opens
    resp = client.get("/dashboard")
    assert resp.status_code == 200

    # Admin vehicle management
    r_veh = client.get("/admin/vehicles")
    assert r_veh.status_code == 200

    # Admin cannot be overridden via client parameters
    r_tamper = client.get("/admin/vehicles?society_id=999")
    assert r_tamper.status_code == 200


def test_duplicate_operational_admin_prevention(app):
    with app.app_context():
        # An active admin (Ramesh Sharma) already exists for Society 2
        with pytest.raises(ValueError, match="An active society administrator already exists"):
            AuthService.validate_admin_creation(society_id=2)


# ============================================================
# 3. RESIDENT LOGIN & PERMISSIONS
# ============================================================

def test_resident_login_and_isolation(client, app):
    with app.app_context():
        res_a = User.query.filter_by(mobile="9800000001").first()
        res_a_id = res_a.id

    with client.session_transaction() as sess:
        sess["user_id"] = res_a_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = 2

    # Resident dashboard opens
    resp = client.get("/dashboard")
    assert resp.status_code == 200

    # Resident cannot access Admin routes
    r_admin = client.get("/admin/vehicles")
    assert r_admin.status_code == 403

    r_admin_flats = client.get("/admin/flats")
    assert r_admin_flats.status_code == 403


# ============================================================
# 4. GUARD LOGIN & PERMISSIONS
# ============================================================

def test_guard_login_and_permissions(client, app):
    with app.app_context():
        guard = User.query.filter_by(mobile="9700000001").first()
        guard_id = guard.id

    with client.session_transaction() as sess:
        sess["user_id"] = guard_id
        sess["role"] = Role.SECURITY
        sess["society_id"] = 2

    # Guard dashboard
    resp = client.get("/dashboard")
    assert resp.status_code == 200

    # Guard can view visitors list
    r_vis = client.get("/visitors/")
    assert r_vis.status_code == 200

    # Guard CANNOT access admin
    r_admin = client.get("/admin/vehicles")
    assert r_admin.status_code == 403

    # Guard CANNOT access resident portal
    r_res = client.get("/resident/vehicles")
    assert r_res.status_code == 403


# ============================================================
# 5. VEHICLE DIRECTORY & ADD VEHICLE (SINGLE SOCIETY)
# ============================================================

def test_resident_adds_vehicle_assigned_to_society_2(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000001").first()
        u1_id = u1.id

    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = 2

    post_resp = client.post(
        "/resident/vehicles/add",
        data={
            "vehicle_number": "GJ01PL5595",
            "vehicle_type": "Scooter",
            "make": "Honda",
            "model": "Activa",
            "color": "Silver",
            "parking_slot_number": "B1-04",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200

    with app.app_context():
        v = Vehicle.query.filter_by(vehicle_number="GJ01PL5595").first()
        assert v is not None
        assert v.society_id == 2
        assert v.owner_user_id == u1_id

    # Resident B opens directory and sees GJ01PL5595
    with app.app_context():
        u2 = User.query.filter_by(mobile="9800000002").first()
        u2_id = u2.id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = 2

    resp_b = client.get("/resident/vehicles")
    assert resp_b.status_code == 200
    assert b"GJ01PL5595" in resp_b.data
    assert b"Honda Activa" in resp_b.data
    assert b"tel:9800000001" in resp_b.data


# ============================================================
# 6. REGISTRATION AUTOMATICALLY USES SINGLE_SOCIETY_ID
# ============================================================

def test_registration_flow_single_society(client, app):
    # GET register page loads Sunrise Heights read-only
    get_resp = client.get("/register")
    assert get_resp.status_code == 200
    assert b"Sunrise Heights" in get_resp.data

    with app.app_context():
        flat102 = Flat.query.filter_by(flat_number="102").first()
        flat102_id = flat102.id
        bld_id = flat102.building_id
        blk_id = flat102.block_id

        # Mark resident B inactive so flat is available
        r_b = Resident.query.filter_by(flat_id=flat102_id).first()
        if r_b:
            r_b.occupancy_status = "Inactive"
            db.session.commit()

    post_resp = client.post(
        "/register",
        data={
            "full_name": "New Resident",
            "mobile": "9998887776",
            "email": "new@example.com",
            "building_id": bld_id,
            "block_id": blk_id,
            "flat_id": flat102_id,
            "occupancy_type": "OWNER",
            "password": "Password@123",
            "confirm_password": "Password@123",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200

    with app.app_context():
        u = User.query.filter_by(mobile="9998887776").first()
        assert u is not None
        assert u.society_id == 2
        assert u.account_status == "PENDING_APPROVAL"


# ============================================================
# 7. EVENTS & MEDIA MODERATION
# ============================================================

def test_events_and_media_visibility(client, app):
    with app.app_context():
        ev = Event(
            society_id=2,
            title="Diwali Celebration 2026",
            description="Community gathering",
            status="ACTIVE",
            start_date=date(2026, 11, 1),
        )
        db.session.add(ev)
        db.session.commit()

        u1 = User.query.filter_by(mobile="9800000001").first()
        u1_id = u1.id

    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = 2

    resp = client.get("/resident/events")
    assert resp.status_code == 200
    assert b"Diwali Celebration 2026" in resp.data
