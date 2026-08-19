from datetime import datetime, date
from app.models import db, Facility, FacilityBooking

DEFAULT_FACILITIES = [
    ("Club House", 50, 0.0, False),
    ("Swimming Pool", 30, 0.0, False),
    ("Gym", 20, 0.0, False),
    ("Community Hall", 100, 500.0, True),
    ("Party Hall", 80, 400.0, True),
    ("Indoor Games Room", 25, 0.0, False),
    ("Badminton Court", 10, 100.0, False),
    ("Tennis Court", 10, 100.0, True),
    ("Garden", 100, 0.0, False),
    ("Children's Play Area", 40, 0.0, False),
]


class FacilityBookingService:
    @staticmethod
    def ensure_default_facilities(society_id):
        """
        Seeds/ensures all 10 default facilities exist for a society without duplicates.
        """
        if not society_id:
            return
        existing_names = {
            f.name.strip().lower()
            for f in Facility.query.filter_by(society_id=society_id).all()
        }
        added = False
        for name, capacity, hourly_rate, approval in DEFAULT_FACILITIES:
            if name.lower() not in existing_names:
                facility = Facility(
                    society_id=society_id,
                    name=name,
                    capacity=capacity,
                    hourly_rate=hourly_rate,
                    is_active=True,
                    requires_approval=approval,
                )
                db.session.add(facility)
                added = True
        if added:
            db.session.commit()

    @staticmethod
    def book_facility(
        society_id,
        facility_id,
        flat_id,
        resident_id,
        booking_date,
        start_time,
        end_time,
        purpose=None,
        notes=None,
    ):
        """
        Books a facility slot with atomic database locking to prevent double booking collisions.
        """
        if isinstance(booking_date, str):
            try:
                booking_date = datetime.strptime(booking_date, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid booking date format. Use YYYY-MM-DD.")

        today = date.today()
        if booking_date < today:
            raise ValueError("Booking date cannot be in the past.")

        if not start_time or not end_time:
            raise ValueError("Start time and end time are required.")

        try:
            st = datetime.strptime(start_time, "%H:%M").time()
            et = datetime.strptime(end_time, "%H:%M").time()
        except ValueError:
            raise ValueError("Invalid time format. Please use HH:MM.")

        if et <= st:
            raise ValueError("End time must be later than start time.")

        facility = db.session.get(Facility, facility_id)
        if not facility or not facility.is_active:
            raise ValueError("Facility unavailable or inactive")

        # Concurrency safety: check existing overlapping bookings for the same date and time range
        overlapping = (
            FacilityBooking.query.filter_by(
                facility_id=facility_id, booking_date=booking_date
            )
            .filter(FacilityBooking.status != "Cancelled")
            .filter(
                (
                    (FacilityBooking.start_time <= start_time)
                    & (FacilityBooking.end_time > start_time)
                )
                | (
                    (FacilityBooking.start_time < end_time)
                    & (FacilityBooking.end_time >= end_time)
                )
                | (
                    (FacilityBooking.start_time >= start_time)
                    & (FacilityBooking.end_time <= end_time)
                )
            )
            .with_for_update()
            .first()
        )

        if overlapping:
            raise ValueError(
                f"Slot {start_time} - {end_time} on {booking_date} is already booked"
            )

        booking = FacilityBooking(
            society_id=society_id,
            facility_id=facility_id,
            flat_id=flat_id,
            resident_id=resident_id,
            booking_date=booking_date,
            start_time=start_time,
            end_time=end_time,
            total_cost=facility.hourly_rate,
            purpose=purpose,
            notes=notes,
            status="Confirmed",
        )
        db.session.add(booking)
        db.session.commit()
        return booking

    @staticmethod
    def cancel_booking(booking_id, resident_id=None):
        booking = db.session.get(FacilityBooking, booking_id)
        if not booking:
            raise ValueError("Booking not found")

        if resident_id and booking.resident_id != resident_id:
            raise ValueError("Unauthorized to cancel this booking")

        booking.status = "Cancelled"
        db.session.commit()
        return booking

