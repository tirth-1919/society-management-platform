<<<<<<< HEAD
"""Resident-only portal pages.
=======
﻿"""Resident-only portal pages.
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

All records in this blueprint are derived from the authenticated resident,
never an identifier supplied by the browser.
"""

import csv
import io

from flask import (
    Blueprint,
    Response,
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from sqlalchemy import or_

from app.models import (
    AuditLog,
    Document,
    MaintenanceBill,
    Notice,
    NotificationLog,
    NotificationPreference,
    Payment,
    PaymentReceipt,
    RegistrationRequest,
    Resident,
    Role,
    SupportRequest,
    User,
    db,
)
from app.utils import utcnow


resident_bp = Blueprint("resident", __name__, url_prefix="/resident")


def _current_resident():
    """Return the authenticated active resident and their User."""
    user = db.session.get(User, session.get("user_id"))

    if (
        not user
        or user.role != Role.RESIDENT
        or user.account_status != "ACTIVE"
    ):
        abort(403)

    resident = Resident.query.filter_by(
        user_id=user.id,
        society_id=user.society_id,
        is_primary=True,
    ).first()

    if not resident:
        abort(403)

    return user, resident


@resident_bp.route("/profile", methods=["GET", "POST"])
def profile():
    user, resident = _current_resident()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip() or None

        if not full_name:
            flash("Your full name is required.", "danger")
        elif (
            email
            and User.query.filter(
                User.email == email,
                User.id != user.id,
            ).first()
        ):
            flash("That email address is already in use.", "danger")
        else:
            user.full_name = full_name
            resident.full_name = full_name
            user.email = email
            resident.email = email

            db.session.add(
                AuditLog(
                    society_id=user.society_id,
                    user_id=user.id,
                    action="RESIDENT_PROFILE_UPDATED",
                    details="Resident updated permitted profile fields.",
                )
            )
            db.session.commit()

            flash("Your profile has been updated.", "success")

        return redirect(url_for("resident.profile"))

    approval = (
        RegistrationRequest.query.filter_by(
            user_id=user.id,
            status="APPROVED",
        )
        .order_by(RegistrationRequest.approved_at.desc())
        .first()
    )

    return render_template(
        "resident/profile.html",
        user=user,
        resident=resident,
        approval=approval,
    )


@resident_bp.route("/change-password", methods=["POST"])
def change_password():
    """Allow an authenticated resident to change their password."""
    user, _resident = _current_resident()

    current_password = request.form.get(
        "current_password",
        "",
    )

    new_password = request.form.get(
        "new_password",
        "",
    )

    confirm_password = request.form.get(
        "confirm_password",
        "",
    )

    if not current_password or not new_password or not confirm_password:
        flash(
            "All password fields are required.",
            "danger",
        )
        return redirect(url_for("resident.profile"))

    if not user.check_password(current_password):
        flash(
            "Current password is incorrect.",
            "danger",
        )
        return redirect(url_for("resident.profile"))

    if len(new_password) < 8:
        flash(
            "New password must be at least 8 characters.",
            "danger",
        )
        return redirect(url_for("resident.profile"))

    if new_password != confirm_password:
        flash(
            "New passwords do not match.",
            "danger",
        )
        return redirect(url_for("resident.profile"))

    if current_password == new_password:
        flash(
            "New password must be different from your current password.",
            "danger",
        )
        return redirect(url_for("resident.profile"))

    user.set_password(new_password)

    db.session.add(
        AuditLog(
            society_id=user.society_id,
            user_id=user.id,
            action="RESIDENT_PASSWORD_CHANGED",
            details=(
                "Resident changed their password "
                "from the resident portal."
            ),
        )
    )

    db.session.commit()

    flash(
        "Your password has been changed successfully.",
        "success",
    )

    return redirect(url_for("resident.profile"))


@resident_bp.route("/bills")
def bills():
    user, resident = _current_resident()

    query = MaintenanceBill.query.filter_by(
        society_id=user.society_id,
        resident_id=resident.id,
    )

    search_term = request.args.get(
        "q",
        "",
    ).strip()

    status = request.args.get(
        "status",
        "",
    ).strip()

    month = request.args.get(
        "month",
        "",
    ).strip()

    year = request.args.get(
        "year",
        "",
    ).strip()

    if search_term:
        pattern = f"%{search_term}%"

        query = query.filter(
            or_(
                MaintenanceBill.bill_number.ilike(pattern),
                MaintenanceBill.billing_month.ilike(pattern),
            )
        )

    if status in {
        "Pending",
        "Partially Paid",
        "Paid",
        "Overdue",
    }:
        query = query.filter_by(
            status=status,
        )

    if month and len(month) == 7:
        query = query.filter_by(
            billing_month=month,
        )

    elif year.isdigit() and len(year) == 4:
        query = query.filter(
            MaintenanceBill.billing_month.like(
                f"{year}-%"
            )
        )

    sort = request.args.get(
        "sort",
        "month_desc",
    )

    orderings = {
        "month_asc": MaintenanceBill.billing_month.asc(),
        "month_desc": MaintenanceBill.billing_month.desc(),
        "amount_desc": MaintenanceBill.total_amount.desc(),
        "amount_asc": MaintenanceBill.total_amount.asc(),
    }

    page = max(
        request.args.get(
            "page",
            1,
            type=int,
        ),
        1,
    )

    pagination = query.order_by(
        orderings.get(
            sort,
            MaintenanceBill.billing_month.desc(),
        )
    ).paginate(
        page=page,
        per_page=10,
        error_out=False,
    )

    years = [
        value[0]
        for value in db.session.query(
            db.func.substr(
                MaintenanceBill.billing_month,
                1,
                4,
            )
        )
        .filter_by(
            society_id=user.society_id,
            resident_id=resident.id,
        )
        .distinct()
        .order_by(
            db.desc(
                db.func.substr(
                    MaintenanceBill.billing_month,
                    1,
                    4,
                )
            )
        )
        .all()
    ]

    return render_template(
        "resident/bills.html",
        bills=pagination.items,
        pagination=pagination,
        years=years,
        filters={
            "q": search_term,
            "status": status,
            "month": month,
            "year": year,
            "sort": sort,
        },
    )


<<<<<<< HEAD
@resident_bp.route("/bills/<int:bill_id>")
def bill_detail(bill_id):
    user, resident = _current_resident()

    bill = MaintenanceBill.query.filter(
        MaintenanceBill.id == bill_id,
        MaintenanceBill.society_id == user.society_id,
        or_(
            MaintenanceBill.resident_id == resident.id,
            db.and_(
                MaintenanceBill.resident_id.is_(None),
                MaintenanceBill.flat_id == resident.flat_id,
            ),
        ),
    ).first_or_404()

    latest_payment = (
        Payment.query.filter_by(
            bill_id=bill.id,
            society_id=user.society_id,
        )
        .order_by(Payment.payment_date.desc())
        .first()
    )

    return render_template(
        "resident/bill_detail.html",
        bill=bill,
        resident=resident,
        latest_payment=latest_payment,
    )


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
@resident_bp.route("/receipts")
def receipts():
    user, resident = _current_resident()

    query = (
        PaymentReceipt.query.join(Payment)
        .filter(
            Payment.society_id == user.society_id,
            Payment.resident_id == resident.id,
        )
    )

    search_term = request.args.get(
        "q",
        "",
    ).strip()

    month = request.args.get(
        "month",
        "",
    ).strip()

    year = request.args.get(
        "year",
        "",
    ).strip()

    if search_term:
        pattern = f"%{search_term}%"

        query = query.filter(
            or_(
                PaymentReceipt.receipt_number.ilike(pattern),
                Payment.transaction_id.ilike(pattern),
            )
        )

    if month and len(month) == 7:
        query = query.filter(
            db.func.strftime(
                "%Y-%m",
                Payment.payment_date,
            )
            == month
        )

    elif year.isdigit() and len(year) == 4:
        query = query.filter(
            db.func.strftime(
                "%Y",
                Payment.payment_date,
            )
            == year
        )

    page = max(
        request.args.get(
            "page",
            1,
            type=int,
        ),
        1,
    )

    pagination = query.order_by(
        Payment.payment_date.desc()
    ).paginate(
        page=page,
        per_page=10,
        error_out=False,
    )

    years = [
        value[0]
        for value in (
            db.session.query(
                db.func.strftime(
                    "%Y",
                    Payment.payment_date,
                )
            )
            .join(
                PaymentReceipt,
                PaymentReceipt.payment_id == Payment.id,
            )
            .filter(
                Payment.society_id == user.society_id,
                Payment.resident_id == resident.id,
            )
            .distinct()
            .order_by(
                db.desc(
                    db.func.strftime(
                        "%Y",
                        Payment.payment_date,
                    )
                )
            )
            .all()
        )
    ]

    return render_template(
        "resident/receipts.html",
        receipts=pagination.items,
        pagination=pagination,
        years=years,
        filters={
            "q": search_term,
            "month": month,
            "year": year,
        },
    )


NOTIFICATION_CATEGORIES = {
    "Maintenance": {
        "BILL_GENERATED",
        "DUE_REMINDER",
        "OVERDUE_REMINDER",
        "LATE_FEE_NOTICE",
    },
    "Payment": {
        "PAYMENT_SUCCESS",
    },
    "Account": set(),
    "System": set(),
}


def _notification_category(notification_type):
    for category, types in NOTIFICATION_CATEGORIES.items():
        if notification_type in types:
            return category

    return "System"


@resident_bp.route("/notifications")
def notifications():
    user, resident = _current_resident()

    category = request.args.get(
        "category",
        "",
    ).strip()

    query = NotificationLog.query.filter_by(
        user_id=user.id,
        society_id=user.society_id,
    )

    if category in NOTIFICATION_CATEGORIES:
        types = NOTIFICATION_CATEGORIES[category]

        if types:
            query = query.filter(
                NotificationLog.notification_type.in_(types)
            )

    notifications_list = (
        query.order_by(
            NotificationLog.created_at.desc()
        ).all()
    )

    links = {}

    for item in notifications_list:
        if not item.billing_month:
            continue

        bill = MaintenanceBill.query.filter_by(
            society_id=user.society_id,
            resident_id=resident.id,
            billing_month=item.billing_month,
        ).first()

        if not bill:
            continue

        if item.notification_type == "PAYMENT_SUCCESS":
            payment = (
                Payment.query.filter_by(
                    bill_id=bill.id,
                    resident_id=resident.id,
                )
                .order_by(
                    Payment.payment_date.desc()
                )
                .first()
            )

            if payment:
                links[item.id] = (
                    "View receipt",
                    url_for(
                        "payments.download_receipt",
                        payment_id=payment.id,
                    ),
                )

        elif bill.remaining_amount > 0:
            label = (
                "Pay now"
                if item.notification_type
                in {
                    "DUE_REMINDER",
                    "OVERDUE_REMINDER",
                    "LATE_FEE_NOTICE",
                }
                else "View bill"
            )

            target = (
                url_for(
                    "payments.pay_bill",
                    bill_id=bill.id,
                )
                if label == "Pay now"
                else url_for(
                    "resident.bill_detail",
                    bill_id=bill.id,
                )
            )

            links[item.id] = (
                label,
                target,
            )

    return render_template(
        "resident/notifications.html",
        notifications=notifications_list,
        links=links,
        category=category,
        categories=list(
            NOTIFICATION_CATEGORIES.keys()
        ),
        notification_category=_notification_category,
    )


@resident_bp.route(
    "/notifications/<int:notification_id>/read",
    methods=["POST"],
)
def mark_notification_read(notification_id):
    user, _resident = _current_resident()

    notification = NotificationLog.query.filter_by(
        id=notification_id,
        user_id=user.id,
        society_id=user.society_id,
    ).first_or_404()

    if notification.read_at is None:
        notification.read_at = utcnow()
        db.session.commit()

    return redirect(
        url_for("resident.notifications")
    )


@resident_bp.route("/search")
def search():
    user, resident = _current_resident()

    term = request.args.get(
        "q",
        "",
    ).strip()

    bills = []
    payments = []
    receipts_list = []

    if len(term) >= 2:
        pattern = f"%{term}%"

        bills = (
            MaintenanceBill.query.filter(
                MaintenanceBill.resident_id == resident.id,
                MaintenanceBill.society_id == user.society_id,
                or_(
                    MaintenanceBill.bill_number.ilike(pattern),
                    MaintenanceBill.billing_month.ilike(pattern),
                ),
            )
            .order_by(
                MaintenanceBill.billing_month.desc()
            )
            .all()
        )

        payments = (
            Payment.query.filter(
                Payment.resident_id == resident.id,
                Payment.society_id == user.society_id,
            )
            .order_by(
                Payment.payment_date.desc()
            )
            .all()
        )

        receipts_list = (
            PaymentReceipt.query.join(Payment)
            .filter(
                Payment.resident_id == resident.id,
                Payment.society_id == user.society_id,
                or_(
                    PaymentReceipt.receipt_number.ilike(
                        pattern
                    ),
                    Payment.transaction_id.ilike(
                        pattern
                    ),
                ),
            )
            .order_by(
                Payment.payment_date.desc()
            )
            .all()
        )

    return render_template(
        "resident/search.html",
        term=term,
        bills=bills,
        payments=payments,
        receipts=receipts_list,
    )


@resident_bp.route("/help")
def help_center():
    user, _resident = _current_resident()

    return render_template(
        "resident/help.html",
        society=user.society,
    )


@resident_bp.route("/announcements")
def announcements():
    user, _resident = _current_resident()

    now = utcnow()

    notices = (
        Notice.query.filter(
            Notice.society_id == user.society_id,
<<<<<<< HEAD
            Notice.created_at <= now,
=======
            Notice.publish_date <= now,
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            or_(
                Notice.expiry_date.is_(None),
                Notice.expiry_date >= now,
            ),
        )
        .order_by(
<<<<<<< HEAD
            Notice.created_at.desc()
=======
            Notice.publish_date.desc()
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )
        .all()
    )

    return render_template(
        "resident/announcements.html",
        notices=notices,
    )


@resident_bp.route("/activity")
def activity():
    user, _resident = _current_resident()

    logs = (
        AuditLog.query.filter_by(
            user_id=user.id,
            society_id=user.society_id,
        )
        .order_by(
            AuditLog.created_at.desc()
        )
        .limit(100)
        .all()
    )

    return render_template(
        "resident/activity.html",
        logs=logs,
    )


@resident_bp.route("/payments/export.csv")
def export_payments_csv():
    user, resident = _current_resident()

    payments = (
        Payment.query.filter_by(
            society_id=user.society_id,
            resident_id=resident.id,
        )
        .order_by(
            Payment.payment_date.desc()
        )
        .all()
    )

    buf = io.StringIO()
    writer = csv.writer(buf)

    writer.writerow(
        [
            "Date",
            "Bill Number",
            "Billing Month",
            "Amount Paid",
            "Method",
            "Transaction ID",
            "Status",
        ]
    )

    for payment in payments:
        writer.writerow(
            [
                (
                    payment.payment_date.strftime(
                        "%Y-%m-%d %H:%M"
                    )
                    if payment.payment_date
                    else ""
                ),
                (
                    payment.bill.bill_number
                    if payment.bill
                    else ""
                ),
                (
                    payment.bill.billing_month
                    if payment.bill
                    else ""
                ),
                f"{payment.amount_paid:.2f}",
                payment.payment_method or "",
                payment.transaction_id or "",
                payment.status or "",
            ]
        )

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": (
                "attachment; "
                "filename=my_payment_history.csv"
            )
        },
    )


SUPPORT_CATEGORIES = [
    "Billing",
    "Payment",
    "Receipt",
    "Account",
    "Technical",
    "Other",
]

SUPPORT_STATUSES = [
    "OPEN",
    "IN_PROGRESS",
    "RESOLVED",
    "CLOSED",
]


@resident_bp.route("/support")
def support_list():
    user, _resident = _current_resident()

    requests_list = (
        SupportRequest.query.filter_by(
            society_id=user.society_id,
            user_id=user.id,
        )
        .order_by(
            SupportRequest.created_at.desc()
        )
        .all()
    )

    return render_template(
        "resident/support_list.html",
        requests=requests_list,
    )


@resident_bp.route(
    "/support/new",
    methods=["GET", "POST"],
)
def support_new():
    user, resident = _current_resident()

    if request.method == "POST":
        subject = (
            request.form.get("subject") or ""
        ).strip()

        category = request.form.get(
            "category",
            "Other",
        )

        message = (
            request.form.get("message") or ""
        ).strip()

        if category not in SUPPORT_CATEGORIES:
            category = "Other"

        if not subject or not message:
            flash(
                "Subject and message are required.",
                "danger",
            )

            return render_template(
                "resident/support_new.html",
                categories=SUPPORT_CATEGORIES,
                form={
                    "subject": subject,
                    "category": category,
                    "message": message,
                },
            )

        req = SupportRequest(
            society_id=user.society_id,
            user_id=user.id,
            resident_id=resident.id,
            subject=subject,
            category=category,
            message=message,
            status="OPEN",
        )

        db.session.add(req)
        db.session.commit()

        flash(
            "Support request submitted. "
            "The society office will respond soon.",
            "success",
        )

        return redirect(
            url_for("resident.support_list")
        )

    return render_template(
        "resident/support_new.html",
        categories=SUPPORT_CATEGORIES,
        form={},
    )


@resident_bp.route(
    "/support/<int:request_id>"
)
def support_detail(request_id):
    user, _resident = _current_resident()

    req = SupportRequest.query.filter_by(
        id=request_id,
        society_id=user.society_id,
        user_id=user.id,
    ).first_or_404()

    return render_template(
        "resident/support_detail.html",
        req=req,
    )


@resident_bp.route(
    "/preferences",
    methods=["GET", "POST"],
)
def notification_preferences():
    user, resident = _current_resident()

    pref = NotificationPreference.get_or_create(
        user.id,
        user.society_id,
        resident.id if resident else None,
    )

    if request.method == "POST":
        pref.maintenance_reminders = (
            "maintenance_reminders"
            in request.form
        )

        pref.payment_reminders = (
            "payment_reminders"
            in request.form
        )

        pref.payment_confirmations = (
            "payment_confirmations"
            in request.form
        )

        pref.announcements = (
            "announcements"
            in request.form
        )

        db.session.commit()

        flash(
            "Notification preferences updated.",
            "success",
        )

        return redirect(
            url_for(
                "resident.notification_preferences"
            )
        )

    return render_template(
        "resident/preferences.html",
        pref=pref,
    )


@resident_bp.route("/documents")
def documents():
    user, _resident = _current_resident()

    docs = (
        Document.query.filter_by(
            society_id=user.society_id,
            access_level="RESIDENT_PUBLIC",
        )
        .order_by(
            Document.created_at.desc()
        )
        .all()
    )

    return render_template(
        "resident/documents.html",
        documents=docs,
    )


@resident_bp.route(
    "/documents/<int:doc_id>/download"
)
def download_document(doc_id):
    user, _resident = _current_resident()

    doc = Document.query.filter_by(
        id=doc_id,
        society_id=user.society_id,
        access_level="RESIDENT_PUBLIC",
    ).first_or_404()

    return send_file(
        doc.file_path,
        as_attachment=True,
<<<<<<< HEAD
    )


# ===========================================================================
# FEATURE 17 — Download Bill as PDF
# ===========================================================================

@resident_bp.route("/bills/<int:bill_id>/pdf")
def bill_pdf(bill_id):
    """Generate and download a bill summary PDF (server-side, resident-scoped)."""
    user, resident = _current_resident()

    bill = MaintenanceBill.query.filter(
        MaintenanceBill.id == bill_id,
        MaintenanceBill.society_id == user.society_id,
        or_(
            MaintenanceBill.resident_id == resident.id,
            db.and_(
                MaintenanceBill.resident_id.is_(None),
                MaintenanceBill.flat_id == resident.flat_id,
            ),
        ),
    ).first_or_404()

    try:
        from pathlib import Path
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas as rl_canvas

        out_dir = Path("instance/documents")
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_path = out_dir / f"Bill_{bill.bill_number}.pdf"

        c = rl_canvas.Canvas(str(pdf_path), pagesize=letter)
        width, height = letter

        society = user.society
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, society.name if society else "Society")
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 65, f"Address: {society.address if society else ''}")
        c.line(50, height - 75, width - 50, height - 75)

        c.setFont("Helvetica-Bold", 13)
        c.drawString(50, height - 100, "MAINTENANCE BILL / INVOICE")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 125, f"Bill Number: {bill.bill_number}")
        c.drawString(350, height - 125, f"Billing Month: {bill.billing_month}")
        c.drawString(50, height - 140, f"Resident: {resident.full_name}")
        c.drawString(350, height - 140, f"Flat: {bill.flat.flat_number if bill.flat else 'N/A'}")
        c.drawString(50, height - 155, f"Due Date: {bill.due_date.strftime('%d %b %Y') if bill.due_date else 'N/A'}")
        c.drawString(350, height - 155, f"Status: {bill.status}")
        c.line(50, height - 165, width - 50, height - 165)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(50, height - 185, "Description")
        c.drawString(430, height - 185, "Amount (INR)")
        c.setFont("Helvetica", 10)
        y = height - 205
        c.drawString(50, y, "Monthly Society Maintenance")
        c.drawString(430, y, f"Rs. {bill.base_amount:,.2f}")
        y -= 16
        if bill.late_fee > 0:
            c.drawString(50, y, "Late Fee / Penalty")
            c.drawString(430, y, f"Rs. {bill.late_fee:,.2f}")
            y -= 16
        if bill.additional_charges > 0:
            c.drawString(50, y, "Additional Charges")
            c.drawString(430, y, f"Rs. {bill.additional_charges:,.2f}")
            y -= 16
        if bill.discount > 0:
            c.drawString(50, y, "Discount")
            c.drawString(430, y, f"-Rs. {bill.discount:,.2f}")
            y -= 16
        c.line(50, y, width - 50, y)
        y -= 16
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Total Payable")
        c.drawString(430, y, f"Rs. {bill.total_amount:,.2f}")
        y -= 14
        if bill.amount_paid > 0:
            c.setFont("Helvetica", 10)
            c.drawString(50, y, "Amount Paid")
            c.drawString(430, y, f"Rs. {bill.amount_paid:,.2f}")
            y -= 14
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, "Balance Due")
        c.drawString(430, y, f"Rs. {bill.remaining_amount:,.2f}")
        y -= 30
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(50, y, "This is a computer generated bill. For queries contact the society office.")
        c.save()

        db.session.add(AuditLog(
            society_id=user.society_id,
            user_id=user.id,
            action="BILL_PDF_DOWNLOADED",
            details=f"Resident downloaded bill PDF: {bill.bill_number}",
        ))
        db.session.commit()

        return send_file(
            str(pdf_path),
            as_attachment=True,
            download_name=f"Bill_{bill.bill_number}.pdf",
        )
    except ImportError:
        abort(503, description="PDF generation library not available.")
    except Exception as e:
        abort(500, description=f"PDF generation failed: {e}")


# ===========================================================================
# FEATURE 18 — Yearly Payment Summary
# ===========================================================================

@resident_bp.route("/payments/yearly")
def yearly_summary():
    """Resident-only yearly payment summary."""
    user, resident = _current_resident()

    current_year = utcnow().year
    year = request.args.get("year", str(current_year), type=str)
    if not year.isdigit():
        year = str(current_year)

    bills_this_year = (
        MaintenanceBill.query.filter(
            MaintenanceBill.resident_id == resident.id,
            MaintenanceBill.society_id == user.society_id,
            MaintenanceBill.billing_month.like(f"{year}-%"),
        )
        .order_by(MaintenanceBill.billing_month.asc())
        .all()
    )

    payments_this_year = (
        Payment.query.filter(
            Payment.resident_id == resident.id,
            Payment.society_id == user.society_id,
            db.func.strftime("%Y", Payment.payment_date) == year,
            Payment.status.in_(["captured", "Success"]),
        )
        .order_by(Payment.payment_date.asc())
        .all()
    )

    total_billed = sum(b.total_amount for b in bills_this_year)
    total_paid = sum(b.amount_paid for b in bills_this_year)
    total_pending = sum(b.remaining_amount for b in bills_this_year)
    total_late_fees = sum(b.late_fee for b in bills_this_year)

    # Available years from bills
    available_years = [
        v[0]
        for v in db.session.query(
            db.func.substr(MaintenanceBill.billing_month, 1, 4)
        )
        .filter_by(resident_id=resident.id, society_id=user.society_id)
        .distinct()
        .order_by(db.desc(db.func.substr(MaintenanceBill.billing_month, 1, 4)))
        .all()
    ]

    return render_template(
        "resident/yearly_summary.html",
        year=year,
        available_years=available_years,
        bills=bills_this_year,
        payments=payments_this_year,
        total_billed=total_billed,
        total_paid=total_paid,
        total_pending=total_pending,
        total_late_fees=total_late_fees,
    )


# ===========================================================================
# FEATURE 38 — Complaint Attachments (uploaded via complaint form)
# FEATURE 40 — Complaint Rating
# ===========================================================================

@resident_bp.route("/complaints")
def resident_complaints():
    """Resident-scoped complaint list with status breakdown."""
    from app.models import Complaint
    user, resident = _current_resident()

    status_filter = request.args.get("status", "").strip()
    query = Complaint.query.filter_by(
        resident_id=resident.id,
        society_id=user.society_id,
    )
    if status_filter:
        query = query.filter_by(status=status_filter)

    complaints_list = query.order_by(Complaint.created_at.desc()).all()

    all_c = Complaint.query.filter_by(resident_id=resident.id, society_id=user.society_id).all()
    status_counts = {
        "Open": sum(1 for c in all_c if c.status == "Submitted"),
        "In Progress": sum(1 for c in all_c if c.status in ("Assigned", "In Progress")),
        "Resolved": sum(1 for c in all_c if c.status == "Resolved"),
        "Closed": sum(1 for c in all_c if c.status == "Closed"),
    }

    return render_template(
        "resident/complaints.html",
        complaints=complaints_list,
        status_filter=status_filter,
        status_counts=status_counts,
    )


@resident_bp.route("/complaints/<int:complaint_id>")
def complaint_detail(complaint_id):
    """Resident-scoped complaint detail with timeline."""
    user, resident = _current_resident()

    from app.models import Complaint, ComplaintComment
    complaint = Complaint.query.filter_by(
        id=complaint_id,
        resident_id=resident.id,
        society_id=user.society_id,
    ).first_or_404()

    comments = ComplaintComment.query.filter_by(
        complaint_id=complaint.id
    ).order_by(ComplaintComment.created_at.asc()).all()

    return render_template(
        "resident/complaint_detail.html",
        complaint=complaint,
        comments=comments,
    )


@resident_bp.route("/complaints/<int:complaint_id>/rate", methods=["POST"])
def rate_complaint(complaint_id):
    """Feature 40: Allow resident to rate a resolved complaint."""
    user, resident = _current_resident()

    from app.models import Complaint, ComplaintComment
    complaint = Complaint.query.filter_by(
        id=complaint_id,
        resident_id=resident.id,
        society_id=user.society_id,
    ).first_or_404()

    if complaint.status not in ("Resolved", "Closed"):
        flash("You can only rate resolved complaints.", "warning")
        return redirect(url_for("resident.complaint_detail", complaint_id=complaint_id))

    # Prevent duplicate rating
    existing_rating = ComplaintComment.query.filter_by(
        complaint_id=complaint_id,
        user_id=user.id,
    ).filter(
        ComplaintComment.comment.like("RATING:%")
    ).first()

    if existing_rating:
        flash("You have already rated this complaint.", "info")
        return redirect(url_for("resident.complaint_detail", complaint_id=complaint_id))

    rating = request.form.get("rating", "").strip()
    feedback = request.form.get("feedback", "").strip()

    if rating not in ("1", "2", "3", "4", "5"):
        flash("Please select a valid rating (1-5).", "danger")
        return redirect(url_for("resident.complaint_detail", complaint_id=complaint_id))

    rating_comment = ComplaintComment(
        complaint_id=complaint_id,
        user_id=user.id,
        comment=f"RATING:{rating} | Feedback: {feedback or 'No additional feedback.'}",
    )
    db.session.add(rating_comment)
    db.session.add(AuditLog(
        society_id=user.society_id,
        user_id=user.id,
        action="COMPLAINT_RATED",
        details=f"Resident rated complaint #{complaint.ticket_number}: {rating}/5",
    ))
    db.session.commit()

    flash(f"Thank you! Your rating of {rating}/5 stars has been recorded.", "success")
    return redirect(url_for("resident.complaint_detail", complaint_id=complaint_id))


# ===========================================================================
# FEATURES 41-44 — Resident Visitor Management
# ===========================================================================

@resident_bp.route("/visitors")
def resident_visitors():
    """Feature 43: Resident-scoped visitor history with filters."""
    user, resident = _current_resident()

    from app.models import PreApprovedPass, Visitor

    # Pre-approved passes (invitations)
    passes = (
        PreApprovedPass.query.filter_by(
            society_id=user.society_id,
            resident_id=resident.id,
        )
        .order_by(PreApprovedPass.created_at.desc())
        .all()
    )

    # Actual visitor log entries for this flat
    visitor_logs = (
        Visitor.query.filter_by(
            society_id=user.society_id,
            flat_id=resident.flat_id,
        )
        .order_by(Visitor.entry_time.desc())
        .limit(50)
        .all()
    )

    return render_template(
        "resident/visitors.html",
        passes=passes,
        visitor_logs=visitor_logs,
        resident=resident,
    )


@resident_bp.route("/visitors/invite", methods=["GET", "POST"])
def invite_visitor():
    """Feature 41: Resident creates a visitor invitation / pre-approved pass."""
    user, resident = _current_resident()

    if request.method == "POST":
        visitor_name = request.form.get("visitor_name", "").strip()
        mobile = request.form.get("mobile", "").strip()
        expected_date_str = request.form.get("expected_date", "").strip()
        expected_time = request.form.get("expected_time", "").strip()
        purpose = request.form.get("purpose", "Guest").strip()

        if not visitor_name or not mobile or not expected_date_str:
            flash("Visitor name, mobile, and expected date are required.", "danger")
            return redirect(url_for("resident.invite_visitor"))

        # Validate phone length
        if len(mobile) < 10:
            flash("Please enter a valid mobile number.", "danger")
            return redirect(url_for("resident.invite_visitor"))

        try:
            from datetime import date as date_cls
            expected_date = date_cls.fromisoformat(expected_date_str)
        except ValueError:
            flash("Invalid date format.", "danger")
            return redirect(url_for("resident.invite_visitor"))

        from app.services.visitor_service import VisitorService
        p = VisitorService.create_pre_approved_pass(
            society_id=user.society_id,
            flat_id=resident.flat_id,
            resident_id=resident.id,
            visitor_name=visitor_name,
            mobile=mobile,
            expected_date=expected_date,
            purpose=purpose,
            expected_time=expected_time or None,
        )
        db.session.add(AuditLog(
            society_id=user.society_id,
            user_id=user.id,
            action="VISITOR_INVITATION_CREATED",
            details=f"Resident created visitor pass {p.pass_code} for {visitor_name} on {expected_date}",
        ))
        db.session.commit()

        flash(f"Visitor invitation created! Pass code: {p.pass_code}", "success")
        return redirect(url_for("resident.resident_visitors"))

    from datetime import date as date_cls
    min_date = date_cls.today().isoformat()
    return render_template("resident/invite_visitor.html", min_date=min_date)


@resident_bp.route("/visitors/<int:pass_id>/cancel", methods=["POST"])
def cancel_visitor(pass_id):
    """Feature 44: Resident can cancel their own active visitor invitation."""
    user, resident = _current_resident()

    from app.models import PreApprovedPass
    visitor_pass = PreApprovedPass.query.filter_by(
        id=pass_id,
        resident_id=resident.id,   # ownership check — cannot cancel others
        society_id=user.society_id,
    ).first_or_404()

    if visitor_pass.is_used:
        flash("This pass has already been used and cannot be cancelled.", "warning")
        return redirect(url_for("resident.resident_visitors"))

    # Mark pass as cancelled by setting is_used = True
    visitor_pass.is_used = True

    db.session.add(AuditLog(
        society_id=user.society_id,
        user_id=user.id,
        action="VISITOR_PASS_CANCELLED",
        details=f"Resident cancelled visitor pass {visitor_pass.pass_code}",
    ))
    db.session.commit()

    flash("Visitor invitation has been cancelled.", "success")
    return redirect(url_for("resident.resident_visitors"))


# ===========================================================================
# FEATURE 47 — Profile Completion helper (used in profile template)
# FEATURE 48 — Account Security: Sessions + Login Activity
# ===========================================================================

@resident_bp.route("/security")
def security():
    """Feature 48: Active sessions and login activity."""
    user, resident = _current_resident()

    from app.models import UserSession, AuditLog as AL
    active_sessions = (
        UserSession.query.filter_by(user_id=user.id, is_active=True)
        .order_by(UserSession.created_at.desc())
        .all()
    )
    login_logs = (
        AL.query.filter_by(user_id=user.id)
        .filter(AL.action.in_(["LOGIN_FAILURE", "RESIDENT_PASSWORD_CHANGED", "RAZORPAY_ORDER_CREATED", "PAYMENT_VERIFIED_AND_CAPTURED"]))
        .order_by(AL.created_at.desc())
        .limit(20)
        .all()
    )
    return render_template(
        "resident/security.html",
        active_sessions=active_sessions,
        login_logs=login_logs,
        user=user,
        resident=resident,
    )


@resident_bp.route("/security/logout-all", methods=["POST"])
def logout_all_devices():
    """Feature 48: Log out all other sessions."""
    user, resident = _current_resident()

    from app.models import UserSession
    current_token = session.get("session_token")

    updated = 0
    for s in UserSession.query.filter_by(user_id=user.id, is_active=True).all():
        if s.session_token != current_token:
            s.is_active = False
            updated += 1

    db.session.add(AuditLog(
        society_id=user.society_id,
        user_id=user.id,
        action="LOGOUT_ALL_DEVICES",
        details=f"Resident logged out {updated} other session(s).",
    ))
    db.session.commit()
    flash(f"Logged out from {updated} other device(s) successfully.", "success")
    return redirect(url_for("resident.security"))


# ===========================================================================
# FEATURE 49 — Household / Family Members
# ===========================================================================

@resident_bp.route("/household")
def household():
    """Feature 49: View and manage household members (dependents)."""
    user, resident = _current_resident()

    from app.models import Dependent, EmergencyContact
    dependents = Dependent.query.filter_by(resident_id=resident.id).all()
    emergency_contacts = EmergencyContact.query.filter_by(
        resident_id=resident.id
    ).all()

    return render_template(
        "resident/household.html",
        resident=resident,
        dependents=dependents,
        emergency_contacts=emergency_contacts,
    )


@resident_bp.route("/household/dependent/add", methods=["POST"])
def add_dependent():
    """Add a household member."""
    user, resident = _current_resident()

    from app.models import Dependent
    name = request.form.get("name", "").strip()
    relation = request.form.get("relation", "").strip()
    age_str = request.form.get("age", "").strip()

    if not name or not relation:
        flash("Name and relation are required.", "danger")
        return redirect(url_for("resident.household"))

    age = int(age_str) if age_str.isdigit() else None
    dep = Dependent(
        resident_id=resident.id,
        name=name,
        relation=relation,
        age=age,
    )
    db.session.add(dep)
    db.session.add(AuditLog(
        society_id=user.society_id,
        user_id=user.id,
        action="HOUSEHOLD_MEMBER_ADDED",
        details=f"Added dependent: {name} ({relation})",
    ))
    db.session.commit()
    flash(f"{name} added to your household.", "success")
    return redirect(url_for("resident.household"))


@resident_bp.route("/household/dependent/<int:dep_id>/remove", methods=["POST"])
def remove_dependent(dep_id):
    """Remove a household member."""
    user, resident = _current_resident()

    from app.models import Dependent
    dep = Dependent.query.filter_by(
        id=dep_id,
        resident_id=resident.id,   # ownership check
    ).first_or_404()

    name = dep.name
    db.session.delete(dep)
    db.session.add(AuditLog(
        society_id=user.society_id,
        user_id=user.id,
        action="HOUSEHOLD_MEMBER_REMOVED",
        details=f"Removed dependent: {name}",
    ))
    db.session.commit()
    flash(f"{name} removed from your household.", "success")
    return redirect(url_for("resident.household"))


@resident_bp.route("/household/emergency/add", methods=["POST"])
def add_emergency_contact():
    """Add an emergency contact."""
    user, resident = _current_resident()

    from app.models import EmergencyContact
    name = request.form.get("name", "").strip()
    relation = request.form.get("relation", "").strip()
    phone = request.form.get("phone", "").strip()

    if not name or not relation or not phone:
        flash("Name, relation, and phone are required.", "danger")
        return redirect(url_for("resident.household"))

    ec = EmergencyContact(
        society_id=user.society_id,
        resident_id=resident.id,
        name=name,
        relation=relation,
        phone=phone,
        is_global=False,
    )
    db.session.add(ec)
    db.session.commit()
    flash(f"Emergency contact {name} added.", "success")
    return redirect(url_for("resident.household"))


@resident_bp.route("/household/emergency/<int:ec_id>/remove", methods=["POST"])
def remove_emergency_contact(ec_id):
    """Remove an emergency contact."""
    user, resident = _current_resident()

    from app.models import EmergencyContact
    ec = EmergencyContact.query.filter_by(
        id=ec_id,
        resident_id=resident.id,  # ownership check
    ).first_or_404()

    name = ec.name
    db.session.delete(ec)
    db.session.commit()
    flash(f"Emergency contact {name} removed.", "success")
    return redirect(url_for("resident.household"))


# ===========================================================================
# FEATURE 45 — Notification Center: Mark All Read
# ===========================================================================

@resident_bp.route("/notifications/mark-all-read", methods=["POST"])
def mark_all_notifications_read():
    """Feature 45: Mark all unread notifications as read."""
    user, _resident = _current_resident()

    updated = NotificationLog.query.filter_by(
        user_id=user.id,
        society_id=user.society_id,
    ).filter(NotificationLog.read_at.is_(None)).all()

    now = utcnow()
    for n in updated:
        n.read_at = now

    db.session.commit()
    flash(f"Marked {len(updated)} notification(s) as read.", "success")
    return redirect(url_for("resident.notifications"))


# ===========================================================================
# FEATURE 34 — Receipt Verification QR display helper
# ===========================================================================

@resident_bp.route("/receipts/<int:payment_id>/qr")
def receipt_qr(payment_id):
    """Feature 34/42: Show receipt verification QR code."""
    user, resident = _current_resident()

    receipt = PaymentReceipt.query.join(Payment).filter(
        Payment.id == payment_id,
        Payment.society_id == user.society_id,
        Payment.resident_id == resident.id,
    ).with_entities(PaymentReceipt).first_or_404()

    try:
        import qrcode
        import io as _io
        from flask import Response as FR
        from app.config import Config as Cfg

        verify_url = (
            (Cfg.APP_URL or "http://localhost:5000")
            + url_for("payments.verify_receipt", receipt_number=receipt.receipt_number)
        )
        img = qrcode.make(verify_url)
        buf = _io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return FR(buf.getvalue(), mimetype="image/png")
    except ImportError:
        abort(503, description="QR code library not available.")


@resident_bp.route("/notifications/unread-count")
def notifications_unread_count():
    """Return the unread notification count for the authenticated resident."""
    user, _resident = _current_resident()
    count = NotificationLog.query.filter_by(
        user_id=user.id,
        society_id=user.society_id,
    ).filter(NotificationLog.read_at.is_(None)).count()
    return {"unread_count": count}


# ===========================================================================
# RESIDENT FINANCIAL STATEMENT / GENERAL LEDGER
# ===========================================================================

@resident_bp.route("/ledger")
def resident_ledger():
    """Resident-scoped financial statement / general ledger."""
    user, resident = _current_resident()
    from app.services.billing_service import BillingService

    ledger_data = BillingService.get_resident_ledger(
        resident_id=resident.id,
        society_id=user.society_id,
    )
    return render_template("resident/ledger.html", ledger_data=ledger_data)


@resident_bp.route("/ledger/export.csv")
def export_ledger_csv():
    """Export resident ledger entries as CSV."""
    user, resident = _current_resident()
    from app.services.billing_service import BillingService

    ledger_data = BillingService.get_resident_ledger(
        resident_id=resident.id,
        society_id=user.society_id,
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Date", "Description", "Debit (INR)", "Credit (INR)", "Balance (INR)", "Type", "Reference"])

    for row in ledger_data["entries"]:
        writer.writerow([
            row["date"],
            row["description"],
            f"{row['debit']:.2f}" if row["debit"] > 0 else "0.00",
            f"{row['credit']:.2f}" if row["credit"] > 0 else "0.00",
            f"{row['balance']:.2f}",
            row["type"],
            row["ref"],
        ])

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=resident_ledger_flat_{resident.flat.flat_number if resident.flat else resident.id}.csv"
        },
    )


@resident_bp.route("/dispute/submit", methods=["POST"])
def submit_dispute():
    """File a payment dispute."""
    user, resident = _current_resident()
    claimed_amount = request.form.get("claimed_amount", type=float)
    transaction_id = request.form.get("transaction_id", "").strip()
    evidence_notes = request.form.get("evidence_notes", "").strip()
    bill_id = request.form.get("bill_id", type=int)

    if not claimed_amount or claimed_amount <= 0:
        flash("Valid claimed amount is required.", "danger")
        return redirect(url_for("resident.bills"))

    from app.services.payment_service import PaymentService

    try:
        dispute = PaymentService.create_payment_dispute(
            society_id=user.society_id,
            resident_id=resident.id,
            claimed_amount=claimed_amount,
            transaction_id=transaction_id,
            bill_id=bill_id,
            evidence_notes=evidence_notes,
        )
        flash(f"Payment dispute #{dispute.id} submitted successfully. Society admin will review your report.", "success")
    except Exception as e:
        flash(f"Failed to submit dispute: {e}", "danger")

    return redirect(url_for("resident.bills"))


=======
    )
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
