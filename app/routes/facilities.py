from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Facility, FacilityBooking, Resident, User, db
from app.services.facility_booking_service import FacilityBookingService

facilities_bp = Blueprint("facilities", __name__, url_prefix="/facilities")


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
    )


@facilities_bp.route("/book", methods=["POST"])
def book():
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
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            purpose=purpose,
        )
        flash(
            f"Facility booked successfully for {booking_date} ({start_time} - {end_time})!",
            "success",
        )
    except ValueError as e:
        flash(str(e), "danger")

    return redirect(url_for("facilities.list_facilities"))




