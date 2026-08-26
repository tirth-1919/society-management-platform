import pytest
from app import create_app
from app.models import (
    db,
    User,
    Role,
    Society,
    Building,
    Flat,
    Resident,
    Vehicle,
    ParkingSlot,
)
from app.services.parking_vehicle_service import ParkingVehicleService


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    app.config["SINGLE_SOCIETY_ID"] = "1"
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()

        # Society 1
        soc1 = Society(
            name="Sunrise Heights",
            registration_number="REG-SOC-001",
            address="100 SG Highway",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380054",
            email="contact@sunrise.com",
            phone="9876543201",
        )
        # Society 2
        soc2 = Society(
            name="Emerald Greens",
            registration_number="REG-SOC-002",
            address="200 Ring Road",
            city="Surat",
            state="Gujarat",
            pincode="395007",
            email="contact@emerald.com",
            phone="9876543202",
        )
        db.session.add_all([soc1, soc2])
        db.session.commit()

        # Buildings & Flats
        bld1 = Building(society_id=soc1.id, name="Wing A")
        bld2 = Building(society_id=soc2.id, name="Wing B")
        db.session.add_all([bld1, bld2])
        db.session.commit()

        flat1 = Flat(society_id=soc1.id, building_id=bld1.id, flat_number="101")
        flat2 = Flat(society_id=soc1.id, building_id=bld1.id, flat_number="102")
        flat103 = Flat(society_id=soc1.id, building_id=bld1.id, flat_number="103")
        flat3 = Flat(society_id=soc2.id, building_id=bld2.id, flat_number="201")
        db.session.add_all([flat1, flat2, flat103, flat3])
        db.session.commit()

        # Admin User for Soc 1
        admin1 = User(
            full_name="Admin Tirth",
            mobile="9800000001",
            email="admin@sunrise.com",
            role=Role.SOCIETY_ADMIN,
            society_id=soc1.id,
            account_status="ACTIVE",
        )
        admin1.set_password("AdminPass@123")

        # Resident A in Soc 1 (Flat 101)
        res1_user = User(
            full_name="Tirth Patel",
            mobile="9800000002",
            email="tirth@sunrise.com",
            role=Role.RESIDENT,
            society_id=soc1.id,
            account_status="ACTIVE",
        )
        res1_user.set_password("ResidentPass@123")

        # Resident B in Soc 1 (Flat 102)
        res2_user = User(
            full_name="Pooja Shah",
            mobile="9800000003",
            email="pooja@sunrise.com",
            role=Role.RESIDENT,
            society_id=soc1.id,
            account_status="ACTIVE",
        )
        res2_user.set_password("ResidentPass@123")

        # Resident C in Soc 1 (Flat 103)
        res_c_user = User(
            full_name="Chirag Joshi",
            mobile="9800000005",
            email="chirag@sunrise.com",
            role=Role.RESIDENT,
            society_id=soc1.id,
            account_status="ACTIVE",
        )
        res_c_user.set_password("ResidentPass@123")

        # Resident in Soc 2 (Flat 201)
        res3_user = User(
            full_name="Rohan Mehta",
            mobile="9800000004",
            email="rohan@emerald.com",
            role=Role.RESIDENT,
            society_id=soc2.id,
            account_status="ACTIVE",
        )
        res3_user.set_password("ResidentPass@123")

        db.session.add_all([admin1, res1_user, res2_user, res_c_user, res3_user])
        db.session.commit()

        # Primary Resident records
        r1 = Resident(society_id=soc1.id, flat_id=flat1.id, user_id=res1_user.id, full_name="Tirth Patel", mobile="9800000002", is_primary=True)
        r2 = Resident(society_id=soc1.id, flat_id=flat2.id, user_id=res2_user.id, full_name="Pooja Shah", mobile="9800000003", is_primary=True)
        r_c = Resident(society_id=soc1.id, flat_id=flat103.id, user_id=res_c_user.id, full_name="Chirag Joshi", mobile="9800000005", is_primary=True)
        r3 = Resident(society_id=soc2.id, flat_id=flat3.id, user_id=res3_user.id, full_name="Rohan Mehta", mobile="9800000004", is_primary=True)
        db.session.add_all([r1, r2, r_c, r3])
        db.session.commit()

        # Parking Slot in Soc 1
        slot1 = ParkingSlot(society_id=soc1.id, slot_number="P-42", location_block="Basement 1", flat_id=flat1.id, status="Allocated")
        db.session.add(slot1)
        db.session.commit()

        yield app


