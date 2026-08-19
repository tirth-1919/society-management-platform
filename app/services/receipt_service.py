<<<<<<< HEAD
import logging
import os
import tempfile
from pathlib import Path

from flask import current_app, has_app_context, url_for
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from app.config import Config
from app.models import (
    Flat,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    Resident,
    Society,
    db,
)
from app.utils import utcnow

logger = logging.getLogger(__name__)
=======
﻿from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models import db, Payment, Society, MaintenanceBill, Flat, Resident
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class ReceiptService:
    @staticmethod
<<<<<<< HEAD
    def get_receipt_directory():
        """
        Returns a single reliable receipt directory Path based on Flask's actual runtime instance_path.
        Creates the directory dynamically if it does not exist.
        """
        if has_app_context() and hasattr(current_app, "instance_path") and current_app.instance_path:
            base_dir = Path(current_app.instance_path)
        else:
            base_dir = Config.INSTANCE_DIR
        out_dir = base_dir / "documents"
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir.resolve()

    @staticmethod
    def get_receipt_file_path(receipt_number):
        """
        Calculates the canonical absolute Path for a receipt number dynamically.
        Never depends on an old absolute path stored in the database.
        """
        clean_num = str(receipt_number).strip()
        if not clean_num.endswith(".pdf"):
            clean_num = f"{clean_num}.pdf"
        out_dir = ReceiptService.get_receipt_directory()
        return out_dir / clean_num

    @staticmethod
    def generate_pdf_receipt(payment_id, output_path=None):
        """
        Idempotent receipt generator and path verifier.

        1. Validates payment exists and is paid/captured.
        2. Obtains or creates the PaymentReceipt DB record with a stable receipt_number.
        3. Determines the canonical runtime filesystem path.
        4. Regenerates the PDF if missing, zero bytes, or corrupted.
        5. Repairs stale stored DB paths and commits safely.
        """
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError(f"Payment with ID {payment_id} not found")

        # Validate payment status — only allow receipt generation for successful/paid payments
        valid_statuses = ("captured", "Success", "authorized")
        if payment.status not in valid_statuses:
            raise ValueError(
                f"Receipt cannot be generated for payment #{payment_id} with status '{payment.status}'"
            )

        society = db.session.get(Society, payment.society_id)
        bill = db.session.get(MaintenanceBill, payment.bill_id) if payment.bill_id else None

        # Obtain or create PaymentReceipt
        receipt = payment.receipt
        if not receipt:
            rcpt_num = f"RCPT-{payment.society_id}-{payment.id}-{payment.payment_date.strftime('%Y%m%d')}"
            canonical_path = ReceiptService.get_receipt_file_path(rcpt_num)
            receipt = PaymentReceipt(
                receipt_number=rcpt_num,
                payment_id=payment.id,
                society_id=payment.society_id,
                file_path=str(canonical_path),
                generated_at=utcnow(),
            )
            try:
                db.session.add(receipt)
                db.session.commit()
            except Exception as exc:
                db.session.rollback()
                logger.warning(
                    "PaymentReceipt creation race condition or error for payment #%s: %s. Fetching existing.",
                    payment_id,
                    exc,
                )
                receipt = PaymentReceipt.query.filter_by(payment_id=payment.id).first()
                if not receipt:
                    raise

        rcpt_num = receipt.receipt_number
        target_path = ReceiptService.get_receipt_file_path(rcpt_num)

        # Check if PDF already exists and is valid (non-zero size)
        if target_path.exists() and target_path.stat().st_size > 0:
            # File is valid; update DB path if stale/different
            if receipt.file_path != str(target_path):
                receipt.file_path = str(target_path)
                try:
                    db.session.commit()
                except Exception as exc:
                    db.session.rollback()
                    logger.warning("Failed to update receipt file_path in DB: %s", exc)
            logger.info("Reusing valid existing receipt PDF for payment #%s at %s", payment_id, target_path)
            return target_path

        # Generate or regenerate PDF at target_path
        logger.info(
            "Generating/regenerating receipt PDF for payment #%s (Receipt: %s) at %s",
            payment_id,
            rcpt_num,
            target_path,
        )
        ReceiptService._build_pdf(payment, society, bill, receipt, target_path)

        # Verify PDF generation succeeded and file is non-zero
        if not target_path.exists() or target_path.stat().st_size == 0:
            raise RuntimeError(f"Failed to generate valid PDF receipt file at {target_path}")

        # Update DB record with valid runtime path
        receipt.file_path = str(target_path)
        receipt.generated_at = utcnow()
        try:
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            logger.warning("Failed to save updated receipt path in DB: %s", exc)

        return target_path

    @staticmethod
    def _build_pdf(payment, society, bill, receipt, target_path):
        """Internal helper to render the PDF onto target_path."""
