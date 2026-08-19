import pytest
from app import create_app
from app.models import db, User, Society, Resident, Building, Flat, MaintenanceBill, Notice


@pytest.fixture
def app():
    app = create_app("testing")
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    with app.app_context():
        db.create_all()
        society = Society(
            name="Search Test Society",
            registration_number="REG-SEARCH-999",
            address="123 Main St",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380001",
            email="society999@example.com",
            phone="9876543219"
        )
        db.session.add(society)
        db.session.commit()

        # Admin user
        admin_user = User(
            full_name="Admin Test User",
            mobile="9990000000",
            role="Society Admin",
            society_id=society.id,
            account_status="ACTIVE"
        )
        admin_user.set_password("Admin@1234")

        # Resident 1
        r1_user = User(
            full_name="Rahul Test Patel",
            mobile="9990000001",
            role="Resident",
            society_id=society.id,
            account_status="ACTIVE"
        )
        r1_user.set_password("Resident@123")

        # Resident 2
        r2_user = User(
            full_name="Suresh Test Sharma",
            mobile="9990000002",
            role="Resident",
            society_id=society.id,
            account_status="ACTIVE"
        )
        r2_user.set_password("Resident@123")

        db.session.add_all([admin_user, r1_user, r2_user])
        db.session.commit()

        bld = Building(society_id=society.id, name="Wing Z")
        db.session.add(bld)
        db.session.commit()

        f1 = Flat(society_id=society.id, building_id=bld.id, flat_number="901", floor_number=9)
        f2 = Flat(society_id=society.id, building_id=bld.id, flat_number="902", floor_number=9)
        db.session.add_all([f1, f2])
        db.session.commit()

        res1 = Resident(society_id=society.id, user_id=r1_user.id, flat_id=f1.id, full_name="Rahul Test Patel", mobile="9990000001", resident_type="Owner")
        res2 = Resident(society_id=society.id, user_id=r2_user.id, flat_id=f2.id, full_name="Suresh Test Sharma", mobile="9990000002", resident_type="Owner")
        db.session.add_all([res1, res2])
        db.session.commit()

        from app.utils import utcnow
        now = utcnow()
        b1 = MaintenanceBill(society_id=society.id, resident_id=res1.id, flat_id=f1.id, bill_number="BILL-TEST-101", billing_month="2026-08", base_amount=1500.0, total_amount=1500.0, amount_paid=0.0, remaining_amount=1500.0, due_date=now, status="Pending")
        b2 = MaintenanceBill(society_id=society.id, resident_id=res2.id, flat_id=f2.id, bill_number="BILL-TEST-102", billing_month="2026-08", base_amount=1500.0, total_amount=1500.0, amount_paid=0.0, remaining_amount=1500.0, due_date=now, status="Pending")
        db.session.add_all([b1, b2])

        n1 = Notice(society_id=society.id, title="Water Supply Maintenance Notice", content="Water will be shut off tomorrow", notice_type="Water")
        db.session.add(n1)
        db.session.commit()

        yield app

        db.session.remove()
        db.drop_all()


def test_admin_search_returns_society_records(app):
    with app.app_context():
        from app.services.search_service import SearchService
        admin_user = User.query.filter_by(mobile="9990000000").first()
        res = SearchService.global_search(admin_user, admin_user.society_id, "BILL-TEST")

        assert len(res["categories"]) > 0
        bill_cat = next((c for c in res["categories"] if c["key"] == "category_bills"), None)
        assert bill_cat is not None
        assert any("BILL-TEST-101" in item["title"] for item in bill_cat["items"])


def test_resident_cannot_search_other_residents(app):
    with app.app_context():
        from app.services.search_service import SearchService
        r1_user = User.query.filter_by(mobile="9990000001").first()

        # Resident 1 searches for Resident 2's name "Suresh Test"
        res = SearchService.global_search(r1_user, r1_user.society_id, "Suresh Test")

        # Must NOT return any residents category or Suresh's private information
        resident_cat = next((c for c in res["categories"] if c["key"] == "category_residents"), None)
        assert resident_cat is None


def test_resident_search_own_bills_and_public_notices(app):
    with app.app_context():
        from app.services.search_service import SearchService
        r1_user = User.query.filter_by(mobile="9990000001").first()

        # Resident 1 searches for "BILL-TEST-101" (own bill)
        res_own = SearchService.global_search(r1_user, r1_user.society_id, "BILL-TEST-101")
        bill_cat = next((c for c in res_own["categories"] if c["key"] == "category_bills"), None)
        assert bill_cat is not None
        assert any("BILL-TEST-101" in item["title"] for item in bill_cat["items"])

        # Resident 1 searches for "BILL-TEST-102" (Resident 2's bill)
        res_other = SearchService.global_search(r1_user, r1_user.society_id, "BILL-TEST-102")
        other_bill_cat = next((c for c in res_other["categories"] if c["key"] == "category_bills"), None)
        assert other_bill_cat is None

        # Resident 1 searches for "Water" (public notice)
        res_notice = SearchService.global_search(r1_user, r1_user.society_id, "Water")
        notice_cat = next((c for c in res_notice["categories"] if c["key"] == "category_notices"), None)
        assert notice_cat is not None
