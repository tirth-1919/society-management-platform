from datetime import date
import pytest
from app.models import (
    db,
    Society,
    User,
    Role,
    Resident,
    Building,
    Flat,
    Facility,
    ParkingSlot,
    Asset,
    Vendor,
)
from app.services.accounting_service import AccountingService
from app.services.visitor_service import VisitorService
from app.services.complaint_service import ComplaintService
from app.services.facility_booking_service import FacilityBookingService
from app.utils import utcnow


def setup_module_fixtures(mobile_suffix):
    society = Society.query.first()
    building = society.buildings[0] if society.buildings else Building(society_id=society.id, name="Tower A")
    if not society.buildings:
        db.session.add(building)
        db.session.flush()

    flat = Flat(
        society_id=society.id,
        building_id=building.id,
        flat_number=f"MOD-{mobile_suffix}",
        floor=2,
    )
    db.session.add(flat)
    db.session.flush()

    user = User(
        full_name=f"Module Resident {mobile_suffix}",
        mobile=f"960000{mobile_suffix}",
        society_id=society.id,
        role=Role.RESIDENT,
        account_status="ACTIVE",
        is_active=True,
    )
    user.set_password("Pass@123")
    db.session.add(user)
    db.session.flush()

    resident = Resident(
        society_id=society.id,
        flat_id=flat.id,
        user_id=user.id,
        full_name=user.full_name,
        mobile=user.mobile,
        resident_type="Owner",
        occupancy_status="Active",
        is_primary=True,
    )
    db.session.add(resident)
    db.session.commit()
    return society, flat, user, resident


def test_accounting_service_vouchers_and_cashbook(app):
    with app.app_context():
        society, flat, user, resident = setup_module_fixtures("0001")

        # Record Income entry
        income_entry = AccountingService.record_income_entry(
            society_id=society.id,
            amount=5000.0,
            account_head="Maintenance Collection",
            narration="Test maintenance collection",
        )
        assert income_entry.entry_type == "CREDIT"
        assert income_entry.amount == 5000.0

        # Create Expense Voucher
        v = AccountingService.create_expense_voucher(
            society_id=society.id,
            category="Electricity",
            amount=1200.0,
            payee_name="Power Grid Corp",
            description="Monthly Common Area Electricity",
            invoice_number="INV-ELEC-01",
        )
        assert v.voucher_number.startswith(f"VCHR-{society.id}-")
        assert v.amount == 1200.0
        assert v.status == "Approved"

        # Check financial summary
        summary = AccountingService.get_financial_summary(society.id)
        assert summary["total_income"] >= 5000.0
        assert summary["total_expense"] >= 1200.0
        assert summary["net_surplus"] == round(summary["total_income"] - summary["total_expense"], 2)

        # Check cashbook
        cashbook = AccountingService.get_cashbook(society.id)
        assert len(cashbook) >= 2


def test_visitor_management_workflow(app):
    with app.app_context():
        society, flat, user, resident = setup_module_fixtures("0002")

        # Resident creates pre-approved pass
        p = VisitorService.create_pre_approved_pass(
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            visitor_name="Guest Alice",
            mobile="9898989898",
            expected_date=utcnow().date(),
            purpose="Dinner Guest",
        )
        assert p.pass_code is not None
        assert p.is_used is False

        # Gate guard verifies and checks in
        ok, msg, visitor = VisitorService.verify_and_checkin_pass(p.pass_code, society.id)
        assert ok is True
        assert visitor is not None
        assert visitor.visitor_name == "Guest Alice"
        assert visitor.flat_id == flat.id

        # Pass status should now be used
        assert p.is_used is True

        # Log visitor exit
        exited = VisitorService.log_visitor_exit(visitor.id)
        assert exited.exit_time is not None


