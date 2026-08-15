from app.utils import utcnow
from datetime import datetime
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
    MaintenanceBill,
    Complaint,
    Visitor,
    User,
    Role,
    Payment,
    NotificationLog,
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

        open_complaints = (
            Complaint.query.filter_by(society_id=society_id)
            .filter(Complaint.status.in_(["Submitted", "In Progress"]))
            .count()
            if society_id
            else 0
        )
        visitors_today = (
            Visitor.query.filter_by(society_id=society_id).count() if society_id else 0
        )

        fin = (
            AccountingService.get_financial_summary(society_id)
            if society_id
            else {"total_expense": 0}
        )

        return render_template(
            "dashboard.html",
            role=role,
            user=user,
            society=society,
            flats_count=flats_count,
            residents_count=residents_count,
            total_collected=total_collected,
            total_pending=total_pending,
            open_complaints=open_complaints,
            visitors_today=visitors_today,
            total_expense=fin["total_expense"],
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

        # Server-side maintenance due calculation â€” never trust frontend
        dues = (
            BillingService.resident_dashboard_summary(resident.id, society_id)
            if flat
            else {
                "current_month_maintenance": Config.MONTHLY_MAINTENANCE,
                "pending_months": 0,
                "maintenance_due": 0.0,
                "late_fee": 0.0,
                "total_due": 0.0,
            }
        )

        recent_payments = (
            (
                Payment.query.filter_by(society_id=society_id, resident_id=resident.id)
                .order_by(Payment.payment_date.desc())
                .limit(5)
                .all()
            )
            if resident
            else []
        )
        notifications = (
            NotificationLog.query.filter_by(society_id=society_id, user_id=user.id)
            .order_by(NotificationLog.created_at.desc())
            .limit(4)
            .all()
        )

        # Additive, read-only summary widgets â€” derived from the same
        # persisted bills/payments dues already uses, no new calculation
        # of what is owed and no change to billing_service's logic.
        today = utcnow().date()
        due_countdown = None
        if dues.get("next_due_date"):
            delta_days = (dues["next_due_date"] - today).days
            due_countdown = {"days": abs(delta_days), "overdue": delta_days < 0}
        current_year = today.strftime("%Y")
        year_payments = (
            (
                Payment.query.filter_by(
                    society_id=society_id, resident_id=resident.id, status="Success"
                )
                .filter(Payment.payment_date >= datetime(today.year, 1, 1))
                .all()
            )
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
            due_countdown=due_countdown,
            payment_summary=payment_summary,
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
    """Generates a QR code that opens the resident portal.

    Uses the configured production APP_URL if set; otherwise falls back to
    the current request's own host, so it works automatically for local
    dev and for an ngrok tunnel without any hardcoded localhost value ever
    reaching a production deployment.
    """
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
    img.save(buf, format="PNG")
    buf.seek(0)
    return Response(buf.getvalue(), mimetype="image/png")


# â”€â”€ Public API: cascading dropdowns for registration form (no auth required) â”€â”€


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







