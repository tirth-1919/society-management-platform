import pytest
from datetime import date, timedelta
from app.models import (
    db,
    User,
    Role,
    Society,
    Building,
    Flat,
    Resident,
    Complaint,
    Facility,
    FacilityBooking,
    PreApprovedPass,
    SupportRequest,
    MaintenanceBill,
    Payment,
    AuditLog,
)
from app.utils import utcnow


@pytest.fixture
def resident_setup(app):
    with app.app_context():
        s = db.session.get(Society, 1)
        b = Building.query.filter_by(society_id=s.id).first()
        f = Flat.query.filter_by(society_id=s.id).first()

        res_user = User(
            username="res_tester",
            full_name="Rajesh Test Patel",
            mobile="9825099999",
            email="rajesh.test@example.com",
            role=Role.RESIDENT,
            society_id=s.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("ResidentPass@123")
        db.session.add(res_user)
        db.session.commit()

        resident = Resident(
            society_id=s.id,
            flat_id=f.id,
            user_id=res_user.id,
            full_name="Rajesh Test Patel",
            mobile="9825099999",
            email="rajesh.test@example.com",
            resident_type="Owner",
            occupancy_status="Active",
        )
        db.session.add(resident)
        db.session.flush()

        # Create a facility
        fac = Facility(
            society_id=s.id,
            name="Clubhouse Hall",
            description="Main clubhouse hall for events",
            capacity=100,
            is_active=True,
        )
        db.session.add(fac)

        # Create sample bill
        bill = MaintenanceBill(
            bill_number="BILL-TEST-001",
            society_id=s.id,
            flat_id=f.id,
            resident_id=resident.id,
            billing_month=date.today().strftime("%Y-%m"),
            base_amount=2500.0,
            total_amount=2500.0,
            remaining_amount=2500.0,
            status="Pending",
            due_date=date.today() + timedelta(days=15),
        )
        db.session.add(bill)
        db.session.commit()

        yield {
            "society": s,
            "user": res_user,
            "resident": resident,
            "facility": fac,
            "flat": f,
            "bill": bill,
        }

def test_profile_edit_and_save_changes_flow(client, resident_setup):
    """Test Issue 2: Resident edits profile and saves changes successfully without 400."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET profile page
    res_get = client.get("/resident/profile")
    assert res_get.status_code == 200
    assert b"My Profile" in res_get.data
    assert b"Rajesh Test Patel" in res_get.data

    # POST Save changes
    res_post = client.post(
        "/resident/profile",
        data={
            "full_name": "Rajesh Kumar Patel",
            "email": "rajesh.updated@example.com",
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"Your profile has been updated." in res_post.data
    assert b"Rajesh Kumar Patel" in res_post.data

    # Verify DB update
    updated_user = db.session.get(User, user.id)
    assert updated_user.full_name == "Rajesh Kumar Patel"
    assert updated_user.email == "rajesh.updated@example.com"


def test_complaint_creation_flow(client, resident_setup):
    """Test Issue 3: Resident creates a new complaint without 400."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET complaint creation page
    res_get = client.get("/complaints/create")
    assert res_get.status_code == 200
    assert b"Lodge a Complaint" in res_get.data

    # POST create complaint
    res_post = client.post(
        "/complaints/create",
        data={
            "category": "Plumbing",
            "title": "Water leak in bathroom tap",
            "description": "The main bathroom tap is constantly dripping water.",
            "priority": "Medium",
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"created successfully" in res_post.data

    # Verify complaint in database
    c = Complaint.query.filter_by(title="Water leak in bathroom tap").first()
    assert c is not None
    assert c.category == "Plumbing"
    assert c.society_id == user.society_id
    assert c.status in ["Submitted", "Open", "Assigned"]

def test_visitor_pass_creation_flow(client, resident_setup):
    """Test Issue 4: Resident creates a visitor pass without 400."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET invite visitor page
    res_get = client.get("/resident/visitors/invite")
    assert res_get.status_code == 200
    assert b"Invite a Visitor" in res_get.data

    # POST invite visitor
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    res_post = client.post(
        "/resident/visitors/invite",
        data={
            "visitor_name": "Suresh Shah",
            "mobile": "9898989898",
            "expected_date": tomorrow,
            "expected_time": "15:00",
            "purpose": "Guest",
            "notes": "Family guest visiting for dinner",
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"Visitor invitation created" in res_post.data

    # Verify pre-approved pass created
    pass_record = PreApprovedPass.query.filter_by(visitor_name="Suresh Shah").first()
    assert pass_record is not None
    assert pass_record.mobile == "9898989898"
    assert pass_record.society_id == user.society_id
    assert pass_record.pass_code is not None


def test_facility_booking_and_cancel_flow(client, resident_setup):
    """Test Issue 6: Facility booking and cancellation flow."""
    user = resident_setup["user"]
    fac = resident_setup["facility"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET facilities page
    res_get = client.get("/facilities")
    assert res_get.status_code == 200
    assert b"Facility Booking" in res_get.data
    assert b"Clubhouse Hall" in res_get.data

    # POST book facility
    booking_date = (date.today() + timedelta(days=2)).isoformat()
    res_post = client.post(
        "/facilities/book",
        data={
            "facility_id": fac.id,
            "booking_date": booking_date,
            "start_time": "14:00",
            "end_time": "16:00",
            "purpose": "Community Meeting",
            "notes": "Need projector screen",
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"booked successfully" in res_post.data

    # Verify booking in DB
    booking = FacilityBooking.query.filter_by(facility_id=fac.id, start_time="14:00").first()
    assert booking is not None
    assert booking.society_id == user.society_id
    assert booking.status == "Confirmed"

    # POST cancel booking
    res_cancel = client.post(
        f"/facilities/{booking.id}/cancel",
        follow_redirects=True,
    )
    assert res_cancel.status_code == 200
    assert b"cancelled" in res_cancel.data.lower()

def test_support_request_creation_flow(client, resident_setup):
    """Test Issue 7: Resident creates support request without 400."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET new support page
    res_get = client.get("/resident/support/new")
    assert res_get.status_code == 200
    assert b"Create Support Request" in res_get.data

    # POST support request
    res_post = client.post(
        "/resident/support/new",
        data={
            "subject": "Need help with maintenance billing",
            "category": "Billing",
            "message": "I want to understand the late fee calculation on my bill.",
        },
        follow_redirects=True,
    )
    assert res_post.status_code == 200
    assert b"Support request submitted" in res_post.data

    # Verify DB record
    req = SupportRequest.query.filter_by(subject="Need help with maintenance billing").first()
    assert req is not None
    assert req.society_id == user.society_id
    assert req.status == "OPEN"
    assert req.category == "Billing"


def test_ai_assistant_page_and_queries(client, resident_setup):
    """Test Issue 8: AI Assistant available status, query responses and feedback."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # GET AI Assistant page
    res_page = client.get("/resident/ai-assistant")
    assert res_page.status_code == 200
    assert b"AI Society Assistant" in res_page.data
    assert b"Available" in res_page.data

    # Test Query 1: Pending amount
    res_q1 = client.post(
        "/api/v1/resident/ai/query",
        json={"prompt": "What is my pending amount?"},
    )
    assert res_q1.status_code == 200
    data1 = res_q1.get_json()
    assert "pending maintenance amount" in data1.get("response", "").lower() or "pending" in data1.get("response", "").lower()

    # Test Query 2: Next due date
    res_q2 = client.post(
        "/api/v1/resident/ai/query",
        json={"prompt": "When is my next bill due?"},
    )
    assert res_q2.status_code == 200
    data2 = res_q2.get_json()
    assert "due" in data2.get("response", "").lower()

    # Test Query 3: Overdue check
    res_q3 = client.post(
        "/api/v1/resident/ai/query",
        json={"prompt": "Do I have any overdue bills?"},
    )
    assert res_q3.status_code == 200
    data3 = res_q3.get_json()
    assert "overdue" in data3.get("response", "").lower()

    # Test Feedback endpoint
    res_fb = client.post(
        "/api/v1/resident/ai/feedback",
        json={"helpful": True, "idx": 1},
    )
    assert res_fb.status_code == 200
    assert res_fb.get_json().get("success") is True

def test_admin_end_to_end_audit_pages(client, app, resident_setup):
    """Test Admin side pages load cleanly and actions work without 400/500 errors."""
    with app.app_context():
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first()
        admin_id = admin.id
        soc_id = resident_setup["society"].id

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN
        sess["society_id"] = soc_id

    # 1. Admin Dashboard
    r_dash = client.get("/dashboard")
    assert r_dash.status_code == 200

    # 2. Resident Management
    r_res = client.get("/admin/residents")
    assert r_res.status_code == 200

    # 3. Registration requests
    r_reg = client.get("/admin/registrations")
    assert r_reg.status_code == 200

    # 4. Maintenance & Bills
    r_bills = client.get("/payments/bills")
    assert r_bills.status_code == 200

    # 5. Complaints
    r_comp = client.get("/complaints/")
    assert r_comp.status_code == 200

    # 6. Facilities
    r_fac = client.get("/facilities")
    assert r_fac.status_code == 200

    # 7. Admin payment dashboard
    r_pay_dash = client.get("/payments/admin/dashboard")
    assert r_pay_dash.status_code == 200

    # 7. AI Energy, AI Parking, AI Maintenance, AI Invoices
    r_ai_energy = client.get("/admin/ai/energy")
    assert r_ai_energy.status_code == 200

    r_ai_parking = client.get("/admin/ai/parking")
    assert r_ai_parking.status_code == 200

    r_ai_maint = client.get("/admin/ai/maintenance")
    assert r_ai_maint.status_code == 200

    r_ai_inv = client.get("/admin/ai/invoices")
    assert r_ai_inv.status_code == 200

def test_csrf_protection_and_form_templates(client, app, resident_setup):
    """Test that all rendered GET forms contain the csrf_token field and valid token succeeds."""
    user = resident_setup["user"]

    with client.session_transaction() as sess:
        sess["user_id"] = user.id
        sess["role"] = Role.RESIDENT
        sess["society_id"] = user.society_id

    # 1. Profile form has csrf_token
    r_prof = client.get("/resident/profile")
    assert r_prof.status_code == 200
    assert b'name="csrf_token"' in r_prof.data

    # 2. Complaint create form has csrf_token
    r_comp = client.get("/complaints/create")
    assert r_comp.status_code == 200
    assert b'name="csrf_token"' in r_comp.data

    # 3. Invite visitor form has csrf_token
    r_vis = client.get("/resident/visitors/invite")
    assert r_vis.status_code == 200
    assert b'name="csrf_token"' in r_vis.data

    # 4. Facility booking form has csrf_token
    r_fac = client.get("/facilities")
    assert r_fac.status_code == 200
    assert b'name="csrf_token"' in r_fac.data

    # 5. Support request form has csrf_token
    r_sup = client.get("/resident/support/new")
    assert r_sup.status_code == 200
    assert b'name="csrf_token"' in r_sup.data
