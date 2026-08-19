import csv
import io
from app.models import db, Flat, Resident, Payment, MaintenanceBill, Complaint


class ImportExportService:
    @staticmethod
    def import_residents_csv(society_id, csv_text):
        """
        Parses CSV, validates fields, and imports residents transactionally.
        Rolls back completely if malformed.
        """
        reader = csv.DictReader(io.StringIO(csv_text))
        imported_count = 0
        errors = []

        try:
            for idx, row in enumerate(reader, start=1):
                flat_num = row.get("flat_number")
                name = row.get("full_name")
                mobile = row.get("mobile")
                res_type = row.get("resident_type", "Owner")

                if not flat_num or not name or not mobile:
                    errors.append(
                        f"Row {idx}: Missing required fields (flat_number, full_name, mobile)"
                    )
                    continue

                flat = Flat.query.filter_by(
                    society_id=society_id, flat_number=flat_num
                ).first()
                if not flat:
                    errors.append(f"Row {idx}: Flat {flat_num} not found in society")
                    continue

                resident = Resident(
                    society_id=society_id,
                    flat_id=flat.id,
                    full_name=name,
                    mobile=mobile,
                    resident_type=res_type,
                    is_primary=True,
                )
                db.session.add(resident)
                imported_count += 1

            if errors:
                db.session.rollback()
                return False, errors, 0

            db.session.commit()
            return True, [], imported_count

        except Exception as e:
            db.session.rollback()
            return False, [str(e)], 0

    @staticmethod
    def export_residents_csv(society_id):
        """Exports residents data to CSV format."""
        residents = Resident.query.filter_by(society_id=society_id).all()
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            ["ID", "Flat Number", "Full Name", "Mobile", "Email", "Type", "Status"]
        )

        for r in residents:
            writer.writerow(
                [
                    r.id,
                    r.flat.flat_number if r.flat else "N/A",
                    r.full_name,
                    r.mobile,
                    r.email or "",
                    r.resident_type,
                    r.occupancy_status,
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_defaulters_csv(
        society_id,
        building_id=None,
        block_id=None,
        min_amount=None,
        min_months=None,
    ):
        """Exports defaulters list to CSV."""
        from app.services.billing_service import BillingService

        defaulters = BillingService.get_defaulters_list(
            society_id=society_id,
            building_id=building_id,
            block_id=block_id,
            min_amount=min_amount,
            min_months=min_months,
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Resident Name",
                "Flat Number",
                "Building",
                "Block",
                "Mobile",
                "Email",
                "Pending Months Count",
                "Pending Months",
                "Maintenance Due (INR)",
                "Late Fees Due (INR)",
                "Total Outstanding (INR)",
                "Days Overdue",
                "Last Payment Date",
                "Last Payment Amount (INR)",
            ]
        )

        for d in defaulters:
            writer.writerow(
                [
                    d["resident_name"],
                    d["flat_number"],
                    d["building_name"],
                    d["block_name"],
                    d["mobile"],
                    d["email"],
                    d["pending_months_count"],
                    "; ".join(d["pending_months"]),
                    f"{d['maintenance_due']:.2f}",
                    f"{d['late_fees_due']:.2f}",
                    f"{d['total_outstanding']:.2f}",
                    d["days_overdue"],
                    d["last_payment_date"],
                    f"{d['last_payment_amount']:.2f}",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_expenses_csv(society_id):
        """Exports expense vouchers to CSV."""
        from app.models import ExpenseVoucher

        vouchers = (
            ExpenseVoucher.query.filter_by(society_id=society_id)
            .order_by(ExpenseVoucher.expense_date.desc())
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Voucher Number",
                "Expense Date",
                "Category",
                "Payee Name",
                "Amount (INR)",
                "Invoice Number",
                "Description",
                "Status",
            ]
        )

        for v in vouchers:
            writer.writerow(
                [
                    v.voucher_number,
                    v.expense_date.strftime("%Y-%m-%d") if v.expense_date else "N/A",
                    v.category,
                    v.payee_name,
                    f"{v.amount:.2f}",
                    v.invoice_number or "N/A",
                    v.description,
                    v.status,
                ]
            )

        return output.getvalue()


    @staticmethod
    def export_payments_csv(society_id):
        """Exports society payments data to CSV format."""
        payments = (
            Payment.query.filter_by(society_id=society_id)
            .order_by(Payment.payment_date.desc())
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Transaction ID",
                "Resident Name",
                "Flat Number",
                "Billing Month",
                "Amount Paid",
                "Payment Method",
                "Status",
                "Date",
            ]
        )

        for p in payments:
            writer.writerow(
                [
                    p.transaction_id,
                    p.resident.full_name if p.resident else "N/A",
                    p.resident.flat.flat_number if p.resident and p.resident.flat else "N/A",
                    p.bill.billing_month if p.bill else "N/A",
                    f"{p.amount_paid:.2f}",
                    p.payment_method,
                    p.status,
                    p.payment_date.strftime("%Y-%m-%d %H:%M:%S") if p.payment_date else "N/A",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_bills_csv(society_id):
        """Exports maintenance bills data to CSV format."""
        bills = (
            MaintenanceBill.query.filter_by(society_id=society_id)
            .order_by(MaintenanceBill.billing_month.desc())
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "Bill Number",
                "Resident Name",
                "Flat Number",
                "Billing Month",
                "Base Amount",
                "Late Fee",
                "Total Amount",
                "Amount Paid",
                "Remaining Amount",
                "Status",
                "Due Date",
            ]
        )

        for b in bills:
            writer.writerow(
                [
                    b.bill_number,
                    b.resident.full_name if b.resident else "N/A",
                    b.flat.flat_number if b.flat else "N/A",
                    b.billing_month,
                    f"{b.base_amount:.2f}",
                    f"{b.late_fee:.2f}",
                    f"{b.total_amount:.2f}",
                    f"{b.amount_paid:.2f}",
                    f"{b.remaining_amount:.2f}",
                    b.status,
                    b.due_date.strftime("%Y-%m-%d") if b.due_date else "N/A",
                ]
            )

        return output.getvalue()

    @staticmethod
    def export_complaints_csv(society_id):
        """Exports complaints data to CSV format."""
        complaints = (
            Complaint.query.filter_by(society_id=society_id)
            .order_by(Complaint.created_at.desc())
            .all()
        )
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "ID",
                "Category",
                "Title",
                "Resident Name",
                "Flat Number",
                "Priority",
                "Status",
                "Created At",
            ]
        )

        for c in complaints:
            writer.writerow(
                [
                    c.id,
                    c.category,
                    c.title,
                    c.resident.full_name if c.resident else "N/A",
                    c.resident.flat.flat_number if c.resident and c.resident.flat else "N/A",
                    c.priority,
                    c.status,
                    c.created_at.strftime("%Y-%m-%d %H:%M:%S") if c.created_at else "N/A",
                ]
            )

        return output.getvalue()

