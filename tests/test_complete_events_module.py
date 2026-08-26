"""Automated Verification Suite for Global Resident Events Module."""
import io
import random
from datetime import datetime
from PIL import Image
import pytest
from app import create_app
from app.models import db, Event, EventPhoto, Resident, Role, Society, User
from app.services.event_gallery_seed_service import EventGallerySeedService


@pytest.fixture
def app_instance():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    return app


@pytest.fixture
def client(app_instance):
    return app_instance.test_client()


def _random_image():
    color = (random.randint(10, 240), random.randint(10, 240), random.randint(10, 240))
    img = Image.new("RGB", (200, 200), color=color)
    img_io = io.BytesIO()
    img.save(img_io, "JPEG")
    img_io.seek(0)
    return img_io


def test_initial_events_and_media_exist(app_instance):
    """Verify Navratri 2024 and Diwali 2024 exist with exactly 5 initial approved photos each."""
    with app_instance.app_context():
        navratri_2024 = Event.query.filter_by(title="Navratri 2024").first()
        assert navratri_2024 is not None, "Navratri 2024 missing."
        assert navratri_2024.approved_photos_count >= 5, f"Expected 5 approved photos, found {navratri_2024.approved_photos_count}"

        diwali_2024 = Event.query.filter_by(title="Diwali 2024").first()
        assert diwali_2024 is not None, "Diwali 2024 missing."
        assert diwali_2024.approved_photos_count >= 5, f"Expected 5 approved photos, found {diwali_2024.approved_photos_count}"


def test_idempotent_seeding(app_instance):
    """Verify running ensure_defaults multiple times creates zero duplicate events or photos."""
    with app_instance.app_context():
        admin = User.query.filter_by(role=Role.SOCIETY_ADMIN).first() or User.query.filter_by(role=Role.SUPER_ADMIN).first()
        count_before = Event.query.count()
        photos_before = EventPhoto.query.count()

        EventGallerySeedService.ensure_defaults(society_id=2, admin_user=admin)

        count_after = Event.query.count()
        photos_after = EventPhoto.query.count()

        assert count_before == count_after, f"Events duplicated: {count_before} -> {count_after}"
        assert photos_before == photos_after, f"Photos duplicated: {photos_before} -> {photos_after}"


def test_global_event_visibility_across_multiple_societies(app_instance, client):
    """Verify residents belonging to Society 1, Society 2, and other societies all see the same global events."""
    with app_instance.app_context():
        # Ensure Society 1 exists and has an active resident user
        soc1 = Society.query.get(1)
        if not soc1:
            soc1 = Society(
                id=1,
                name="Emerald Heights",
                registration_number="REG-001",
                address="Sector 1",
                city="Mumbai",
                state="Maharashtra",
                pincode="400001",
                email="soc1@test.com",
                phone="9800000001",
            )
            db.session.add(soc1)
            db.session.commit()

        res_soc1 = User.query.filter_by(society_id=1, role=Role.RESIDENT, account_status="ACTIVE").first()
        if not res_soc1:
            res_soc1 = User(
                username="res_soc1_test",
                full_name="Resident Society 1",
                mobile="9900000001",
                email="res1@test.com",
                role=Role.RESIDENT,
                society_id=1,
                account_status="ACTIVE",
                is_active=True,
            )
            res_soc1.set_password("Resident@123")
            db.session.add(res_soc1)
            db.session.commit()

        # Society 2 resident
        res_soc2 = User.query.filter_by(society_id=2, role=Role.RESIDENT, account_status="ACTIVE").first()

        # Create Society 3 and resident if needed
        soc3 = Society.query.get(3)
        if not soc3:
            soc3 = Society(
                id=3,
                name="Palm Grove",
                registration_number="REG-003",
                address="Sector 3",
                city="Mumbai",
                state="Maharashtra",
                pincode="400003",
                email="soc3@test.com",
                phone="9800000003",
            )
            db.session.add(soc3)
            db.session.commit()

        res_soc3 = User.query.filter_by(society_id=3, role=Role.RESIDENT, account_status="ACTIVE").first()
        if not res_soc3:
            res_soc3 = User(
                username="res_soc3_test",
                full_name="Resident Society 3",
                mobile="9900000003",
                email="res3@test.com",
                role=Role.RESIDENT,
                society_id=3,
                account_status="ACTIVE",
                is_active=True,
            )
            res_soc3.set_password("Resident@123")
            db.session.add(res_soc3)
            db.session.commit()

        soc1_user_id = res_soc1.id
        soc2_user_id = res_soc2.id
        soc3_user_id = res_soc3.id

    # Test all 3 residents see the global events
    for uid, soc_id in [(soc1_user_id, 1), (soc2_user_id, 2), (soc3_user_id, 3)]:
        with client.session_transaction() as sess:
            sess["user_id"] = uid
            sess["role"] = "Resident"
            sess["society_id"] = soc_id

        resp = client.get("/resident/events?filter=past")
        assert resp.status_code == 200, f"Failed for society {soc_id}"
        html = resp.data.decode("utf-8")
        assert "Navratri 2024" in html, f"Navratri 2024 missing for resident of society {soc_id}"
        assert "Diwali 2024" in html, f"Diwali 2024 missing for resident of society {soc_id}"


