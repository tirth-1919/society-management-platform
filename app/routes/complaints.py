from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import db, Complaint, Resident, User
from app.services.complaint_service import ComplaintService

complaints_bp = Blueprint("complaints", __name__, url_prefix="/complaints")


@complaints_bp.route("/")
def list_complaints():
    society_id = session.get("society_id")
    user_id = session.get("user_id")
    user = db.session.get(User, user_id)

    if user.role == "Resident":
        resident = Resident.query.filter_by(user_id=user.id).first()
        complaints_list = (
            Complaint.query.filter_by(resident_id=resident.id).all() if resident else []
        )
    else:
        complaints_list = Complaint.query.filter_by(society_id=society_id).all()

    return render_template("maintenance/complaints.html", complaints=complaints_list)


@complaints_bp.route("/create", methods=["GET", "POST"])
def create_complaint():
    user = db.session.get(User, session.get("user_id"))
    resident = Resident.query.filter_by(user_id=user.id).first()

    if request.method == "POST":
        category = request.form.get("category")
        title = request.form.get("title")
        description = request.form.get("description")
        priority = request.form.get("priority", "Medium")

        c = ComplaintService.create_complaint(
            society_id=user.society_id,
            flat_id=resident.flat_id if resident else 1,
            resident_id=resident.id if resident else 1,
            category=category,
            title=title,
            description=description,
            priority=priority,
        )
        flash(f"Complaint Ticket {c.ticket_number} created successfully!", "success")
        return redirect(url_for("complaints.list_complaints"))

    return render_template("maintenance/create_complaint.html")


@complaints_bp.route("/<int:complaint_id>/status", methods=["POST"])
def update_status(complaint_id):
    new_status = request.form.get("status")
    notes = request.form.get("resolution_notes")
    ComplaintService.update_status(complaint_id, new_status, notes)
    flash("Complaint status updated!", "success")
    return redirect(url_for("complaints.list_complaints"))




