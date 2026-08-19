import pytest
from datetime import date
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    Resident,
    User,
    Role,
)
from app.services.property_lifecycle_service import PropertyLifecycleService


@pytest.fixture
def prop_society(app):
    with app.app_context():
        society = Society(
            name="Lifecycle Property Society",
            registration_number="LIFECYCLE-001",
            address="456 Residency Blvd",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            email="info@lifeproperty.com",
            phone="9876543211",
        )
        db.session.add(society)
        db.session.commit()

        wing = Building(society_id=society.id, name="Wing B")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=society.id, building_id=wing.id, name="B")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=society.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="202",
            occupancy_status="Vacant",
        )
        db.session.add(flat)
        db.session.commit()

        admin = User(
            username="propadmin",
            full_name="Property Admin",
            email="admin@lifeproperty.com",
            mobile="9876543211",
            role=Role.SOCIETY_ADMIN,
            society_id=society.id,
            account_status="ACTIVE",
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()

        return society.id, flat.id, admin.id


def test_property_key_normalization():
    # Test whitespace, case, and hyphen variations
    assert PropertyLifecycleService.normalize_property_key("B", "202") == "B-202"
    assert PropertyLifecycleService.normalize_property_key("b", " 202 ") == "B-202"
    assert PropertyLifecycleService.normalize_property_key("B 202", None) == "B-202"
    assert PropertyLifecycleService.normalize_property_key("b-202", None) == "B-202"
    assert PropertyLifecycleService.normalize_property_key(" b - 202 ", None) == "B-202"
    assert PropertyLifecycleService.normalize_property_key("Wing B", "202") == "WING B-202"


def test_property_lifecycle_sequential_occupants(app, prop_society):
    society_id, flat_id, admin_id = prop_society
    with app.app_context():
        admin = db.session.get(User, admin_id)
        flat = db.session.get(Flat, flat_id)

        # 1. Resident A moves in
        user_a = User(username="user_a", full_name="Alice User", email="a@res.com", mobile="9800000001", role=Role.RESIDENT, society_id=society_id)
        user_a.set_password("Resident@123")
        db.session.add(user_a)
        db.session.commit()

        res_a = Resident(
            society_id=society_id,
            flat_id=flat.id,
            user_id=user_a.id,
            full_name="Resident Alice",
            mobile="9800000001",
            resident_type="Owner",
        )
        db.session.add(res_a)
        db.session.commit()

        occ_a = PropertyLifecycleService.record_move_in(
            society_id=society_id,
            flat_id=flat.id,
            resident_id=res_a.id,
            user_id=user_a.id,
            move_in_date=date(2026, 1, 1),
            admin_user=admin,
        )
        assert flat.occupancy_status == "Occupied"
        assert res_a.occupancy_status == "Active"
        assert occ_a.occupancy_status == "Active"

        # 2. Resident A moves out
        PropertyLifecycleService.record_move_out(
            resident_id=res_a.id,
            move_out_date=date(2026, 6, 30),
            reason="Relocated for job",
            admin_user=admin,
        )
        assert flat.occupancy_status == "Vacant"
        assert res_a.occupancy_status == "Moved Out"
        assert occ_a.occupancy_status == "Moved Out"
        assert occ_a.move_out_date == date(2026, 6, 30)

        # 3. Resident B moves in (New independent occupant without mixing A's records)
        user_b = User(username="user_b", full_name="Bob User", email="b@res.com", mobile="9800000002", role=Role.RESIDENT, society_id=society_id)
        user_b.set_password("Resident@123")
        db.session.add(user_b)
        db.session.commit()

        res_b = Resident(
            society_id=society_id,
            flat_id=flat.id,
            user_id=user_b.id,
            full_name="Resident Bob",
            mobile="9800000002",
            resident_type="Tenant",
        )
        db.session.add(res_b)
        db.session.commit()

        occ_b = PropertyLifecycleService.record_move_in(
            society_id=society_id,
            flat_id=flat.id,
            resident_id=res_b.id,
            user_id=user_b.id,
            resident_type="Tenant",
            move_in_date=date(2026, 7, 1),
            admin_user=admin,
        )
        assert occ_b is not None
        assert flat.occupancy_status == "Occupied"
        assert res_b.occupancy_status == "Active"
        assert res_b.advance_balance == 0.0

        # Verify historical isolation
        history = PropertyLifecycleService.get_property_occupancy_history(flat.id)
        assert len(history) == 2
        assert history[0].resident_id == res_b.id  # Most recent
        assert history[1].resident_id == res_a.id  # Prior occupant