def test_complaint_lifecycle_sla_and_reopen(app):
    with app.app_context():
        society, flat, user, resident = setup_module_fixtures("0003")

        # Create complaint
        c = ComplaintService.create_complaint(
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            category="Plumbing",
            title="Leaking Kitchen Tap",
            description="Water is dripping continuously in flat kitchen sink.",
            priority="High",
        )
        assert c.status == "Submitted"
        assert c.ticket_number.startswith(f"TICK-{society.id}-")

        # Assign staff
        admin_user = User.query.filter_by(society_id=society.id, role=Role.SOCIETY_ADMIN).first() or user
        c = ComplaintService.assign_staff(c.id, admin_user.id)
        assert c.status == "Assigned"
        assert c.assigned_staff_id == admin_user.id

        # Update status to In Progress
        c = ComplaintService.update_status(c.id, "In Progress")
        assert c.status == "In Progress"

        # Add comment
        comment = ComplaintService.add_comment(c.id, user.id, "Plumber visited and inspected parts.")
        assert comment.comment == "Plumber visited and inspected parts."
        assert len(c.comments) >= 1

        # Resolve complaint
        c = ComplaintService.update_status(c.id, "Resolved", resolution_notes="Replaced pipe washer.")
        assert c.status == "Resolved"
        assert c.resolved_at is not None
        assert c.resolution_notes == "Replaced pipe washer."

        # Reopen complaint
        c = ComplaintService.reopen_complaint(c.id, user.id, "Dripping started again after 2 hours.")
        assert c.status == "In Progress"
        assert c.resolved_at is None


def test_facility_booking_and_double_booking_conflict_prevention(app):
    with app.app_context():
        society, flat, user, resident = setup_module_fixtures("0004")

        fac = Facility(
            society_id=society.id,
            name=f"Banquet Hall {user.id}",
            capacity=100,
            is_active=True,
        )
        db.session.add(fac)
        db.session.flush()

        booking_date = date(2026, 11, 15)

        # First booking: 14:00 - 18:00
        b1 = FacilityBookingService.book_facility(
            society_id=society.id,
            facility_id=fac.id,
            flat_id=flat.id,
            resident_id=resident.id,
            booking_date=booking_date,
            start_time="14:00",
            end_time="18:00",
            purpose="Birthday Party",
        )
        assert b1.status == "Confirmed"

        # Attempt overlapping booking on same facility and date: 16:00 - 20:00 -> MUST RAISE ValueError
        with pytest.raises(ValueError) as exc:
            FacilityBookingService.book_facility(
                society_id=society.id,
                facility_id=fac.id,
                flat_id=flat.id,
                resident_id=resident.id,
                booking_date=booking_date,
                start_time="16:00",
                end_time="20:00",
                purpose="Another Event",
            )
        assert "overlap" in str(exc.value).lower() or "conflict" in str(exc.value).lower() or "already booked" in str(exc.value).lower()


def test_parking_allocation_and_assets(app):
    with app.app_context():
        society, flat, user, resident = setup_module_fixtures("0005")

        # Create Parking Slot
        slot = ParkingSlot(
            society_id=society.id,
            slot_number=f"P-{user.id}",
            slot_type="Covered 4-Wheeler",
            status="Available",
        )
        db.session.add(slot)
        db.session.flush()

        # Allocate slot to flat
        slot.allocated_flat_id = flat.id
        slot.status = "Allocated"
        db.session.commit()

        assert slot.allocated_flat_id == flat.id
        assert slot.status == "Allocated"

        # Create Vendor and Asset
        v = Vendor(
            society_id=society.id,
            company_name=f"Elevator Care {user.id}",
            contact_person="Rajesh Kumar",
            phone="9876543210",
            category="Lift AMC",
            contract_amount=50000.0,
            status="Active",
        )
        db.session.add(v)
        db.session.flush()

        asset = Asset(
            society_id=society.id,
            asset_name=f"Passenger Lift {user.id}",
            category="Lift",
            location="Wing A",
            purchase_cost=1500000.0,
            vendor_id=v.id,
            status="Operational",
        )
        db.session.add(asset)
        db.session.commit()

        assert asset.vendor_id == v.id
        assert asset.status == "Operational"
