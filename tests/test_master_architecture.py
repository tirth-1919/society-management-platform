import pytest
from app import create_app
from app.models import (
    db, Society, Building, Block, Flat, Resident, User, Role,
    RegistrationRequest, MaintenanceBill, Payment, PaymentReceipt,
    AccountLedger, AuditLog
)
from app.services.registration_service import (
    RegistrationService, normalize_flat_number, normalize_building_name,
    build_property_key, check_flat_availability
)
from app.services.payment_service import PaymentService
from app.services.billing_service import BillingService
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def test_app():
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def setup_society(test_app):
    society = Society(
        name="Shanti Heights",
        registration_number="SOC/MH/2026/001",
        address="Sector 10, Nerul",
        city="Navi Mumbai",
        state="Maharashtra",
        pincode="400706",
        email="society@shanti.com",
        phone="9876543210",
    )
    db.session.add(society)
    db.session.flush()

    wing_a = Building(society_id=society.id, name="Wing A")
    wing_b = Building(society_id=society.id, name="Wing B")
    db.session.add_all([wing_a, wing_b])
    db.session.flush()

    flat_a_101 = Flat(society_id=society.id, building_id=wing_a.id, flat_number="101", occupancy_status="Available")
    flat_b_202 = Flat(society_id=society.id, building_id=wing_b.id, flat_number="202", occupancy_status="Available")
    flat_b_203 = Flat(society_id=society.id, building_id=wing_b.id, flat_number="203", occupancy_status="Available")
    db.session.add_all([flat_a_101, flat_b_202, flat_b_203])

    admin = User(
        full_name="Society Secretary",
        mobile="9900112233",
        role=Role.SOCIETY_ADMIN,
        society_id=society.id,
        account_status="ACTIVE",
    )
    admin.set_password("Admin@123")
    db.session.add(admin)
    db.session.commit()

    return {
        "society": society,
        "wing_a": wing_a,
        "wing_b": wing_b,
        "flat_a_101": flat_a_101,
        "flat_b_202": flat_b_202,
        "flat_b_203": flat_b_203,
        "admin": admin,
    }


def test_01_normalization_helpers():
    """Verify normalize_flat_number, normalize_building_name, and build_property_key."""
    assert normalize_flat_number(" 202 ") == "202"
    assert normalize_flat_number("b-202") == "B-202"
    assert normalize_building_name(" wing b ") == "WING B"
    assert build_property_key("Wing B", "202") == "WING B-202"
    assert build_property_key("B", " 202 ") == "B-202"


def test_02_database_unique_flat_constraint(setup_society):
    """Database must strictly prevent duplicate flats within the same building/society."""
    data = setup_society
    # Trying to insert another flat '202' into wing_b must raise an IntegrityError
    duplicate_flat = Flat(
        society_id=data["society"].id,
        building_id=data["wing_b"].id,
        flat_number="202",
        occupancy_status="Available"
    )
    db.session.add(duplicate_flat)
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_03_property_key_computed_property(setup_society):
    """Flat ORM object computes human readable property_key."""
    data = setup_society
    assert data["flat_b_202"].property_key == "WING B-202"
    assert data["flat_a_101"].property_key == "WING A-101"


def test_04_new_user_registration_and_duplicate_prevention(setup_society):
    """Registering a new resident for B-202 succeeds, subsequent registration for same flat fails."""
    data = setup_society
    soc = data["society"]
    wing_b = data["wing_b"]
    flat_b202 = data["flat_b_202"]

    # 1. First registration succeeds
    req1 = RegistrationService.register_resident(
        full_name="Pooja Sharma",
        mobile="9820011111",
        email="pooja@test.com",
        society_id=soc.id,
        building_id=wing_b.id,
        flat_id=flat_b202.id,
        occupancy_type="OWNER",
        password="Password@123"
    )
    assert req1.status == "PENDING_APPROVAL"
    assert req1.user.account_status == "PENDING_APPROVAL"

    # 2. Check flat availability now returns False (since pending request exists)
    avail, occupant = check_flat_availability(soc.id, flat_b202.id)
    assert avail is False

    # 3. Approve first resident
    RegistrationService.approve_request(req1.id, data["admin"])
    resident1 = Resident.query.filter_by(flat_id=flat_b202.id, is_primary=True).first()
    assert resident1 is not None
    assert resident1.occupancy_status == "Active"
    assert flat_b202.occupancy_status == "Occupied"

    # 4. Attempt second registration on occupied flat -> rejected
    with pytest.raises(ValueError) as exc:
        RegistrationService.register_resident(
            full_name="Duplicate Applicant",
            mobile="9820022222",
            email="dup@test.com",
            society_id=soc.id,
            building_id=wing_b.id,
            flat_id=flat_b202.id,
            occupancy_type="TENANT",
            password="Password@123"
        )
    assert "already registered" in str(exc.value)


