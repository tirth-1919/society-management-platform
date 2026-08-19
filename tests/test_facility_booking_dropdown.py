import html as html_lib
from datetime import date, timedelta
from app.models import Facility, db, User, Resident, Society, Building, Flat, Role
from app.services.facility_booking_service import FacilityBookingService

EXPECTED_10_FACILITIES = [
    "Club House",
    "Swimming Pool",
    "Gym",
    "Community Hall",
    "Party Hall",
    "Indoor Games Room",
    "Badminton Court",
    "Tennis Court",
    "Garden",
    "Children's Play Area",
]


def _setup_test_resident(app):
    with app.app_context():
        soc = Society.query.first()
        bld = Building.query.filter_by(society_id=soc.id).first()
        flat = Flat.query.filter_by(building_id=bld.id).first()

        user = User(
            full_name="Facility Test Resident",
            mobile="9876543210",
            email="fac_resident@test.com",
            role=Role.RESIDENT,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        user.set_password("Resident@123")
        db.session.add(user)
        db.session.commit()

        resident = Resident(
            user_id=user.id,
            society_id=soc.id,
            flat_id=flat.id,
            full_name="Facility Test Resident",
            mobile="9876543210",
            is_primary=True,
            occupancy_status="Active",
        )
        db.session.add(resident)
        db.session.commit()
        return user.id, soc.id, flat.id, resident.id


def test_ensure_default_facilities_seeds_all_10(app):
    with app.app_context():
        society = Society.query.first()
        FacilityBookingService.ensure_default_facilities(society.id)

        facilities = Facility.query.filter_by(society_id=society.id).all()
        fac_names = [f.name for f in facilities]

        for name in EXPECTED_10_FACILITIES:
            assert name in fac_names

        # Running again must not duplicate facilities
        FacilityBookingService.ensure_default_facilities(society.id)
        facilities_after = Facility.query.filter_by(society_id=society.id).all()
        assert len(facilities_after) == len(facilities)


def test_facility_booking_page_renders_dropdown_and_10_facilities(client, app):
    user_id, soc_id, flat_id, resident_id = _setup_test_resident(app)

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["society_id"] = soc_id

    res = client.get("/facilities/")
    assert res.status_code == 200
    rendered = html_lib.unescape(res.data.decode("utf-8"))

    assert "Select Facility" in rendered
    assert "Select a facility" in rendered
    assert "Book Facility" in rendered

    for name in EXPECTED_10_FACILITIES:
        assert name in rendered


def test_booking_validation_missing_fields_and_past_date(client, app):
    user_id, soc_id, flat_id, resident_id = _setup_test_resident(app)

    with app.app_context():
        today = date.today()
        yesterday = today - timedelta(days=1)
        future = today + timedelta(days=5)
        FacilityBookingService.ensure_default_facilities(soc_id)
        fac = Facility.query.filter_by(society_id=soc_id, name="Club House").first()
        fac_id = fac.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["society_id"] = soc_id

    # 1. Missing facility
    res = client.post("/facilities/book", data={
        "facility_id": "",
        "booking_date": future.strftime("%Y-%m-%d"),
        "start_time": "10:00",
        "end_time": "12:00",
    }, follow_redirects=True)
    assert "Facility is required." in res.data.decode("utf-8") or "required" in res.data.decode("utf-8")

    # 2. Past date
    res = client.post("/facilities/book", data={
        "facility_id": str(fac_id),
        "booking_date": yesterday.strftime("%Y-%m-%d"),
        "start_time": "10:00",
        "end_time": "12:00",
    }, follow_redirects=True)
    assert "past" in res.data.decode("utf-8")

    # 3. End time <= Start time
    res = client.post("/facilities/book", data={
        "facility_id": str(fac_id),
        "booking_date": future.strftime("%Y-%m-%d"),
        "start_time": "14:00",
        "end_time": "12:00",
    }, follow_redirects=True)
    assert "End time must be later than start time." in res.data.decode("utf-8")


def test_successful_facility_booking_and_overlap_prevention(client, app):
    user_id, soc_id, flat_id, resident_id = _setup_test_resident(app)

    with app.app_context():
        today = date.today()
        future = today + timedelta(days=10)
        FacilityBookingService.ensure_default_facilities(soc_id)
        fac = Facility.query.filter_by(society_id=soc_id, name="Club House").first()
        fac_id = fac.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["society_id"] = soc_id

    # Successful booking
    res = client.post("/facilities/book", data={
        "facility_id": str(fac_id),
        "booking_date": future.strftime("%Y-%m-%d"),
        "start_time": "14:00",
        "end_time": "16:00",
        "purpose": "Birthday Celebration",
        "notes": "Need 20 extra chairs",
    }, follow_redirects=True)

    html = res.data.decode("utf-8")
    assert "booked successfully" in html or "Club House" in html
    assert "Birthday Celebration" in html

    # Overlapping booking attempt
    res2 = client.post("/facilities/book", data={
        "facility_id": str(fac_id),
        "booking_date": future.strftime("%Y-%m-%d"),
        "start_time": "15:00",
        "end_time": "17:00",
        "purpose": "Another Event",
    }, follow_redirects=True)

    html2 = res2.data.decode("utf-8")
    assert "already booked" in html2
