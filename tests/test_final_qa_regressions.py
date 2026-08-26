from datetime import date, timedelta
import re
from app.models import db, Complaint, FacilityBooking, PreApprovedPass, SupportRequest
from test_production_400_and_features_audit import resident_setup

def _resident_session(client, resident_setup):
    user = resident_setup["user"]
    with client.session_transaction() as sess:
        sess.update(user_id=user.id, role=user.role, society_id=user.society_id)
    return user

def _csrf(client, path):
    response = client.get(path)
    return re.search(rb'name="csrf_token" value="([^"]+)"', response.data).group(1).decode()


def test_valid_csrf_and_invalid_csrf_for_resident_mutations(client, app, resident_setup):
    app.config["WTF_CSRF_ENABLED"] = True
    user = _resident_session(client, resident_setup)
    token = _csrf(client, "/resident/profile")
    response = client.post("/resident/profile", data={"full_name": "Valid QA", "email": "valid.qa@example.com", "csrf_token": token})
    assert response.status_code == 302
    response = client.post("/resident/profile", data={"full_name": "Rejected QA", "email": "rejected.qa@example.com", "csrf_token": "invalid"})
    assert response.status_code == 400
    db.session.refresh(user)
    assert user.full_name == "Valid QA"


def test_invalid_required_fields_remain_controlled(client, resident_setup):
    user = _resident_session(client, resident_setup)
    checks = [
        ("/resident/profile", {"email": "missing-name@example.com"}),
        ("/complaints/create", {"category": "Plumbing", "description": "missing title"}),
        ("/resident/visitors/invite", {"visitor_name": "Missing date", "mobile": "9898989898"}),
        ("/facilities/book", {"facility_id": resident_setup["facility"].id}),
        ("/resident/support/new", {"subject": "Missing message"}),
        ("/api/v1/resident/ai/query", {"prompt": ""}),
    ]
    for path, payload in checks:
        request_kwargs = {"json": payload} if path.startswith("/api/") else {"data": payload}
        response = client.post(path, **request_kwargs)
        assert response.status_code in (200, 302, 400), (path, response.status_code)
        assert response.status_code != 500

def test_fixed_records_keep_authenticated_tenant(client, resident_setup):
    user = _resident_session(client, resident_setup)
    society_id = user.society_id
    client.post("/complaints/create", data={"title": "Tenant QA", "description": "Scoped", "category": "General"})
    client.post("/resident/visitors/invite", data={"visitor_name": "Tenant Visitor", "mobile": "9898989888", "expected_date": (date.today() + timedelta(days=1)).isoformat()})
    client.post("/resident/support/new", data={"subject": "Tenant Support", "message": "Scoped support", "category": "Other"})
    assert Complaint.query.filter_by(title="Tenant QA", society_id=society_id).first()
    assert PreApprovedPass.query.filter_by(visitor_name="Tenant Visitor", society_id=society_id).first()
    assert SupportRequest.query.filter_by(subject="Tenant Support", society_id=society_id).first()
