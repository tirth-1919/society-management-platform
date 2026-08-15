from app.utils import utcnow
import random
from app.models import db, Visitor, PreApprovedPass


class VisitorService:
    @staticmethod
    def create_pre_approved_pass(
        society_id,
        flat_id,
        resident_id,
        visitor_name,
        mobile,
        expected_date,
        purpose="Guest",
    ):
        """Resident generates a pre-approved visitor pass code."""
        pass_code = f"PASS{random.randint(1000, 9999)}"
        pass_entry = PreApprovedPass(
            pass_code=pass_code,
            society_id=society_id,
            flat_id=flat_id,
            resident_id=resident_id,
            visitor_name=visitor_name,
            mobile=mobile,
            expected_date=expected_date,
            purpose=purpose,
            is_used=False,
        )
        db.session.add(pass_entry)
        db.session.commit()
        return pass_entry

    @staticmethod
    def verify_and_checkin_pass(pass_code, society_id):
        """Security verifies pre-approved pass code and registers gate entry."""
        pass_entry = PreApprovedPass.query.filter_by(
            pass_code=pass_code, society_id=society_id, is_used=False
        ).first()

        if not pass_entry:
            return False, "Invalid or already used pass code", None

        pass_entry.is_used = True

        visitor = Visitor(
            society_id=society_id,
            flat_id=pass_entry.flat_id,
            resident_id=pass_entry.resident_id,
            visitor_name=pass_entry.visitor_name,
            mobile=pass_entry.mobile,
            purpose=pass_entry.purpose,
            pass_code=pass_code,
            approval_status="Approved",
            entry_time=utcnow(),
        )
        db.session.add(visitor)
        db.session.commit()
        return True, "Pass verified successfully", visitor

    @staticmethod
    def log_visitor_entry(
        society_id,
        flat_id,
        visitor_name,
        mobile,
        purpose="Guest",
        vehicle_number=None,
        resident_id=None,
    ):
        """Security logs an ad-hoc visitor entry at the gate."""
        visitor = Visitor(
            society_id=society_id,
            flat_id=flat_id,
            resident_id=resident_id,
            visitor_name=visitor_name,
            mobile=mobile,
            purpose=purpose,
            vehicle_number=vehicle_number,
            approval_status="Approved",
            entry_time=utcnow(),
        )
        db.session.add(visitor)
        db.session.commit()
        return visitor

    @staticmethod
    def log_visitor_exit(visitor_id):
        """Security logs visitor departure."""
        visitor = db.session.get(Visitor, visitor_id)
        if not visitor:
            raise ValueError("Visitor record not found")

        visitor.exit_time = utcnow()
        db.session.commit()
        return visitor


