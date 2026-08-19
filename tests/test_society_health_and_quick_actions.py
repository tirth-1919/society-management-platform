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
    BackupLog,
)
from app.services.society_health_service import SocietyHealthService


@pytest.fixture
def health_society(app):
    with app.app_context():
        society = Society(
            name="Health Audit Society",
            registration_number="HEALTH-001",
            address="100 Wellness Avenue",
            city="Vadodara",
            state="Gujarat",
            pincode="390001",
            email="health@society.com",
            phone="9876543214",
        )
        db.session.add(society)
        db.session.commit()

        wing = Building(society_id=society.id, name="Wing H")
        db.session.add(wing)
        db.session.commit()

        flat = Flat(
            society_id=society.id,
            building_id=wing.id,
            flat_number="101",
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        user = User(username="healthres", full_name="Health User", email="res@health.com", mobile="9876543214", role=Role.RESIDENT, society_id=society.id)
        user.set_password("Resident@123")
        db.session.add(user)
        db.session.commit()

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name="Health Resident",
            mobile="9876543214",
        )
        db.session.add(resident)
        db.session.commit()

        # Add a paid bill and backup log
        bill = MaintenanceBill(
            bill_number="BILL-HEALTH-101-2026-08",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-08",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=1500.0,
            remaining_amount=0.0,
            due_date=date(2026, 8, 10),
            status="Paid",
        )
        db.session.add(bill)

        backup = BackupLog(
            filename="health_backup.sql",
            file_path="/backups/health_backup.sql",
            backup_type="Scheduled",
            status="Completed",
        )
        db.session.add(backup)
        db.session.commit()

        return society.id


def test_society_health_score_calculation(app, health_society):
    society_id = health_society
    with app.app_context():
        health = SocietyHealthService.calculate_society_health(society_id=society_id)
        assert "score" in health
        assert 0 <= health["score"] <= 100
        assert health["tier"] in ["EXCELLENT", "HEALTHY", "NEEDS_ATTENTION", "CRITICAL"]
        assert len(health["pillars"]) == 10
        assert "collection_performance" in health["pillars"]
        assert "reconciliation_health" in health["pillars"]


def test_admin_daily_brief(app, health_society):
    society_id = health_society
    with app.app_context():
        brief = SocietyHealthService.get_admin_daily_brief(society_id=society_id)
        assert "active_residents" in brief
        assert "society_health" in brief
        assert "action_required" in brief
        assert brief["active_residents"] == 1
