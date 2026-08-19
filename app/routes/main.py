<<<<<<< HEAD
from app.utils import utcnow
from datetime import datetime, date
from sqlalchemy import func
=======
﻿from app.utils import utcnow
from datetime import datetime
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
from flask import (
    Blueprint,
    render_template,
    session,
    redirect,
    url_for,
    abort,
    jsonify,
    request,
    Response,
)
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    Resident,
<<<<<<< HEAD
    RegistrationRequest,
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    MaintenanceBill,
    Complaint,
    Visitor,
    User,
    Role,
    Payment,
    NotificationLog,
<<<<<<< HEAD
    PaymentReceipt,
    PreApprovedPass,
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
)
from app.services.accounting_service import AccountingService
from app.services.billing_service import BillingService
from app.config import Config

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    # Always start at login; the dashboard is reached only after sign-in.
    return redirect(url_for("auth.login"))


@main_bp.route("/dashboard")
def dashboard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, user_id)
    if not user or user.account_status != "ACTIVE":
        abort(
            403,
            description="Forbidden: Pending approval or inactive account cannot access dashboard",
        )

    society_id = session.get("society_id")
    role = session.get("role")

    society = db.session.get(Society, society_id) if society_id else None

    if role in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        flats_count = (
            Flat.query.filter_by(society_id=society_id).count()
            if society_id
            else Flat.query.count()
        )
        residents_count = (
            Resident.query.filter_by(society_id=society_id).count()
            if society_id
            else Resident.query.count()
        )

        bills = (
            MaintenanceBill.query.filter_by(society_id=society_id).all()
            if society_id
            else MaintenanceBill.query.all()
        )
        total_collected = sum(b.amount_paid for b in bills)
        total_pending = sum(b.remaining_amount for b in bills)
