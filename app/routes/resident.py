"""Resident-only portal pages.

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
            Notice.publish_date <= now,
            or_(
                Notice.expiry_date.is_(None),
                Notice.expiry_date >= now,
            ),
        )
        .order_by(
            Notice.publish_date.desc()
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
    )