def test_05_admin_approval_atomicity_and_billing_creation(setup_society):
    """Admin approval creates resident, marks flat occupied, creates bill, and logs audit."""
    data = setup_society
    soc = data["society"]
    wing_a = data["wing_a"]
    flat_a101 = data["flat_a_101"]

    req = RegistrationService.register_resident(
        full_name="Amit Verma",
        mobile="9820033333",
        email="amit@test.com",
        society_id=soc.id,
        building_id=wing_a.id,
        flat_id=flat_a101.id,
        occupancy_type="OWNER",
        password="Password@123"
    )

    RegistrationService.approve_request(req.id, data["admin"])

    # Verify Resident created
    res = Resident.query.filter_by(flat_id=flat_a101.id, is_primary=True).first()
    assert res is not None
    assert res.full_name == "Amit Verma"
    assert res.occupancy_status == "Active"

    # Verify initial bill generated
    bill = MaintenanceBill.query.filter_by(resident_id=res.id).first()
    assert bill is not None
    assert bill.base_amount == 1500.0
    assert bill.status == "Pending"
    assert bill.remaining_amount == 1500.0

    # Verify Audit log
    audit = AuditLog.query.filter_by(action="RESIDENT_REGISTRATION_APPROVED").first()
    assert audit is not None
    assert "Amit Verma" in audit.details


def test_06_payment_flow_ledger_sync_and_receipt(setup_society):
    """Verified payment updates bill, credits accounting ledger, creates receipt, and increases collection."""
    data = setup_society
    soc = data["society"]
    wing_b = data["wing_b"]
    flat_b203 = data["flat_b_203"]

    req = RegistrationService.register_resident(
        full_name="Vikram Mehta",
        mobile="9820044444",
        email="vikram@test.com",
        society_id=soc.id,
        building_id=wing_b.id,
        flat_id=flat_b203.id,
        occupancy_type="OWNER",
        password="Password@123"
    )
    RegistrationService.approve_request(req.id, data["admin"])
    res = Resident.query.filter_by(flat_id=flat_b203.id, is_primary=True).first()
    bill = MaintenanceBill.query.filter_by(resident_id=res.id).first()

    # Initial collection
    summary_before = PaymentService.get_collection_summary(soc.id)
    initial_collection = summary_before["lifetime_collection"]

    # Process successful payment
    payment = PaymentService.process_successful_payment(
        bill_id=bill.id,
        society_id=soc.id,
        resident_id=res.id,
        amount_paid=1500.0,
        transaction_id="TXN-TEST-123456",
        payment_method="UPI",
        provider_name="Mock",
    )

    # 1. Bill marked Paid
    db.session.refresh(bill)
    assert bill.status == "Paid"
    assert bill.remaining_amount == 0.0
    assert bill.amount_paid == 1500.0

    # 2. Receipt generated
    assert payment.receipt is not None
    assert payment.receipt.receipt_number.startswith(f"RCPT-{soc.id}")

    # 3. Ledger updated with CREDIT entry
    ledger_entry = AccountLedger.query.filter_by(
        society_id=soc.id,
        reference_id=payment.id,
        entry_type="CREDIT"
    ).first()
    assert ledger_entry is not None
    assert ledger_entry.amount == 1500.0

    # 4. Collection summary automatically increased
    summary_after = PaymentService.get_collection_summary(soc.id)
    assert summary_after["lifetime_collection"] == initial_collection + 1500.0
    assert summary_after["today_collection"] == 1500.0
    assert summary_after["paid_residents"] == 1


def test_07_payment_idempotency_prevents_duplicate_collection(setup_society):
    """Processing payment with identical idempotency_key must be idempotent."""
    data = setup_society
    soc = data["society"]
    wing_b = data["wing_b"]
    flat_b203 = data["flat_b_203"]

    req = RegistrationService.register_resident(
        full_name="Karan Johar",
        mobile="9820055555",
        email="karan@test.com",
        society_id=soc.id,
        building_id=wing_b.id,
        flat_id=flat_b203.id,
        occupancy_type="OWNER",
        password="Password@123"
    )
    RegistrationService.approve_request(req.id, data["admin"])
    res = Resident.query.filter_by(flat_id=flat_b203.id, is_primary=True).first()
    bill = MaintenanceBill.query.filter_by(resident_id=res.id).first()

    idem_key = "IDEMPOTENT-TEST-KEY-999"
    # First execution
    pay1 = PaymentService.process_successful_payment(
        bill_id=bill.id,
        society_id=soc.id,
        resident_id=res.id,
        amount_paid=1500.0,
        transaction_id="TXN-IDEM-001",
        idempotency_key=idem_key
    )

    # Second execution with same idempotency key
    pay2 = PaymentService.process_successful_payment(
        bill_id=bill.id,
        society_id=soc.id,
        resident_id=res.id,
        amount_paid=1500.0,
        transaction_id="TXN-IDEM-002",
        idempotency_key=idem_key
    )

    assert pay1.id == pay2.id
    # Only 1 payment record exists for this idempotency key
    assert Payment.query.filter_by(idempotency_key=idem_key).count() == 1