<<<<<<< HEAD
        total_billed = sum(b.total_amount for b in bills)
        total_late_fee = sum(b.late_fee for b in bills)
        overdue_bills = [b for b in bills if b.status == "Overdue"]
        overdue_amount = sum(b.remaining_amount for b in overdue_bills)
        collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0.0

        # --- Real 6-month rolling collection trend (no external deps) ---
        today = utcnow().date()
        monthly_chart_labels = []
        monthly_chart_data = []
        for i in range(5, -1, -1):
            # Subtract i months from today using pure datetime arithmetic
            year = today.year
            month = today.month - i
            while month <= 0:
                month += 12
                year -= 1
            month_str = f"{year:04d}-{month:02d}"
            label = datetime(year, month, 1).strftime("%b %Y")
            if society_id:
                collected = db.session.query(
                    func.coalesce(func.sum(MaintenanceBill.amount_paid), 0.0)
                ).filter(
                    MaintenanceBill.society_id == society_id,
                    MaintenanceBill.billing_month == month_str,
                ).scalar()
            else:
                collected = db.session.query(
                    func.coalesce(func.sum(MaintenanceBill.amount_paid), 0.0)
                ).filter(
                    MaintenanceBill.billing_month == month_str,
                ).scalar()
            monthly_chart_labels.append(label)
            monthly_chart_data.append(float(collected or 0.0))

        # --- All-time payment method distribution (not just last 6 payments) ---
        if society_id:
            all_captured = Payment.query.filter(
                Payment.society_id == society_id,
                Payment.status.in_(["captured", "Success", "paid"]),
            ).all()
        else:
            all_captured = Payment.query.filter(
                Payment.status.in_(["captured", "Success", "paid"]),
            ).all()
        payment_methods_all = {}
        for p in all_captured:
            m = p.payment_method or "Online"
            payment_methods_all[m] = payment_methods_all.get(m, 0) + float(p.amount_paid)
        # Fallback: if no captured payments, use all payments from recent transactions
        payment_methods = payment_methods_all if payment_methods_all else {}

        # --- Occupancy rate ---
        occupied_flats = (
            Flat.query.filter_by(society_id=society_id, occupancy_status="Occupied").count()
            if society_id
            else Flat.query.filter_by(occupancy_status="Occupied").count()
        )
        occupancy_rate = round((occupied_flats / flats_count * 100) if flats_count > 0 else 0.0, 1)

        # --- Open complaints (count + list for sidebar panel) ---
        open_complaints_q = (
            Complaint.query.filter_by(society_id=society_id)
            .filter(Complaint.status.in_(["Submitted", "In Progress"]))
            if society_id
            else Complaint.query.filter(Complaint.status.in_(["Submitted", "In Progress"]))
        )
        open_complaints = open_complaints_q.count()
        open_complaints_list = (
            open_complaints_q
            .order_by(Complaint.created_at.desc())
            .limit(5)
            .all()
        )

        # --- Visitors today (entries today, exit_time is None = still inside) ---
        today_start = datetime(today.year, today.month, today.day)
        visitors_today = (
            Visitor.query.filter(
                Visitor.society_id == society_id,
                Visitor.entry_time >= today_start,
            ).count()
            if society_id
            else Visitor.query.filter(Visitor.entry_time >= today_start).count()
        )

        pending_registrations = (
            RegistrationRequest.query.filter_by(society_id=society_id, status="PENDING_APPROVAL").count()
            if society_id
            else RegistrationRequest.query.filter_by(status="PENDING_APPROVAL").count()
=======

        open_complaints = (
            Complaint.query.filter_by(society_id=society_id)
            .filter(Complaint.status.in_(["Submitted", "In Progress"]))
            .count()
            if society_id
            else 0
        )
        visitors_today = (
            Visitor.query.filter_by(society_id=society_id).count() if society_id else 0
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )

        fin = (
            AccountingService.get_financial_summary(society_id)
            if society_id
            else {"total_expense": 0}
        )

<<<<<<< HEAD
        # Recent transactions widget
        recent_transactions = (
            Payment.query.filter_by(society_id=society_id)
            .order_by(Payment.payment_date.desc())
            .limit(6)
            .all()
            if society_id
            else Payment.query.order_by(Payment.payment_date.desc()).limit(6).all()
        )

        from app.services.society_health_service import SocietyHealthService
        daily_brief = SocietyHealthService.get_admin_daily_brief(society_id=society_id)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        return render_template(
            "dashboard.html",
            role=role,
            user=user,
            society=society,
            flats_count=flats_count,
<<<<<<< HEAD
            occupied_flats_count=occupied_flats,
            occupancy_rate=occupancy_rate,
            pending_registrations_count=pending_registrations,
            residents_count=residents_count,
            total_collected=total_collected,
            total_pending=total_pending,
            total_billed=total_billed,
            total_late_fee=total_late_fee,
            overdue_amount=overdue_amount,
            overdue_count=len(overdue_bills),
            collection_rate=round(collection_rate, 1),
            recent_transactions=recent_transactions,
            payment_methods=payment_methods,
            open_complaints=open_complaints,
            open_complaints_list=open_complaints_list,
            visitors_today=visitors_today,
            total_expense=fin["total_expense"],
            daily_brief=daily_brief,
            society_health=daily_brief.get("society_health"),
            monthly_chart_labels=monthly_chart_labels,
            monthly_chart_data=monthly_chart_data,
=======
            residents_count=residents_count,
            total_collected=total_collected,
            total_pending=total_pending,
            open_complaints=open_complaints,
            visitors_today=visitors_today,
            total_expense=fin["total_expense"],
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )

    elif role == Role.RESIDENT:
        resident = Resident.query.filter_by(user_id=user.id).first()
        flat = resident.flat if resident else None
        bills = (
            MaintenanceBill.query.filter_by(
                society_id=society_id, resident_id=resident.id
            )
            .order_by(MaintenanceBill.billing_month.desc())
            .all()
            if flat
            else []
        )
        my_complaints = (
            Complaint.query.filter_by(resident_id=resident.id).all() if resident else []
        )

<<<<<<< HEAD
        # Server-side maintenance due calculation — never trust frontend
=======
        # Server-side maintenance due calculation â€” never trust frontend
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        dues = (
            BillingService.resident_dashboard_summary(resident.id, society_id)
            if flat
            else {
                "current_month_maintenance": Config.MONTHLY_MAINTENANCE,
                "pending_months": 0,
                "maintenance_due": 0.0,
                "late_fee": 0.0,
                "total_due": 0.0,
<<<<<<< HEAD
                "unpaid_bills": [],
                "next_due_date": None,
                "next_payable_bill": None,
                "overall_status": "Paid",
                "overdue_bills": [],
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            }
        )

        recent_payments = (
<<<<<<< HEAD
            Payment.query.filter_by(society_id=society_id, resident_id=resident.id)
            .order_by(Payment.payment_date.desc())
            .limit(5)
            .all()
=======
            (
                Payment.query.filter_by(society_id=society_id, resident_id=resident.id)
                .order_by(Payment.payment_date.desc())
                .limit(5)
                .all()
            )
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            if resident
            else []
        )
        notifications = (
            NotificationLog.query.filter_by(society_id=society_id, user_id=user.id)
            .order_by(NotificationLog.created_at.desc())
<<<<<<< HEAD
            .limit(5)
            .all()
        )

        from app.services.ai_service import AIService
        resident_ai = AIService.get_resident_payment_insights(resident.id, society_id) if resident else None

        unread_notifications_count = (
            NotificationLog.query.filter_by(society_id=society_id, user_id=user.id)
            .filter(NotificationLog.read_at.is_(None))
            .count()
        )

        # Feature 4 / 16 — Due countdown
=======
            .limit(4)
            .all()
        )

        # Additive, read-only summary widgets â€” derived from the same
        # persisted bills/payments dues already uses, no new calculation
        # of what is owed and no change to billing_service's logic.
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        today = utcnow().date()
        due_countdown = None
        if dues.get("next_due_date"):
            delta_days = (dues["next_due_date"] - today).days
            due_countdown = {"days": abs(delta_days), "overdue": delta_days < 0}
