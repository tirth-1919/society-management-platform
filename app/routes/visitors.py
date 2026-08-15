from app.utils import utcnow
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Visitor, PreApprovedPass, Resident, User, db
from app.services.visitor_service import VisitorService

visitors_bp = Blueprint("visitors", __name__, url_prefix="/visitors")


@visitors_bp.route("/")
def list_visitors():
    society_id = session.get("society_id")
    db.session.get(User, session.get("user_id"))

    visitors_list = (
        Visitor.query.filter_by(society_id=society_id)
        .order_by(Visitor.entry_time.desc())
        .all()
    )
    passes = PreApprovedPass.query.filter_by(society_id=society_id).all()
    return render_template(
        "security/visitors.html", visitors=visitors_list, passes=passes
    )


@visitors_bp.route("/pre-approve", methods=["POST"])
def pre_approve():
    user = db.session.get(User, session.get("user_id"))
    resident = Resident.query.filter_by(user_id=user.id).first()

    visitor_name = request.form.get("visitor_name")
    mobile = request.form.get("mobile")
    purpose = request.form.get("purpose", "Guest")

    p = VisitorService.create_pre_approved_pass(
        society_id=user.society_id,
        flat_id=resident.flat_id if resident else 1,
        resident_id=resident.id if resident else 1,
        visitor_name=visitor_name,
        mobile=mobile,
        expected_date=utcnow().date(),
        purpose=purpose,
    )
    flash(f"Pre-approved pass generated! Code: {p.pass_code}", "success")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/verify-pass", methods=["POST"])
def verify_pass():
    society_id = session.get("society_id")
    pass_code = request.form.get("pass_code")

    ok, msg, visitor = VisitorService.verify_and_checkin_pass(pass_code, society_id)
    if ok:
        flash(f"{msg}: {visitor.visitor_name} checked in!", "success")
    else:
        flash(msg, "danger")
    return redirect(url_for("visitors.list_visitors"))


@visitors_bp.route("/exit/<int:visitor_id>", methods=["POST"])
def exit_visitor(visitor_id):
    VisitorService.log_visitor_exit(visitor_id)
    flash("Visitor exit recorded!", "info")
    return redirect(url_for("visitors.list_visitors"))





