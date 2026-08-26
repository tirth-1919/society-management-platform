from datetime import timedelta
from app.models import db, Resident, RegistrationRequest, Society, User, Role, Building, Block, Flat
from app.services.registration_service import get_registration_advisory
from app.utils import utcnow

def _admin(client, app):
    with app.app_context():
        society = Society.query.first()
        user = User(username="stage1_admin", full_name="Stage One Admin", mobile="9100001", email="stage1@example.com", society_id=society.id, role=Role.SOCIETY_ADMIN, account_status="ACTIVE", is_active=True)
        user.set_password("Admin@123")
        db.session.add(user)
        db.session.commit()
        with client.session_transaction() as session:
            session.update(user_id=user.id, society_id=society.id, role=Role.SOCIETY_ADMIN)
        return society.id

def test_admin_global_search_is_authenticated_and_society_scoped(client, app):
    with app.app_context():
        society = Society.query.first()
        resident = Resident.query.filter_by(society_id=society.id).first()
        if not resident:
            return
        resident.full_name = "Stage One Search Resident"
        db.session.commit()
        resident_id = resident.id
        other = Society.query.filter(Society.id != society.id).first()
        if other:
            other_user = User(full_name="Other Society Secret", mobile="9199999", society_id=other.id, role=Role.RESIDENT, account_status="ACTIVE", is_active=True)
            db.session.add(other_user)
            db.session.commit()
    _admin(client, app)
    response = client.get("/api/v1/search?q=Stage+One")
    assert response.status_code == 200
    payload = response.get_json()
    assert any(item["id"] == resident_id for category in payload["categories"] for item in category["items"])
    assert "Other Society Secret" not in response.get_data(as_text=True)


def test_registration_advisory_detects_existing_mobile_without_rejecting(app):
    with app.app_context():
        society = Society.query.first()
        resident = Resident.query.filter_by(society_id=society.id).first()
        if not resident:
            return
        req = RegistrationRequest(user_id=resident.user_id, society_id=society.id, flat_id=resident.flat_id, full_name="Applicant", mobile=resident.mobile, status="PENDING_APPROVAL", created_at=utcnow() - timedelta(days=4))
        db.session.add(req)
        db.session.commit()
        advisory = get_registration_advisory(req)
        assert advisory["duplicate_detected"] is True
        assert advisory["residents"]
        assert req.status == "PENDING_APPROVAL"


def test_registration_page_exposes_pending_aging_and_actions(client, app):
    with app.app_context():
        society = Society.query.first()
        admin = User(username="aging_admin", full_name="Aging Admin", mobile="9100002", society_id=society.id, role=Role.SOCIETY_ADMIN, account_status="ACTIVE", is_active=True)
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()
        building = Building.query.filter_by(society_id=society.id).first()
        block = Block.query.filter_by(society_id=society.id, building_id=building.id).first()
        flat = Flat.query.filter_by(society_id=society.id, building_id=building.id, block_id=block.id).first()
        req = RegistrationRequest(user_id=admin.id, society_id=society.id, building_id=building.id, block_id=block.id, flat_id=flat.id, full_name="Aging Applicant", mobile="9100003", status="PENDING_APPROVAL", created_at=utcnow() - timedelta(days=9))
        db.session.add(req)
        db.session.commit()
        with client.session_transaction() as session:
            session.update(user_id=admin.id, society_id=society.id, role=Role.SOCIETY_ADMIN)
    html = client.get("/admin/registrations").get_data(as_text=True)
    assert "8+ days" in html
    assert "Possible duplicate" in html or "Aging Applicant" in html