@pytest.fixture
def client(app):
    return app.test_client()


# ============================================================
# 1. MODEL & NORMALIZATION TESTS
# ============================================================

def test_number_plate_normalization(app):
    with app.app_context():
        assert ParkingVehicleService.normalize_plate("GJ02XX1234") == "GJ02XX1234"
        assert ParkingVehicleService.normalize_plate("GJ 02 XX 1234") == "GJ02XX1234"
        assert ParkingVehicleService.normalize_plate("gj02xx1234") == "GJ02XX1234"
        assert ParkingVehicleService.normalize_plate("GJ-02-XX-1234") == "GJ02XX1234"
        assert ParkingVehicleService.normalize_plate("GJ.02/XX_1234") == "GJ02XX1234"
        assert ParkingVehicleService.normalize_plate("") == ""


# TEST 1 — OWNER (Resident A creates Vehicle GJ02XX1234 and phone is verified)
def test_test1_owner_creates_vehicle(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        u1_id = u1.id
        u1_soc = u1.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    post_resp = client.post(
        "/resident/vehicles/add",
        data={
            "vehicle_number": "GJ02XX1234",
            "vehicle_type": "Car",
            "make": "Honda",
            "model": "City",
            "color": "White",
            "parking_slot_number": "P-42",
            "secondary_mobile": "9876543210",
            "notes": "Private parking instructions",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200
    assert b"registered successfully" in post_resp.data

    with app.app_context():
        veh = Vehicle.query.filter_by(vehicle_number="GJ02XX1234").first()
        assert veh is not None
        assert veh.owner_user_id == u1_id
        assert veh.normalized_number_plate == "GJ02XX1234"
        assert veh.brand_model == "Honda City"
        assert veh.secondary_mobile == "9876543210"
        assert veh.status == "ACTIVE"


# TEST 2 — SAME SOCIETY SEARCH (Resident B searches GJ02XX1234)
def test_test2_same_society_search_and_call(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
            color="White",
            parking_slot_number="P-42",
            secondary_mobile="9876543210",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    # Resident B logs in and searches
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.get("/resident/vehicles?q=GJ02XX1234")
    assert resp.status_code == 200
    assert b"GJ02XX1234" in resp.data
    assert b"Honda City" in resp.data
    assert b"Tirth Patel" in resp.data
    assert b"9800000002" in resp.data
    assert b"tel:9800000002" in resp.data  # Call action
    assert b"tel:9876543210" in resp.data  # Call Alt action
    assert b"View Details" in resp.data


# TEST 3 — THIRD RESIDENT (Resident C searches same vehicle)
def test_test3_third_resident_search(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
            color="White",
        )

        u_c = User.query.filter_by(mobile="9800000005").first()
        u_c_id = u_c.id
        u_c_soc = u_c.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u_c_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u_c_soc

    resp = client.get("/resident/vehicles?q=GJ02XX1234")
    assert resp.status_code == 200
    assert b"GJ02XX1234" in resp.data
    assert b"Honda City" in resp.data
    assert b"Tirth Patel" in resp.data
    assert b"tel:9800000002" in resp.data


# TEST 4 — OWNER EDIT (Resident A can edit their own vehicle)
def test_test4_owner_edit(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        u1_id = u1.id
        u1_soc = u1.society_id
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        veh = ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )
        veh_id = veh.id

    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    edit_resp = client.post(
        f"/resident/vehicles/{veh_id}/edit",
        data={
            "vehicle_number": "GJ02XX1234",
            "vehicle_type": "Car",
            "make": "Honda",
            "model": "City ZX",
            "color": "Pearl White",
            "parking_slot_number": "P-42",
        },
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200
    assert b"updated successfully" in edit_resp.data

    with app.app_context():
        v = db.session.get(Vehicle, veh_id)
        assert v.model == "City ZX"
        assert v.color == "Pearl White"


# TEST 5 — NON-OWNER EDIT (Resident B attempts to edit Resident A's vehicle -> 403 / 404)
def test_test5_non_owner_edit_rejected(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        veh = ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )
        veh_id = veh.id

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.post(
        f"/resident/vehicles/{veh_id}/edit",
        data={"make": "Hacked", "vehicle_number": "GJ02XX1234"},
    )
    assert resp.status_code in [403, 404]

    with app.app_context():
        v = db.session.get(Vehicle, veh_id)
        assert v.make == "Honda"


# TEST 6 — NON-OWNER DELETE (Resident B attempts to deactivate Resident A's vehicle -> 403 / 404)
def test_test6_non_owner_delete_rejected(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        veh = ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )
        veh_id = veh.id

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.post(f"/resident/vehicles/{veh_id}/deactivate")
    assert resp.status_code in [403, 404]

    with app.app_context():
        v = db.session.get(Vehicle, veh_id)
        assert v.status == "ACTIVE"


# TEST 7 — SOCIETY ISOLATION (Society 2 resident vehicle not visible to Society 1 / Society 3)
def test_test7_society_isolation(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()  # Soc 1
        u1_id = u1.id
        u1_soc = u1.society_id

        u3 = User.query.filter_by(mobile="9800000004").first()  # Soc 2
        r3 = Resident.query.filter_by(user_id=u3.id).first()

        # Society 2 vehicle
        v_soc2 = ParkingVehicleService.register_vehicle(
            society_id=u3.society_id,
            owner_user_id=u3.id,
            resident_id=r3.id,
            flat_id=r3.flat_id,
            vehicle_number="GJ02XX1234",
            make="Honda",
            model="City",
        )
        v_soc2_id = v_soc2.id

    # Society 1 resident searches
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    resp = client.get("/resident/vehicles?q=GJ02XX1234")
    assert b"Honda City" not in resp.data
    assert b"No vehicle found" in resp.data

    # Direct view IDOR check across society
    resp_detail = client.get(f"/resident/vehicles/{v_soc2_id}")
    assert resp_detail.status_code in [403, 404]


# TEST 8 — SEARCH NORMALIZATION (gj02xx1234, GJ02 XX 1234, GJ-02-XX-1234)
def test_test8_search_normalization(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    # Lowercase
    r1 = client.get("/resident/vehicles?q=gj02xx1234")
    assert b"GJ02XX1234" in r1.data
    assert b"Honda City" in r1.data

    # Spaced
    r2 = client.get("/resident/vehicles?q=GJ 02 XX 1234")
    assert b"GJ02XX1234" in r2.data

    # Hyphenated
    r3 = client.get("/resident/vehicles?q=GJ-02-XX-1234")
    assert b"GJ02XX1234" in r3.data


# TEST 9 — PARTIAL SEARCH (GJ02, Honda, Swift)
def test_test9_partial_search(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02AB4567",
            vehicle_type="Car",
            make="Maruti",
            model="Swift",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    # Partial number
    r_partial = client.get("/resident/vehicles?q=GJ02")
    assert b"GJ02XX1234" in r_partial.data
    assert b"GJ02AB4567" in r_partial.data

    # Make search
    r_make = client.get("/resident/vehicles?q=Honda")
    assert b"GJ02XX1234" in r_make.data

    # Model search
    r_model = client.get("/resident/vehicles?q=Swift")
    assert b"GJ02AB4567" in r_model.data


# TEST 10 — CALL BUTTON (Phone present vs not present)
def test_test10_call_button_behavior(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02PHONE1",
            make="Hyundai",
            secondary_mobile="9998887776",
        )

        # Vehicle with no phone
        u_nophone = User(
            full_name="No Phone User",
            mobile="",
            email="nophone@sunrise.com",
            role=Role.RESIDENT,
            society_id=u1.society_id,
            account_status="ACTIVE",
        )
        u_nophone.set_password("Pass@123")
        db.session.add(u_nophone)
        db.session.commit()

        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u_nophone.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02NOPHONE2",
            make="Tata",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    # Search vehicle with phone
    r_phone = client.get("/resident/vehicles?q=GJ02PHONE1")
    assert b"tel:9800000002" in r_phone.data
    assert b"tel:9998887776" in r_phone.data
    assert b"Call" in r_phone.data

    # Search vehicle without phone
    r_nophone = client.get("/resident/vehicles?q=GJ02NOPHONE2")
    assert b"Phone number not available" in r_nophone.data


# TEST 11 & 12 — OWNER & SOCIETY MANIPULATION (Tampering parameters rejected)
def test_test11_and_12_owner_society_tampering(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        u1_id = u1.id
        u1_soc = u1.society_id
        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id

    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    # Attempt to pass spoofed owner_user_id and society_id in POST body
    client.post(
        "/resident/vehicles/add",
        data={
            "vehicle_number": "GJ02SPOOF01",
            "make": "Kia",
            "owner_user_id": u2_id,  # spoofed
            "society_id": 999,  # spoofed
        },
        follow_redirects=True,
    )

    with app.app_context():
        veh = Vehicle.query.filter_by(vehicle_number="GJ02SPOOF01").first()
        assert veh is not None
        assert veh.owner_user_id == u1_id  # Derived from session, NOT spoofed
        assert veh.society_id == u1_soc  # Derived from session, NOT spoofed


# TEST 13 — PRIVATE DATA NOT EXPOSED
def test_test13_private_data_protection(client, app):
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ02SECRET01",
            make="BMW",
            notes="Secret confidential note: OTP=123456",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    # Non-owner searches
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.get("/resident/vehicles?q=GJ02SECRET01")
    assert b"OTP=123456" not in resp.data
    assert b"Secret confidential note" not in resp.data

    # Non-owner views detail
    with app.app_context():
        veh = Vehicle.query.filter_by(vehicle_number="GJ02SECRET01").first()
        veh_id = veh.id

    resp_detail = client.get(f"/resident/vehicles/{veh_id}")
    assert resp_detail.status_code == 200
    assert b"OTP=123456" not in resp_detail.data
    assert b"Secret confidential note" not in resp_detail.data
    # Non-owner does NOT see edit/deactivate buttons
    assert b"Edit" not in resp_detail.data
    assert b"Deactivate" not in resp_detail.data


# TEST 14 — ADMIN VEHICLE MANAGEMENT
def test_test14_admin_vehicle_management(client, app):
    with app.app_context():
        admin = User.query.filter_by(mobile="9800000001").first()
        admin_id = admin.id
        admin_soc = admin.society_id
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        veh = ParkingVehicleService.register_vehicle(
            society_id=admin.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ01ADM999",
            vehicle_type="Car",
            make="Mercedes",
            model="C-Class",
            parking_slot_number="P-01",
            secondary_mobile="9876543299",
            status="ACTIVE",
        )
        veh_id = veh.id

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SOCIETY_ADMIN
        sess["society_id"] = admin_soc

    # 1. Admin Directory List
    list_resp = client.get("/admin/vehicles")
    assert list_resp.status_code == 200
    assert b"GJ01ADM999" in list_resp.data

    # 2. Admin View Full Detail
    view_resp = client.get(f"/admin/vehicles/{veh_id}")
    assert view_resp.status_code == 200
    assert b"9876543299" in view_resp.data

    # 3. Admin Edit Vehicle
    edit_resp = client.post(
        f"/admin/vehicles/{veh_id}/edit",
        data={
            "vehicle_number": "GJ01ADM999",
            "vehicle_type": "Car",
            "make": "Mercedes",
            "model": "E-Class",
            "color": "Silver",
            "parking_slot_number": "P-02",
            "status": "ACTIVE",
        },
        follow_redirects=True,
    )
    assert edit_resp.status_code == 200
    assert b"updated successfully" in edit_resp.data

    with app.app_context():
        v = db.session.get(Vehicle, veh_id)
        assert v.model == "E-Class"


# TEST 15 — EXACT PROMPT SCENARIO: AMIT VERMA / GJ01PL5595
def test_test15_exact_prompt_scenario_amit_verma_gj01pl5595(client, app):
    with app.app_context():
        admin = User.query.filter_by(role=Role.SOCIETY_ADMIN).first()
        admin.mobile = "9100000001"
        db.session.commit()

        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        u1.full_name = "Amit Verma"
        u1.mobile = "9800000001"
        r1.full_name = "Amit Verma"
        r1.mobile = "9800000001"

        # Ensure flat is BLOCK A-101
        from app.models import Block
        blk = Block(society_id=u1.society_id, building_id=r1.flat.building_id, name="Block A")
        db.session.add(blk)
        db.session.flush()
        r1.flat.block_id = blk.id
        r1.flat.flat_number = "101"
        db.session.commit()

        # Register GJ01PL5595
        veh = ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ01PL5595",
            vehicle_type="Scooter",
            make="Honda",
            model="Activa",
            color="Silver",
            parking_slot_number="B1-04",
            status="ACTIVE",
        )
        veh_id = veh.id
        u1_id = u1.id
        u1_soc = u1.society_id

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

        u_c = User.query.filter_by(mobile="9800000005").first()
        u_c_id = u_c.id
        u_c_soc = u_c.society_id

        u_soc2 = User.query.filter_by(mobile="9800000004").first()
        u_soc2_id = u_soc2.id
        u_soc2_soc = u_soc2.society_id

        admin = User.query.filter_by(role=Role.SOCIETY_ADMIN).first()
        admin_id = admin.id
        admin_soc = admin.society_id

    # 1. Resident B (same society) searches GJ01PL5595
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.get("/resident/vehicles?q=GJ01PL5595")
    assert resp.status_code == 200
    assert b"GJ01PL5595" in resp.data
    assert b"Honda Activa" in resp.data
    assert b"Amit Verma" in resp.data
    assert b"9800000001" in resp.data
    assert b"B1-04" in resp.data
    assert b"tel:9800000001" in resp.data
    assert b"View Details" in resp.data

    # 2. Resident B searches normalization & partials
    for q in ["gj01pl5595", "GJ01 PL 5595", "GJ01", "Amit", "Activa", "BLOCK A-101", "B1-04"]:
        r = client.get(f"/resident/vehicles?q={q}")
        assert r.status_code == 200
        assert b"GJ01PL5595" in r.data, f"Query '{q}' did not return GJ01PL5595"

    # 3. Resident C (same society) searches
    with client.session_transaction() as sess:
        sess["user_id"] = u_c_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u_c_soc

    resp_c = client.get("/resident/vehicles?q=GJ01PL5595")
    assert resp_c.status_code == 200
    assert b"GJ01PL5595" in resp_c.data

    # 4. Resident A (owner) searches own vehicle
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    resp_a = client.get("/resident/vehicles?q=GJ01PL5595")
    assert resp_a.status_code == 200
    assert b"GJ01PL5595" in resp_a.data

    # 5. Cross-Society Resident (Society 2) searches
    with client.session_transaction() as sess:
        sess["user_id"] = u_soc2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u_soc2_soc

    resp_other = client.get("/resident/vehicles?q=GJ01PL5595")
    assert resp_other.status_code == 200
    assert b"No vehicle found" in resp_other.data
    assert b"Amit Verma" not in resp_other.data
    assert b"tel:9800000001" not in resp_other.data
    assert b"B1-04" not in resp_other.data

    # 6. Resident B attempts to edit Resident A vehicle -> 403
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    edit_hack = client.post(f"/resident/vehicles/{veh_id}/edit", data={"make": "TVS", "vehicle_number": "GJ01HACK"})
    assert edit_hack.status_code == 403

    # 7. Resident B attempts to deactivate Resident A vehicle -> 403
    deact_hack = client.post(f"/resident/vehicles/{veh_id}/deactivate")
    assert deact_hack.status_code == 403

    # 8. Admin sees vehicle in admin directory
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SOCIETY_ADMIN
        sess["society_id"] = admin_soc

    admin_resp = client.get("/admin/vehicles")
    assert admin_resp.status_code == 200
    assert b"GJ01PL5595" in admin_resp.data


# ============================================================
# TESTS 16 - 19: FULL WORKFLOW & EMPTY STATE VERIFICATION
# ============================================================

def test_test16_initial_directory_load_shows_all_society_vehicles(client, app):
    """When a resident opens Parking & Vehicles without search, all society vehicles are displayed."""
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ01PL5595",
            vehicle_type="Scooter",
            make="Honda",
            model="Activa",
        )
        u2 = User.query.filter_by(mobile="9800000003").first()
        r2 = Resident.query.filter_by(user_id=u2.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u2.society_id,
            owner_user_id=u2.id,
            resident_id=r2.id,
            flat_id=r2.flat_id,
            vehicle_number="GJ02XX1234",
            vehicle_type="Car",
            make="Honda",
            model="City",
        )

        u2_id = u2.id
        u2_soc = u2.society_id

    # Resident B opens Parking & Vehicles with NO search query
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    resp = client.get("/resident/vehicles")
    assert resp.status_code == 200
    # Directory shows both vehicles
    assert b"GJ01PL5595" in resp.data
    assert b"Honda Activa" in resp.data
    assert b"GJ02XX1234" in resp.data
    assert b"Honda City" in resp.data
    assert b"Society Vehicle Directory" in resp.data
    assert b"Registered Vehicles: 2" in resp.data
    assert b"No vehicle found" not in resp.data


def test_test17_empty_society_vehicles_state(client, app):
    """When a society has no vehicles, opening /resident/vehicles shows proper empty state."""
    with app.app_context():
        # Society 2 resident has no vehicles
        u3 = User.query.filter_by(mobile="9800000004").first()
        u3_id = u3.id
        u3_soc = u3.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u3_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u3_soc

    resp = client.get("/resident/vehicles")
    assert resp.status_code == 200
    assert b"No vehicles registered yet" in resp.data
    assert b"No vehicle found" not in resp.data


def test_test18_vehicle_type_filtering(client, app):
    """Vehicle type category filters (Cars, Bikes, Other) filter the society directory accurately."""
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        r1 = Resident.query.filter_by(user_id=u1.id).first()
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ01CAR001",
            vehicle_type="Car",
            make="Hyundai",
            model="Creta",
        )
        ParkingVehicleService.register_vehicle(
            society_id=u1.society_id,
            owner_user_id=u1.id,
            resident_id=r1.id,
            flat_id=r1.flat_id,
            vehicle_number="GJ01BIKE01",
            vehicle_type="Scooter",
            make="Honda",
            model="Activa",
        )

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    # 1. Filter Cars
    r_cars = client.get("/resident/vehicles?type=Cars")
    assert r_cars.status_code == 200
    assert b"GJ01CAR001" in r_cars.data
    assert b"GJ01BIKE01" not in r_cars.data

    # 2. Filter Bikes
    r_bikes = client.get("/resident/vehicles?type=Bikes")
    assert r_bikes.status_code == 200
    assert b"GJ01BIKE01" in r_bikes.data
    assert b"GJ01CAR001" not in r_bikes.data


def test_test19_new_vehicle_visible_to_all_residents_after_refresh(client, app):
    """Resident A adds vehicle GJ04ZZ8888, Resident B refreshes and sees it immediately from DB."""
    with app.app_context():
        u1 = User.query.filter_by(mobile="9800000002").first()
        u1_id = u1.id
        u1_soc = u1.society_id

        u2 = User.query.filter_by(mobile="9800000003").first()
        u2_id = u2.id
        u2_soc = u2.society_id

    # 1. Resident A adds vehicle
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u1_soc

    post_resp = client.post(
        "/resident/vehicles/add",
        data={
            "vehicle_number": "GJ04ZZ8888",
            "vehicle_type": "Car",
            "make": "Toyota",
            "model": "Innova",
            "color": "Silver",
            "parking_slot_number": "P-99",
        },
        follow_redirects=True,
    )
    assert post_resp.status_code == 200

    # 2. Resident B refreshes /resident/vehicles and sees GJ04ZZ8888
    with client.session_transaction() as sess:
        sess["user_id"] = u2_id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = u2_soc

    refresh_resp = client.get("/resident/vehicles")
    assert refresh_resp.status_code == 200
    assert b"GJ04ZZ8888" in refresh_resp.data
    assert b"Toyota Innova" in refresh_resp.data

    # 3. Resident B searches for GJ04ZZ8888
    search_resp = client.get("/resident/vehicles?q=GJ04ZZ8888")
    assert search_resp.status_code == 200
    assert b"GJ04ZZ8888" in search_resp.data
    assert b"Toyota Innova" in search_resp.data