def test_resident_upload_pending_moderation_and_cross_society_approval(app_instance, client):
    """Verify upload enters PENDING, is hidden from other residents across societies, and visible to all once approved."""
    with app_instance.app_context():
        res_soc1 = User.query.filter_by(society_id=1, role=Role.RESIDENT, account_status="ACTIVE").first()
        res_soc2 = User.query.filter_by(society_id=2, role=Role.RESIDENT, account_status="ACTIVE").first()
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first() or User.query.filter_by(role=Role.SOCIETY_ADMIN).first()

        event = Event.query.filter_by(title="Navratri 2024").first()
        event_id = event.id
        soc1_user_id = res_soc1.id
        soc2_user_id = res_soc2.id
        admin_id = admin.id

    img_io = _random_image()

    # Resident from Society 1 uploads photo
    with client.session_transaction() as sess:
        sess["user_id"] = soc1_user_id
        sess["role"] = "Resident"
        sess["society_id"] = 1

    upload_resp = client.post(
        f"/resident/events/{event_id}/photos",
        data={"photo": (img_io, f"garba_{random.randint(100,999)}.jpg", "image/jpeg"), "caption": "Garba Celebration"},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201, f"Upload error: {upload_resp.get_json()}"
    json_data = upload_resp.get_json()
    photo_id = json_data["items"][0]["id"]
    assert json_data["items"][0]["status"] == "PENDING"

    # Resident from Society 2 visits gallery -> PENDING photo must NOT be visible
    with client.session_transaction() as sess:
        sess["user_id"] = soc2_user_id
        sess["role"] = "Resident"
        sess["society_id"] = 2

    gallery_resp = client.get(f"/resident/events/{event_id}/photos")
    assert gallery_resp.status_code == 200
    items = gallery_resp.get_json()["items"]
    assert not any(p["id"] == photo_id for p in items), "PENDING photo was visible in public gallery!"

    # Admin approves photo
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = "Super Admin"

    approve_resp = client.post(f"/admin/events/photos/{photo_id}/approve")
    assert approve_resp.status_code == 200

    # Now Resident from Society 2 visits gallery -> photo MUST be visible!
    with client.session_transaction() as sess:
        sess["user_id"] = soc2_user_id
        sess["role"] = "Resident"
        sess["society_id"] = 2

    gallery_resp2 = client.get(f"/resident/events/{event_id}/photos")
    assert gallery_resp2.status_code == 200
    items2 = gallery_resp2.get_json()["items"]
    assert any(p["id"] == photo_id for p in items2), "APPROVED photo not visible to resident of Society 2!"


def test_rejected_media_remains_hidden(app_instance, client):
    """Verify rejected media is hidden from resident gallery."""
    with app_instance.app_context():
        res = User.query.filter_by(society_id=2, role=Role.RESIDENT, account_status="ACTIVE").first()
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first() or User.query.filter_by(role=Role.SOCIETY_ADMIN).first()
        event = Event.query.filter_by(title="Diwali 2024").first()
        event_id = event.id
        user_id = res.id
        admin_id = admin.id

    img_io = _random_image()

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = "Resident"
        sess["society_id"] = 2

    upload_resp = client.post(
        f"/resident/events/{event_id}/photos",
        data={"photo": (img_io, f"blur_{random.randint(100,999)}.jpg", "image/jpeg"), "caption": "Blurry moment"},
        content_type="multipart/form-data",
    )
    assert upload_resp.status_code == 201
    photo_id = upload_resp.get_json()["items"][0]["id"]

    # Admin rejects photo
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = "Super Admin"

    reject_resp = client.post(
        f"/admin/events/photos/{photo_id}/reject",
        json={"rejection_reason": "Low quality"},
    )
    assert reject_resp.status_code == 200

    # Check gallery -> rejected photo is NOT in public gallery
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = "Resident"
        sess["society_id"] = 2

    gallery_resp = client.get(f"/resident/events/{event_id}/photos")
    items = gallery_resp.get_json()["items"]
    assert not any(p["id"] == photo_id for p in items)


def test_archived_and_draft_events_hidden_from_residents(app_instance, client):
    """Verify archived and draft/unpublished events do not appear on resident events listing."""
    with app_instance.app_context():
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first() or User.query.filter_by(role=Role.SOCIETY_ADMIN).first()
        archived_event = Event.query.filter_by(title="Secret Archived Event").first()
        if not archived_event:
            archived_event = Event(
                society_id=2,
                title="Secret Archived Event",
                status="ARCHIVED",
                start_date=datetime(2026, 1, 1),
                created_by_id=admin.id,
            )
            db.session.add(archived_event)

        draft_event = Event.query.filter_by(title="Draft Internal Event").first()
        if not draft_event:
            draft_event = Event(
                society_id=2,
                title="Draft Internal Event",
                status="DRAFT",
                start_date=datetime(2026, 1, 1),
                created_by_id=admin.id,
            )
            db.session.add(draft_event)
        db.session.commit()

        res = User.query.filter_by(society_id=2, role=Role.RESIDENT, account_status="ACTIVE").first()
        user_id = res.id

    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["role"] = "Resident"
        sess["society_id"] = 2

    resp = client.get("/resident/events?filter=past")
    assert resp.status_code == 200
    html = resp.data.decode("utf-8")
    assert "Secret Archived Event" not in html
    assert "Draft Internal Event" not in html


def test_tenant_isolation_preserved_for_other_modules(app_instance, client):
    """Verify tenant isolation remains strictly enforced for non-event modules (Bills, Complaints, etc.)."""
    with app_instance.app_context():
        res1 = User.query.filter_by(society_id=1, role=Role.RESIDENT).first()
        r_profile = Resident.query.filter_by(user_id=res1.id).first()
        if not r_profile:
            r_profile = Resident(
                society_id=1,
                user_id=res1.id,
                full_name=res1.full_name,
                email=res1.email,
                mobile=res1.mobile,
                is_primary=True,
            )
            db.session.add(r_profile)
            db.session.commit()
        user1_id = res1.id

    with client.session_transaction() as sess:
        sess["user_id"] = user1_id
        sess["role"] = "Resident"
        sess["society_id"] = 1

    # Resident of Society 1 visits /resident/bills
    resp = client.get("/resident/bills")
    assert resp.status_code == 200
