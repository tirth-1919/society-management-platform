import pytest
from datetime import date
from app.models import (
    db,
    Society,
    Building,
    Flat,
    Resident,
    User,
    Role,
    MaintenanceBill,
)
from app.services.ai_service import AIService


@pytest.fixture
def ai_test_data(app):
    with app.app_context():
        # Society 1
        soc1 = Society(
            name="AI Privacy Society 1",
            registration_number="AI-PRIV-001",
            address="111 AI Road",
            city="Rajkot",
            state="Gujarat",
            pincode="360001",
            email="soc1@ai.com",
            phone="9876543215",
        )
        # Society 2
        soc2 = Society(
            name="AI Privacy Society 2",
            registration_number="AI-PRIV-002",
            address="222 AI Road",
            city="Rajkot",
            state="Gujarat",
            pincode="360002",
            email="soc2@ai.com",
            phone="9876543216",
        )
        db.session.add_all([soc1, soc2])
        db.session.commit()

        wing1 = Building(society_id=soc1.id, name="Wing A")
        db.session.add(wing1)
        db.session.commit()

        flat1 = Flat(society_id=soc1.id, building_id=wing1.id, flat_number="101")
        db.session.add(flat1)
        db.session.commit()

        user1 = User(username="aires1", full_name="Alice AI User", email="res1@ai.com", mobile="9876543215", role=Role.RESIDENT, society_id=soc1.id)
        user1.set_password("Resident@123")
        db.session.add(user1)
        db.session.commit()

        res1 = Resident(society_id=soc1.id, flat_id=flat1.id, user_id=user1.id, full_name="Alice AI", mobile="9876543215")
        db.session.add(res1)
        db.session.commit()

        # Bill due
        bill = MaintenanceBill(
            bill_number="BILL-AI-101-2026-08",
            society_id=soc1.id,
            flat_id=flat1.id,
            resident_id=res1.id,
            billing_month="2026-08",
            base_amount=1500.0,
            total_amount=1500.0,
            remaining_amount=1500.0,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        return soc1.id, soc2.id, user1.id, res1.id


def test_ai_resident_insights(app, ai_test_data):
    soc1_id, _, _, res1_id = ai_test_data
    with app.app_context():
        insights = AIService.get_resident_payment_insights(resident_id=res1_id, society_id=soc1_id)
        assert insights["total_due"] == 1500.0
        assert insights["unpaid_count"] == 1
        assert "late_payment_risk_score" in insights
        assert len(insights["recommendations"]) > 0


def test_ai_complaint_classification():
    # Electrical
    res_elec = AIService.classify_complaint("Sparking socket", "The main power switch in the kitchen is sparking.")
    assert res_elec["category"] == "Electrical"
    assert res_elec["priority"] == "High"

    # Plumbing
    res_plumb = AIService.classify_complaint("Water leakage", "The pipe under the sink has a severe water leak.")
    assert res_plumb["category"] == "Plumbing"
    assert res_plumb["priority"] == "High"

    # Elevator
    res_lift = AIService.classify_complaint("Lift stuck", "Elevator in Wing B is stopped on floor 3.")
    assert res_lift["category"] == "Elevator"
    assert res_lift["priority"] == "Emergency"


def test_ai_resident_isolation(app, ai_test_data):
    soc1_id, soc2_id, user1_id, res1_id = ai_test_data
    with app.app_context():
        # Querying with wrong society_id returns error/isolation block
        summary = AIService.get_resident_daily_summary(resident_id=res1_id, society_id=soc2_id)
        assert "error" in summary
