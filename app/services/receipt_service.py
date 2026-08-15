from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from app.models import db, Payment, Society, MaintenanceBill, Flat, Resident


class ReceiptService:
    @staticmethod
    def generate_pdf_receipt(payment_id, output_path=None):
        """Generates a downloadable PDF receipt using ReportLab."""
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError("Payment not found")

        society = db.session.get(Society, payment.society_id)
        bill = db.session.get(MaintenanceBill, payment.bill_id)
        flat = db.session.get(Flat, bill.flat_id) if bill else None
        resident = (
            db.session.get(Resident, payment.resident_id) if payment.resident_id else None
        )

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
            f"Receipt No: {payment.receipt.receipt_number if payment.receipt else 'RCPT-' + str(payment.id)}",
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

        c.line(50, height - 212, width - 50, height - 212)

        # Payment Breakdown
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, height - 237, "Bill Breakdown")
        c.drawString(400, height - 237, "Amount (INR)")

        c.setFont("Helvetica", 10)
        line_y = height - 257
        if bill:
            c.drawString(50, line_y, "Maintenance")
            c.drawString(400, line_y, f"Rs. {bill.base_amount:,.2f}")
            line_y -= 16
            c.drawString(50, line_y, "Late Fee")
            c.drawString(400, line_y, f"Rs. {bill.late_fee:,.2f}")
            line_y -= 16
            c.drawString(50, line_y, "Total Bill Amount")
            c.drawString(400, line_y, f"Rs. {bill.total_amount:,.2f}")
            line_y -= 16
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

        c.setFont("Helvetica-Oblique", 9)
        c.drawString(
            50,
            height - 400,
            "This is a computer generated digital receipt. No signature required.",
        )
        c.drawString(
            50, height - 415, "Thank you for supporting community maintenance!"
        )

        c.save()
        return str(output_path)