=======
    def generate_pdf_receipt(payment_id, output_path=None):
        """Generates a downloadable PDF receipt using ReportLab."""
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError("Payment not found")

        society = db.session.get(Society, payment.society_id)
        bill = db.session.get(MaintenanceBill, payment.bill_id)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        flat = db.session.get(Flat, bill.flat_id) if bill else None
        resident = (
            db.session.get(Resident, payment.resident_id) if payment.resident_id else None
        )

<<<<<<< HEAD
        c = canvas.Canvas(str(target_path), pagesize=letter)
=======
        if not output_path:
            out_dir = Path("instance/documents")
            out_dir.mkdir(parents=True, exist_ok=True)
            rcpt_num = (
                payment.receipt.receipt_number
                if payment.receipt
                else f"RCPT-{payment.id}"
            )
            output_path = out_dir / f"{rcpt_num}.pdf"

        c = canvas.Canvas(str(output_path), pagesize=letter)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        width, height = letter

        # Header - Society Name
        c.setFont("Helvetica-Bold", 18)
        c.drawString(50, height - 50, society.name if society else "Housing Society")

        c.setFont("Helvetica", 10)
        c.drawString(
            50,
            height - 65,
            f"Reg No: {society.registration_number if society else 'N/A'}",
        )
        c.drawString(
            50,
            height - 80,
            f"Address: {society.address if society else ''}, {society.city if society else ''}",
        )

        c.setLineWidth(1)
        c.line(50, height - 90, width - 50, height - 90)

        # Receipt Title
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, height - 115, "OFFICIAL MAINTENANCE PAYMENT RECEIPT")

        # Details Box
        c.setFont("Helvetica-Bold", 10)
        c.drawString(
            50,
            height - 145,
<<<<<<< HEAD
            f"Receipt No: {receipt.receipt_number}",
=======
            f"Receipt No: {payment.receipt.receipt_number if payment.receipt else 'RCPT-' + str(payment.id)}",
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )
        c.drawString(
            350,
            height - 145,
            f"Date: {payment.payment_date.strftime('%Y-%m-%d %H:%M')}",
        )

        wing = flat.building.name if flat and flat.building else "N/A"
        c.drawString(
            50,
            height - 165,
            f"Resident Name: {resident.full_name if resident else 'Resident'}",
        )
        c.drawString(
            350,
            height - 165,
            f"Wing: {wing}  Flat: {flat.flat_number if flat else 'N/A'}",
        )

        c.drawString(
            50, height - 185, f"Billing Period: {bill.billing_month if bill else 'N/A'}"
        )
        c.drawString(
            350, height - 185, f"Bill No: {bill.bill_number if bill else 'N/A'}"
        )

        c.drawString(50, height - 200, f"Transaction ID: {payment.transaction_id}")
        c.drawString(350, height - 200, f"Payment Method: {payment.payment_method}")

<<<<<<< HEAD
        line_y = height - 215
        if payment.provider_order_id:
            c.setFont("Helvetica", 9)
            c.drawString(50, line_y, f"Razorpay Order ID: {payment.provider_order_id}")
            line_y -= 12
        if payment.provider_payment_id:
            c.setFont("Helvetica", 9)
            c.drawString(50, line_y, f"Razorpay Payment ID: {payment.provider_payment_id}")
            line_y -= 12

        c.line(50, line_y, width - 50, line_y)
        line_y -= 20

        # Payment Breakdown
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, line_y, "Bill Breakdown")
        c.drawString(400, line_y, "Amount (INR)")
        line_y -= 20

        c.setFont("Helvetica", 10)
