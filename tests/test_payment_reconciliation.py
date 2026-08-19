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
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    RefundRequest,
    PaymentReconciliationIssue,
)
from app.services.reconciliation_service import PaymentReconciliationService


@pytest.fixture
def recon_data(app):
    with app.app_context():
        society = Society(
            name="Reconciliation Test Society",
            registration_number="RECON-001",
            address="789 Finance Way",
            city="Surat",
            state="Gujarat",
            pincode="395001",
            email="finance@reconsoc.com",
            phone="9876543212",
        )
        db.session.add(society)
        db.session.commit()

        wing = Building(society_id=society.id, name="Wing A")
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

        user = User(username="reconres", full_name="Recon User", email="res@reconsoc.com", mobile="9876543212", role=Role.RESIDENT, society_id=society.id)
        user.set_password("Resident@123")
        db.session.add(user)
        db.session.commit()

        admin = User(username="reconadmin", full_name="Recon Admin", email="admin@reconsoc.com", mobile="9876543213", role=Role.SOCIETY_ADMIN, society_id=society.id)
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=user.id,
            full_name="Recon Resident",
            mobile="9876543212",
        )
        db.session.add(resident)
        db.session.commit()

        bill = MaintenanceBill(
            bill_number="BILL-RECON-101-2026-08",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-08",
            base_amount=1500.0,
            total_amount=1500.0,
            remaining_amount=1500.0,
            due_date=date(2026, 8, 10),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        return society.id, bill.id, resident.id, admin.id


def test_reconciliation_detects_unpaid_bill_with_payment(app, recon_data):
    society_id, bill_id, resident_id, admin_id = recon_data
    with app.app_context():
        # Insert a captured payment for this bill without marking the bill Paid
        pmt = Payment(
            transaction_id="TXN_RECON_001",
            society_id=society_id,
            bill_id=bill_id,
            resident_id=resident_id,
            amount_paid=1500.0,
            payment_method="UPI",
            provider_name="Razorpay",
            status="captured",
        )
        db.session.add(pmt)
        db.session.commit()

        # Run reconciliation
        res = PaymentReconciliationService.reconcile_all(society_id=society_id)
        assert res["records_scanned"] > 0
        assert res["records_created"] > 0

        # Check that UNPAID_BILL_WITH_PAYMENT issue was registered
        issue = PaymentReconciliationIssue.query.filter_by(
            society_id=society_id,
            issue_type="UNPAID_BILL_WITH_PAYMENT",
            status="OPEN",
        ).first()
        assert issue is not None
        assert issue.severity == "CRITICAL"
        assert issue.bill_id == bill_id
        assert issue.payment_id == pmt.id

        # Now resolve the issue
        admin = db.session.get(User, admin_id)
        resolve_res = PaymentReconciliationService.resolve_issue(issue.id, admin, "Resolved test anomaly")
        assert resolve_res["success"] is True

        # Verify bill is now marked Paid
        bill = db.session.get(MaintenanceBill, bill_id)
        assert bill.status == "Paid"
        assert bill.remaining_amount == 0.0
        assert issue.status == "RESOLVED"


def test_reconciliation_net_collection_summary(app, recon_data):
    society_id, bill_id, resident_id, _ = recon_data
    with app.app_context():
        pmt = Payment(
            transaction_id="TXN_NET_001",
            society_id=society_id,
            bill_id=bill_id,
            resident_id=resident_id,
            amount_paid=2000.0,
            payment_method="UPI",
            provider_name="Razorpay",
            status="captured",
        )
        db.session.add(pmt)
        db.session.commit()

        # Add refund of 500
        refund = RefundRequest(
            payment_id=pmt.id,
            society_id=society_id,
            resident_id=resident_id,
            requested_amount=500.0,
            refunded_amount=500.0,
            reason="Overpayment",
            status="processed",
        )
        db.session.add(refund)
        db.session.commit()

        summary = PaymentReconciliationService.get_net_collection_summary(society_id=society_id)
        assert summary["lifetime_gross"] >= 2000.0
        assert summary["total_refunds"] >= 500.0
        assert summary["lifetime_collection"] == summary["lifetime_gross"] - summary["total_refunds"]
