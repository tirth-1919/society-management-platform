from app.models import db, Facility, FacilityBooking


class FacilityBookingService:
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
    ):
        """
        Books a facility slot with atomic database locking to prevent double booking collisions.
        """
        facility = db.session.get(Facility, facility_id)
        if not facility or not facility.is_active:
            raise ValueError("Facility unavailable or inactive")

        # Concurrency safety: check existing overlapping bookings for the same date and time range
        overlapping = (
            FacilityBooking.query.filter_by(
                facility_id=facility_id, booking_date=booking_date, status="Confirmed"
            )
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