=======
        c.line(50, height - 212, width - 50, height - 212)

        # Payment Breakdown
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, height - 237, "Bill Breakdown")
        c.drawString(400, height - 237, "Amount (INR)")

        c.setFont("Helvetica", 10)
        line_y = height - 257
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        if bill:
            c.drawString(50, line_y, "Maintenance")
            c.drawString(400, line_y, f"Rs. {bill.base_amount:,.2f}")
            line_y -= 16
<<<<<<< HEAD
            if bill.late_fee > 0:
                c.drawString(50, line_y, "Late Fee")
                c.drawString(400, line_y, f"Rs. {bill.late_fee:,.2f}")
                line_y -= 16
            if hasattr(bill, "additional_charges") and bill.additional_charges > 0:
                c.drawString(50, line_y, "Additional Charges")
                c.drawString(400, line_y, f"Rs. {bill.additional_charges:,.2f}")
                line_y -= 16
            if hasattr(bill, "discount") and bill.discount > 0:
                c.drawString(50, line_y, "Discount")
                c.drawString(400, line_y, f"-Rs. {bill.discount:,.2f}")
                line_y -= 16
            c.drawString(50, line_y, "Total Bill Amount")
            c.drawString(400, line_y, f"Rs. {bill.total_amount:,.2f}")
            line_y -= 16

=======
            c.drawString(50, line_y, "Late Fee")
            c.drawString(400, line_y, f"Rs. {bill.late_fee:,.2f}")
            line_y -= 16
            c.drawString(50, line_y, "Total Bill Amount")
            c.drawString(400, line_y, f"Rs. {bill.total_amount:,.2f}")
            line_y -= 16
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        c.drawString(50, line_y, f"Amount Paid This Receipt ({payment.payment_method})")
        c.drawString(400, line_y, f"Rs. {payment.amount_paid:,.2f}")
        line_y -= 10

        c.line(50, line_y, width - 50, line_y)
        line_y -= 20

        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, line_y, "Total Amount Received:")
        c.drawString(400, line_y, f"Rs. {payment.amount_paid:,.2f}")
        line_y -= 20

        if bill:
            c.setFont("Helvetica", 10)
            c.drawString(
                50, line_y, f"Remaining Bill Balance: Rs. {bill.remaining_amount:,.2f}"
            )
            line_y -= 15
            c.drawString(50, line_y, f"Bill Status: {bill.status}")
            line_y -= 15
        c.drawString(50, line_y, f"Payment Status: {payment.status}")
<<<<<<< HEAD
        line_y -= 25

        # Embed QR Verification Code if qrcode library available
        try:
            import qrcode

            verify_url = None
            if has_app_context():
                try:
                    verify_url = url_for(
                        "payments.verify_receipt",
                        receipt_number=receipt.receipt_number,
                        _external=True,
                    )
                except Exception:
                    pass
            if not verify_url:
                app_url = Config.APP_URL or "http://localhost:5000"
                verify_url = f"{app_url}/payments/receipt/verify/{receipt.receipt_number}"

            qr_img = qrcode.make(verify_url)
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_file:
                qr_img.save(tmp_file.name, "PNG")
                tmp_qr_path = tmp_file.name

            c.drawImage(tmp_qr_path, width - 130, line_y - 40, width=65, height=65)
            os.unlink(tmp_qr_path)
            c.setFont("Helvetica", 8)
            c.drawString(width - 135, line_y - 50, "Scan to verify receipt")
        except Exception as qr_err:
            logger.warning("Receipt PDF QR generation skipped: %s", qr_err)
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

        c.setFont("Helvetica-Oblique", 9)
        c.drawString(
            50,
<<<<<<< HEAD
            line_y - 20,
            "This is a computer generated digital receipt. No signature required.",
        )
        c.drawString(
            50, line_y - 35, "Thank you for supporting community maintenance!"
        )

        c.save()

=======
            height - 400,
            "This is a computer generated digital receipt. No signature required.",
        )
        c.drawString(
            50, height - 415, "Thank you for supporting community maintenance!"
        )

        c.save()
        return str(output_path)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

