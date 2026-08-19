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
from app.models import db, Complaint, Resident, User, Role
from app.services.complaint_service import ComplaintService
from app.services.tenant_service import TenantService

complaints_bp = Blueprint("complaints", __name__, url_prefix="/complaints")


def _get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@complaints_bp.route("/")
def list_complaints():
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=society_id
        ).first()
        complaints_list = (
            Complaint.query.filter_by(
                resident_id=resident.id, society_id=society_id
            ).order_by(Complaint.created_at.desc()).all()
            if resident
            else []
        )
    else:
        complaints_list = (
            Complaint.query.filter_by(society_id=society_id)
            .order_by(Complaint.created_at.desc())
            .all()
        )

    # Attach SLA check info
    for c in complaints_list:
        c.sla_breached = ComplaintService.check_sla_breach(c)

    return render_template("maintenance/complaints.html", complaints=complaints_list)


@complaints_bp.route("/<int:complaint_id>")
def complaint_detail(complaint_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    complaint = Complaint.query.get_or_404(complaint_id)
    TenantService.enforce_tenant_isolation(user, complaint.society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=complaint.society_id
        ).first()
        if not resident or complaint.resident_id != resident.id:
            abort(403, description="Forbidden: You do not have permission to view this ticket")

    sla_breached = ComplaintService.check_sla_breach(complaint)
    staff_members = User.query.filter(
        User.society_id == complaint.society_id,
        User.role.in_([Role.SOCIETY_ADMIN, Role.GUARD, Role.COMMITTEE_MEMBER]),
    ).all()

    return render_template(
        "maintenance/complaint_detail.html",
        complaint=complaint,
        sla_breached=sla_breached,
        staff_members=staff_members,
    )


@complaints_bp.route("/create", methods=["GET", "POST"])
def create_complaint():
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()

    if not resident:
        flash("Only registered residents can create complaints.", "danger")
        return redirect(url_for("complaints.list_complaints"))

    if request.method == "POST":
        category = request.form.get("category", "General").strip()
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        priority = request.form.get("priority", "Medium").strip()

        if not title or not description:
            flash("Title and description are required.", "danger")
            return render_template("maintenance/create_complaint.html")

        c = ComplaintService.create_complaint(
            society_id=society_id,
            flat_id=resident.flat_id,
            resident_id=resident.id,
            category=category,
            title=title,
            description=description,
            priority=priority,
        )
        flash(f"Complaint Ticket #{c.ticket_number} created successfully!", "success")
        return redirect(url_for("complaints.list_complaints"))

    return render_template("maintenance/create_complaint.html")


@complaints_bp.route("/<int:complaint_id>/status", methods=["POST"])
def update_status(complaint_id):
    user = _get_current_user()
    if not user:
        abort(403)

    complaint = Complaint.query.get_or_404(complaint_id)
    TenantService.enforce_tenant_isolation(user, complaint.society_id)

    # Authorization check
    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=complaint.society_id
        ).first()
        if not resident or complaint.resident_id != resident.id:
            abort(403)

    new_status = request.form.get("status")
    notes = request.form.get("resolution_notes")
    ComplaintService.update_status(complaint_id, new_status, notes)
    flash("Complaint status updated!", "success")
    return redirect(url_for("complaints.list_complaints"))


@complaints_bp.route("/<int:complaint_id>/comment", methods=["POST"])
def add_comment(complaint_id):
    user = _get_current_user()
    if not user:
        abort(403)

    complaint = Complaint.query.get_or_404(complaint_id)
    TenantService.enforce_tenant_isolation(user, complaint.society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=complaint.society_id
        ).first()
        if not resident or complaint.resident_id != resident.id:
            abort(403)

    comment_text = request.form.get("comment", "").strip()
    if comment_text:
        ComplaintService.add_comment(complaint_id, user.id, comment_text)
        flash("Comment added successfully.", "success")
    return redirect(url_for("complaints.complaint_detail", complaint_id=complaint_id))


@complaints_bp.route("/<int:complaint_id>/assign", methods=["POST"])
def assign_staff(complaint_id):
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    complaint = Complaint.query.get_or_404(complaint_id)
    TenantService.enforce_tenant_isolation(user, complaint.society_id)

    staff_id = request.form.get("assigned_staff_id", type=int)
    ComplaintService.assign_staff(complaint_id, staff_id)
    flash("Staff assigned successfully.", "success")
    return redirect(url_for("complaints.complaint_detail", complaint_id=complaint_id))


@complaints_bp.route("/<int:complaint_id>/reopen", methods=["POST"])
def reopen_complaint(complaint_id):
    user = _get_current_user()
    if not user:
        abort(403)

    complaint = Complaint.query.get_or_404(complaint_id)
    TenantService.enforce_tenant_isolation(user, complaint.society_id)

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=complaint.society_id
        ).first()
        if not resident or complaint.resident_id != resident.id:
            abort(403)

    reason = request.form.get("reason", "Issue not resolved").strip()
    ComplaintService.reopen_complaint(complaint_id, user.id, reason)
    flash("Complaint ticket reopened.", "info")
    return redirect(url_for("complaints.complaint_detail", complaint_id=complaint_id))






