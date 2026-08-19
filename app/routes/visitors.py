from app.utils import utcnow
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from app.models import Visitor, PreApprovedPass, Resident, User, Role, db
from app.services.visitor_service import VisitorService
from app.services.tenant_service import TenantService

visitors_bp = Blueprint("visitors", __name__, url_prefix="/visitors")


def _get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@visitors_bp.route("/")
def list_visitors():
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=society_id
        ).first()
        if resident:
            visitors_list = (
                Visitor.query.filter_by(
                    society_id=society_id, flat_id=resident.flat_id
                )
                .order_by(Visitor.entry_time.desc())
                .all()
            )
            passes = (
                PreApprovedPass.query.filter_by(
                    society_id=society_id, resident_id=resident.id
                )
                .order_by(PreApprovedPass.created_at.desc())
                .all()
            )
        else:
            visitors_list = []
            passes = []
    else:
        visitors_list = (
            Visitor.query.filter_by(society_id=society_id)
            .order_by(Visitor.entry_time.desc())
            .all()
        )
        passes = (
            PreApprovedPass.query.filter_by(society_id=society_id)
            .order_by(PreApprovedPass.created_at.desc())
            .all()
        )

    return render_template(
        "security/visitors.html", visitors=visitors_list, passes=passes
    )


@visitors_bp.route("/pre-approve", methods=["POST"])
def pre_approve():
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()

    if not resident:
        flash("Only registered residents can generate pre-approved passes.", "danger")
        return redirect(url_for("visitors.list_visitors"))

    visitor_name = request.form.get("visitor_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    purpose = request.form.get("purpose", "Guest").strip()

    if not visitor_name or not mobile:
        flash("Visitor name and mobile number are required.", "danger")
        return redirect(url_for("visitors.list_visitors"))

    p = VisitorService.create_pre_approved_pass(
        society_id=society_id,
        flat_id=resident.flat_id,
        resident_id=resident.id,
        visitor_name=visitor_name,
        mobile=mobile,
        expected_date=utcnow().date(),
        purpose=purpose,
    )
    flash(f"Pre-approved pass generated! Code: {p.pass_code}", "success")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/verify-pass", methods=["POST"])
def verify_pass():
    user = _get_current_user()
    if not user:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    pass_code = request.form.get("pass_code", "").strip()

    ok, msg, visitor = VisitorService.verify_and_checkin_pass(pass_code, society_id)
    if ok and visitor:
        flash(f"{msg}: {visitor.visitor_name} checked in!", "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/pass/<int:pass_id>/cancel", methods=["POST"])
def cancel_pass(pass_id):
    user = _get_current_user()
    if not user:
        abort(403)

    pass_obj = PreApprovedPass.query.get_or_404(pass_id)
    TenantService.enforce_tenant_isolation(user, pass_obj.society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=pass_obj.society_id
        ).first()
        if not resident or pass_obj.resident_id != resident.id:
            abort(403, description="Forbidden: Cannot cancel another resident's pass")

    pass_obj.status = "Cancelled"
    from app.models import db
    db.session.commit()
    flash("Visitor pass cancelled successfully.", "info")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/checkin-adhoc", methods=["POST"])
def checkin_adhoc():
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN, Role.GUARD]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    flat_id = request.form.get("flat_id", type=int)
    visitor_name = request.form.get("visitor_name", "").strip()
    mobile = request.form.get("mobile", "").strip()
    purpose = request.form.get("purpose", "Visitor").strip()
    vehicle_number = request.form.get("vehicle_number", "").strip()

    v = VisitorService.log_visitor_entry(
        society_id=society_id,
        flat_id=flat_id,
        visitor_name=visitor_name,
        mobile=mobile,
        purpose=purpose,
        vehicle_number=vehicle_number,
    )
    flash(f"Ad-hoc visitor {v.visitor_name} checked in successfully.", "success")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/exit/<int:visitor_id>", methods=["POST"])
def exit_visitor(visitor_id):
    user = _get_current_user()
    if not user:
        abort(403)

    visitor = Visitor.query.get_or_404(visitor_id)
    TenantService.enforce_tenant_isolation(user, visitor.society_id)

    VisitorService.log_visitor_exit(visitor.id)
    flash("Visitor exit recorded!", "info")
    return redirect(url_for("visitors.list_visitors"))