<<<<<<< HEAD

        current_year = today.strftime("%Y")
        year_payments = (
            Payment.query.filter(
                Payment.society_id == society_id,
                Payment.resident_id == resident.id,
                Payment.status.in_(["captured", "Success"]),
                Payment.payment_date >= datetime(today.year, 1, 1),
            ).all()
=======
        current_year = today.strftime("%Y")
        year_payments = (
            (
                Payment.query.filter_by(
                    society_id=society_id, resident_id=resident.id, status="Success"
                )
                .filter(Payment.payment_date >= datetime(today.year, 1, 1))
                .all()
            )
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            if resident
            else []
        )
        year_bills = (
            [b for b in bills if b.billing_month.startswith(current_year)]
            if bills
            else []
        )
        payment_summary = {
            "current_month_maintenance": dues.get("current_month_maintenance", 0.0),
            "total_paid_bills": len([b for b in bills if b.status == "Paid"]),
            "total_pending_bills": dues.get("pending_months", 0),
            "year_total_paid": sum(p.amount_paid for p in year_payments),
            "year_maintenance_paid": sum(
                b.amount_paid for b in year_bills if b.status == "Paid"
            ),
            "year_late_fee_paid": sum(
                b.late_fee for b in year_bills if b.status == "Paid"
            ),
            "year_paid_months": len([b for b in year_bills if b.status == "Paid"]),
            "year_pending_months": len([b for b in year_bills if b.status != "Paid"]),
        }

<<<<<<< HEAD
        # Feature 7 — Last payment details
        last_payment = recent_payments[0] if recent_payments else None

        # Feature 9 — Latest receipt shortcut
        latest_receipt = (
            PaymentReceipt.query.join(Payment)
            .filter(
                Payment.society_id == society_id,
                Payment.resident_id == resident.id,
            )
            .order_by(Payment.payment_date.desc())
            .first()
            if resident
            else None
        )

        # Feature 6 — Pending months timeline
        all_months_timeline = []
        if bills:
            paid_map = {b.billing_month: b for b in bills if b.status == "Paid"}
            partial_map = {b.billing_month: b for b in bills if b.status == "Partially Paid"}
            overdue_map = {b.billing_month: b for b in bills if b.status == "Overdue"}
            pending_map = {b.billing_month: b for b in bills if b.status == "Pending"}

            all_bill_months = sorted({b.billing_month for b in bills})
            for month_str in all_bill_months:
                if month_str in paid_map:
                    status_label, status_class = "Paid", "success"
                elif month_str in partial_map:
                    status_label, status_class = "Partial", "info"
                elif month_str in overdue_map:
                    status_label, status_class = "Overdue", "danger"
                else:
                    status_label, status_class = "Pending", "warning"
                try:
                    month_display = datetime.strptime(month_str, "%Y-%m").strftime("%B %Y")
                except ValueError:
                    month_display = month_str
                bill_obj = (
                    paid_map.get(month_str)
                    or partial_map.get(month_str)
                    or overdue_map.get(month_str)
                    or pending_map.get(month_str)
                )
                all_months_timeline.append({
                    "month": month_str,
                    "display": month_display,
                    "status": status_label,
                    "class": status_class,
                    "bill_id": bill_obj.id if bill_obj else None,
                })

        # Feature 10 — Open complaints count
        open_complaints_count = sum(
            1 for c in my_complaints if c.status not in ("Closed", "Resolved")
        )

        # Upcoming visitor passes
        upcoming_visitors = (
            PreApprovedPass.query.filter_by(
                society_id=society_id,
                resident_id=resident.id,
                is_used=False,
            )
            .order_by(PreApprovedPass.expected_date.asc())
            .limit(3)
            .all()
            if resident
            else []
        )

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        return render_template(
            "dashboard.html",
            role=role,
            user=user,
            resident=resident,
            flat=flat,
            bills=bills,
            complaints=my_complaints,
            dues=dues,
            recent_payments=recent_payments,
            notifications=notifications,
<<<<<<< HEAD
            unread_notifications_count=unread_notifications_count,
            due_countdown=due_countdown,
            payment_summary=payment_summary,
            last_payment=last_payment,
            latest_receipt=latest_receipt,
            all_months_timeline=all_months_timeline,
            open_complaints_count=open_complaints_count,
            upcoming_visitors=upcoming_visitors,
            resident_ai=resident_ai,
=======
            due_countdown=due_countdown,
            payment_summary=payment_summary,
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )

    elif role == Role.SECURITY:
        recent_visitors = (
            Visitor.query.filter_by(society_id=society_id)
            .order_by(Visitor.entry_time.desc())
            .limit(10)
            .all()
            if society_id
            else []
        )
        return render_template(
            "dashboard.html", role=role, user=user, visitors=recent_visitors
        )

    return render_template("dashboard.html", role=role, user=user)


@main_bp.route("/qr/portal.png")
def portal_qr():
<<<<<<< HEAD
    """Generates a QR code that opens the resident portal."""
=======
    """Generates a QR code that opens the resident portal.

    Uses the configured production APP_URL if set; otherwise falls back to
    the current request's own host, so it works automatically for local
    dev and for an ngrok tunnel without any hardcoded localhost value ever
    reaching a production deployment.
    """
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    try:
        import qrcode
        import io
    except ImportError:
        abort(
            503,
            description="QR code support is not installed. Add 'qrcode[pil]' to requirements.txt and reinstall.",
        )
    target_url = Config.APP_URL or request.host_url
    img = qrcode.make(target_url)
    buf = io.BytesIO()
<<<<<<< HEAD
    img.save(buf, "PNG")
=======
    img.save(buf, format="PNG")
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


<<<<<<< HEAD
# Public API: cascading dropdowns for registration form (no auth required)
=======
# â”€â”€ Public API: cascading dropdowns for registration form (no auth required) â”€â”€
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


@main_bp.route("/api/buildings")
def api_buildings():
    """Wings for a given society_id."""
    society_id = request.args.get("society_id")
    if not society_id:
        return jsonify({"buildings": []})
    buildings = (
        Building.query.filter_by(society_id=int(society_id))
        .order_by(Building.name)
        .all()
    )
    return jsonify({"buildings": [{"id": b.id, "name": b.name} for b in buildings]})


@main_bp.route("/api/blocks")
def api_blocks():
    """Blocks for a given wing (building_id) and society_id."""
    building_id = request.args.get("building_id")
    society_id = request.args.get("society_id")
    if not building_id:
        return jsonify({"blocks": []})
    q = Block.query.filter_by(building_id=int(building_id))
    if society_id:
        q = q.filter_by(society_id=int(society_id))
    blocks = q.order_by(Block.name).all()
    return jsonify({"blocks": [{"id": b.id, "name": b.name} for b in blocks]})


@main_bp.route("/api/flats")
def api_flats():
    """Flats for a given block_id (preferred) or building_id (fallback)."""
    block_id = request.args.get("block_id")
    building_id = request.args.get("building_id")
    if block_id:
        flats = (
            Flat.query.filter_by(block_id=int(block_id))
            .order_by(Flat.flat_number)
            .all()
        )
    elif building_id:
        flats = (
            Flat.query.filter_by(building_id=int(building_id))
            .order_by(Flat.flat_number)
            .all()
        )
    else:
        return jsonify({"flats": []})
    return jsonify(
        {"flats": [{"id": f.id, "flat_number": f.flat_number} for f in flats]}
    )


<<<<<<< HEAD
@main_bp.route("/api/search")
def api_search():
    user_id = session.get("user_id")
    if not user_id:
        abort(401)
    user = db.session.get(User, user_id)
    society_id = session.get("society_id") or (user.society_id if user else None)
    if not society_id:
        return jsonify({"query": "", "categories": []})
    query_str = request.args.get("q", "")
    category = request.args.get("category", None)
    limit = request.args.get("limit", 6, type=int)
    from app.services.search_service import SearchService
    res = SearchService.global_search(
        user, int(society_id), query_str, category=category, limit=limit
    )
    return jsonify(res)
=======




>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

