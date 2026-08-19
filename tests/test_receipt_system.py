import os
from pathlib import Path
import pytest
from flask import current_app
from app.models import db, User, Resident, Role, Society, Flat, MaintenanceBill, Payment, PaymentReceipt
from app.services.receipt_service import ReceiptService
from app.utils import utcnow


@pytest.fixture
def test_data(app):
    with app.app_context():
        society = Society.query.first()
        flat = Flat.query.filter_by(society_id=society.id).first()

        res_user = User(
            username="res1",
            full_name="Resident One",
            mobile="9876543210",
            email="res1@test.com",
            role=Role.RESIDENT,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("Pass@123")
        db.session.add(res_user)
        db.session.commit()

        resident = Resident(
            user_id=res_user.id,
            society_id=society.id,
            flat_id=flat.id,
            full_name="Resident One",
            email="res1@test.com",
            mobile="9876543210",
            is_primary=True,
            occupancy_status="OCCUPIED",
        )
        db.session.add(resident)
        db.session.commit()

        bill = MaintenanceBill(
            bill_number="BILL-TEST-101",
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            billing_month="2026-03",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=1500.0,
            remaining_amount=0.0,
            due_date=utcnow().date(),
            status="Paid",
        )
        db.session.add(bill)
        db.session.commit()

        payment = Payment(
            transaction_id="TXN-TEST-999",
            society_id=society.id,
            bill_id=bill.id,
            resident_id=resident.id,
            amount_paid=1500.0,
            payment_method="UPI",
            provider_name="Mock",
            provider_order_id="order_mock_123",
            provider_payment_id="pay_mock_123",
            status="captured",
            payment_date=utcnow(),
        )
        db.session.add(payment)
        db.session.commit()

        return {
            "society_id": society.id,
            "user_id": res_user.id,
            "resident_id": resident.id,
            "bill_id": bill.id,
            "payment_id": payment.id,
        }


def test_receipt_generation_no_existing_receipt(app, test_data):
    """TEST 1: Successful payment + no receipt row -> Receipt row created and PDF generated."""
    with app.app_context():
        payment_id = test_data["payment_id"]
        payment = db.session.get(Payment, payment_id)
        assert payment.receipt is None

        pdf_path = ReceiptService.generate_pdf_receipt(payment_id)
        assert pdf_path is not None
        assert os.path.exists(pdf_path)
        assert os.path.getsize(pdf_path) > 0

        # Verify receipt row in DB
        receipt = PaymentReceipt.query.filter_by(payment_id=payment_id).first()
        assert receipt is not None
        assert receipt.receipt_number.startswith("RCPT-")
        assert os.path.abspath(receipt.file_path) == os.path.abspath(pdf_path)


def test_receipt_missing_pdf_regeneration(app, test_data):
    """TEST 2: Successful payment + receipt row + missing PDF -> Same receipt number reused and PDF regenerated."""
    with app.app_context():
        payment_id = test_data["payment_id"]
        pdf_path = ReceiptService.generate_pdf_receipt(payment_id)

        receipt = PaymentReceipt.query.filter_by(payment_id=payment_id).first()
        rcpt_num = receipt.receipt_number

        # Delete the generated PDF file
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        assert not os.path.exists(pdf_path)

        # Re-run generate_pdf_receipt
        new_pdf_path = ReceiptService.generate_pdf_receipt(payment_id)
        assert os.path.exists(new_pdf_path)
        assert os.path.getsize(new_pdf_path) > 0

        # Same receipt number reused
        new_receipt = PaymentReceipt.query.filter_by(payment_id=payment_id).first()
        assert new_receipt.receipt_number == rcpt_num


def test_receipt_valid_pdf_no_duplicate(app, test_data):
    """TEST 3: Successful payment + receipt row + valid PDF -> No duplicate PDF generation."""
    with app.app_context():
        payment_id = test_data["payment_id"]
        pdf_path1 = ReceiptService.generate_pdf_receipt(payment_id)

        # Get mtime
        mtime1 = os.path.getmtime(pdf_path1)

        # Second call
        pdf_path2 = ReceiptService.generate_pdf_receipt(payment_id)
        mtime2 = os.path.getmtime(pdf_path2)

        assert str(pdf_path1) == str(pdf_path2)
        assert mtime1 == mtime2
        assert PaymentReceipt.query.filter_by(payment_id=payment_id).count() == 1


def test_stale_database_path_repair(app, test_data):
    """TEST 4: Receipt row contains old/stale absolute path -> Application repairs location."""
    with app.app_context():
        payment_id = test_data["payment_id"]
        pdf_path = ReceiptService.generate_pdf_receipt(payment_id)

        # Inject stale/invalid path into DB
        stale_path = r"C:\Users\HP\Downloads\6\app\instance\documents\RCPT-999-OLD.pdf"
        receipt = PaymentReceipt.query.filter_by(payment_id=payment_id).first()
        receipt.file_path = stale_path
        db.session.commit()

        # Calling generate_pdf_receipt should repair the stored path
        repaired_path = ReceiptService.generate_pdf_receipt(payment_id)
        assert os.path.exists(repaired_path)
        assert str(repaired_path) != stale_path

        updated_receipt = PaymentReceipt.query.filter_by(payment_id=payment_id).first()
        assert updated_receipt.file_path == str(repaired_path)


def test_documents_directory_auto_creation(app, test_data):
    """TEST 5: Documents directory does not exist -> Directory automatically created."""
    with app.app_context():
        doc_dir = ReceiptService.get_receipt_directory()
        assert os.path.exists(doc_dir)


def test_zero_bytes_pdf_regeneration(app, test_data):
    """TEST 6: PDF is zero bytes -> PDF regenerated."""
    with app.app_context():
        payment_id = test_data["payment_id"]
        pdf_path = ReceiptService.generate_pdf_receipt(payment_id)

        # Overwrite file with 0 bytes
        with open(pdf_path, "wb") as f:
            f.write(b"")
        assert os.path.getsize(pdf_path) == 0

        # Calling generate_pdf_receipt should regenerate it
        repaired_path = ReceiptService.generate_pdf_receipt(payment_id)
        assert os.path.exists(repaired_path)
        assert os.path.getsize(repaired_path) > 0


def test_failed_payment_receipt_rejection(app, test_data):
    """TEST 7: Payment failed -> Receipt cannot be generated."""
    with app.app_context():
        failed_payment = Payment(
            transaction_id="TXN-FAILED-100",
            society_id=test_data["society_id"],
            bill_id=test_data["bill_id"],
            resident_id=test_data["resident_id"],
            amount_paid=1500.0,
            payment_method="UPI",
            status="failed",
            payment_date=utcnow(),
        )
        db.session.add(failed_payment)
        db.session.commit()

        with pytest.raises(ValueError, match="Receipt cannot be generated"):
            ReceiptService.generate_pdf_receipt(failed_payment.id)


def test_download_route_view_mode_and_attachment(client, app, test_data):
    """TEST 8, 9, 10, 11: Authorization, view=1, normal download, repeated downloads."""
    payment_id = test_data["payment_id"]

    # Login as resident using mobile
    login_res = client.post("/login", data={"mobile": "9876543210", "password": "Pass@123"})
    assert login_res.status_code == 302

    # TEST 9: view=1 -> inline view
    res_view = client.get(f"/payments/receipt/{payment_id}?view=1")
    assert res_view.status_code == 200
    assert res_view.mimetype == "application/pdf"
    assert "inline" in res_view.headers.get("Content-Disposition", "")

    # TEST 10: normal download -> attachment download
    res_dl = client.get(f"/payments/receipt/{payment_id}")
    assert res_dl.status_code == 200
    assert res_dl.mimetype == "application/pdf"
    assert "attachment" in res_dl.headers.get("Content-Disposition", "")

    # TEST 11: download 10 times -> still 1 receipt row
    for _ in range(10):
        res = client.get(f"/payments/receipt/{payment_id}")
        assert res.status_code == 200

    with app.app_context():
        assert PaymentReceipt.query.filter_by(payment_id=payment_id).count() == 1

