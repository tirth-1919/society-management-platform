from app.utils import utcnow
import secrets
from app.models import db, Complaint, ComplaintComment


class ComplaintService:
    @staticmethod
    def create_complaint(
        society_id,
        flat_id,
        resident_id,
        category,
        title,
        description,
        priority="Medium",
    ):
        ticket_num = f"TICK-{society_id}-{secrets.token_hex(4).upper()}"
        complaint = Complaint(
            ticket_number=ticket_num,
            society_id=society_id,
            flat_id=flat_id,
            resident_id=resident_id,
            category=category,
            title=title,
            description=description,
            priority=priority,
            status="Submitted",
        )
        db.session.add(complaint)
        db.session.commit()
        return complaint

    @staticmethod
    def assign_staff(complaint_id, staff_user_id):
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            raise ValueError("Complaint not found")

        complaint.assigned_staff_id = staff_user_id
        complaint.status = "Assigned"
        db.session.commit()
        return complaint

    @staticmethod
    def update_status(complaint_id, new_status, resolution_notes=None):
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            raise ValueError("Complaint not found")

        valid_statuses = ["Submitted", "Assigned", "In Progress", "Resolved", "Closed"]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status {new_status}")

        complaint.status = new_status
        if resolution_notes:
            complaint.resolution_notes = resolution_notes
        if new_status in ["Resolved", "Closed"]:
            complaint.resolved_at = utcnow()

        db.session.commit()
        return complaint

    @staticmethod
    def add_comment(complaint_id, user_id, comment_text):
        comment = ComplaintComment(
            complaint_id=complaint_id, user_id=user_id, comment=comment_text
        )
        db.session.add(comment)
        db.session.commit()
        return comment


