<<<<<<< HEAD
from datetime import datetime, date
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
from app.models import Facility, FacilityBooking, Resident, User, Role, db
from app.services.facility_booking_service import FacilityBookingService
from app.services.tenant_service import TenantService
=======
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Facility, FacilityBooking, Resident, User, db
from app.services.facility_booking_service import FacilityBookingService
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

facilities_bp = Blueprint("facilities", __name__, url_prefix="/facilities")


<<<<<<< HEAD
def _get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return db.session.get(User, user_id)


@facilities_bp.route("", methods=["GET"])
@facilities_bp.route("/", methods=["GET"])
@facilities_bp.route("/list", methods=["GET"])
def list_facilities():
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    FacilityBookingService.ensure_default_facilities(society_id)
    fac_list = Facility.query.filter_by(society_id=society_id, is_active=True).all()

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=society_id
        ).first()
        bookings = (
            FacilityBooking.query.filter_by(
                society_id=society_id, resident_id=resident.id
            )
            .order_by(FacilityBooking.booking_date.desc())
            .all()
            if resident
            else []
        )
    else:
        bookings = (
            FacilityBooking.query.filter_by(society_id=society_id)
            .order_by(FacilityBooking.booking_date.desc())
            .all()
        )

    today_date = date.today().isoformat()

    return render_template(
        "maintenance/facilities.html",
        facilities=fac_list,
        bookings=bookings,
        today_date=today_date,
=======
@facilities_bp.route("/")
def list_facilities():
    society_id = session.get("society_id")
    fac_list = Facility.query.filter_by(society_id=society_id).all()
    bookings = (
        FacilityBooking.query.filter_by(society_id=society_id)
        .order_by(FacilityBooking.booking_date.desc())
        .all()
    )
    return render_template(
        "maintenance/facilities.html", facilities=fac_list, bookings=bookings
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    )


@facilities_bp.route("/book", methods=["POST"])
def book():
<<<<<<< HEAD
    user = _get_current_user()
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()

    if not resident:
        flash("Only registered residents can book facilities.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    facility_id_raw = request.form.get("facility_id")
    booking_date_str = request.form.get("booking_date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    purpose = request.form.get("purpose", "").strip()
    notes = request.form.get("notes", "").strip()

    if not facility_id_raw:
        flash("Facility is required.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    try:
        facility_id = int(facility_id_raw)
    except (ValueError, TypeError):
        flash("Invalid facility selected.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    if not booking_date_str:
        flash("Booking date is required.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    if not start_time:
        flash("Start time is required.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    if not end_time:
        flash("End time is required.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    try:
        booking_date = datetime.strptime(booking_date_str, "%Y-%m-%d").date()
    except ValueError:
        flash("Invalid booking date format. Use YYYY-MM-DD.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    if booking_date < date.today():
        flash("Booking date cannot be in the past.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    try:
        st = datetime.strptime(start_time, "%H:%M").time()
        et = datetime.strptime(end_time, "%H:%M").time()
    except ValueError:
        flash("Invalid time format.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    if et <= st:
        flash("End time must be later than start time.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    facility = Facility.query.filter_by(
        id=facility_id, society_id=society_id
    ).first()
    if not facility:
        flash("Invalid facility selected.", "danger")
        return redirect(url_for("facilities.list_facilities"))

    try:
        FacilityBookingService.book_facility(
            society_id=society_id,
            facility_id=facility_id,
            flat_id=resident.flat_id,
            resident_id=resident.id,
=======
    user = db.session.get(User, session.get("user_id"))
    resident = Resident.query.filter_by(user_id=user.id).first()

    facility_id = int(request.form.get("facility_id"))
    booking_date = datetime.strptime(
        request.form.get("booking_date"), "%Y-%m-%d"
    ).date()
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    purpose = request.form.get("purpose")

    try:
        FacilityBookingService.book_facility(
            society_id=user.society_id,
            facility_id=facility_id,
            flat_id=resident.flat_id if resident else 1,
            resident_id=resident.id if resident else 1,
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
<<<<<<< HEAD
            notes=notes,
        )
        flash(
            f"Facility '{facility.name}' booked successfully for {booking_date.strftime('%d %b %Y')} ({start_time} - {end_time})!",
=======
        )
        flash(
            f"Facility booked successfully for {booking_date} ({start_time} - {end_time})!",
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("facilities.list_facilities"))


<<<<<<< HEAD
@facilities_bp.route("/<int:booking_id>/cancel", methods=["POST"])
def cancel_booking(booking_id):
    user = _get_current_user()
    if not user:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    booking = FacilityBooking.query.filter_by(
        id=booking_id, society_id=society_id
    ).first_or_404()

    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=society_id
        ).first()
        if not resident or booking.resident_id != resident.id:
            abort(403)

    booking.status = "Cancelled"
    db.session.commit()
    flash("Facility booking cancelled.", "info")
    return redirect(url_for("facilities.list_facilities"))




=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


