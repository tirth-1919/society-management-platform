<<<<<<< HEAD
from app.utils import utcnow
from datetime import timedelta
=======
﻿from app.utils import utcnow
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
    def reopen_complaint(complaint_id, user_id, reason):
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            raise ValueError("Complaint not found")

        complaint.status = "In Progress"
        complaint.resolved_at = None
        db.session.commit()

        comment_text = f"Ticket reopened: {reason}"
        ComplaintService.add_comment(complaint_id, user_id, comment_text)
        return complaint

    @staticmethod
    def escalate_complaint(complaint_id, user_id, reason):
        complaint = db.session.get(Complaint, complaint_id)
        if not complaint:
            raise ValueError("Complaint not found")

        complaint.priority = "Emergency"
        db.session.commit()

        comment_text = f"Ticket escalated to Emergency: {reason}"
        ComplaintService.add_comment(complaint_id, user_id, comment_text)
        return complaint

    @staticmethod
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    def add_comment(complaint_id, user_id, comment_text):
        comment = ComplaintComment(
            complaint_id=complaint_id, user_id=user_id, comment=comment_text
        )
        db.session.add(comment)
        db.session.commit()
        return comment

<<<<<<< HEAD
    @staticmethod
    def check_sla_breach(complaint):
        """Returns True if the complaint SLA has been breached."""
        sla_hours = {
            "Emergency": 6,
            "High": 24,
            "Medium": 48,
            "Low": 72,
        }
        max_hours = sla_hours.get(complaint.priority, 48)
        now = utcnow()
        created = complaint.created_at or now

        if complaint.status in ["Resolved", "Closed"]:
            end_time = complaint.resolved_at or now
            return (end_time - created) > timedelta(hours=max_hours)
        return (now - created) > timedelta(hours=max_hours)


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

