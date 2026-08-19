<<<<<<< HEAD
from app.models.tenant import db
from app.utils import utcnow
=======
﻿from datetime import datetime
from app.models.tenant import db
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class Notice(db.Model):
    __tablename__ = "notices"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(150), nullable=False)
    content = db.Column(db.Text, nullable=False)
    notice_type = db.Column(
        db.String(50), default="General"
    )  # General, Maintenance, Water, Meeting, Emergency
    priority = db.Column(db.String(20), default="Normal")  # Normal, High, Urgent
    audience = db.Column(
        db.String(50), default="All"
    )  # All, Owners, Tenants, Building A
    attachment_url = db.Column(db.String(255), nullable=True)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

=======
    publish_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiry_date = db.Column(db.DateTime, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

class SocietyMeeting(db.Model):
    __tablename__ = "society_meetings"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    title = db.Column(db.String(150), nullable=False)
    agenda = db.Column(db.Text, nullable=False)
    meeting_date = db.Column(db.DateTime, nullable=False)
    location = db.Column(db.String(100), default="Clubhouse / Online")
    minutes_of_meeting = db.Column(db.Text, nullable=True)
<<<<<<< HEAD
    created_at = db.Column(db.DateTime, default=utcnow)
=======
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class PollVote(db.Model):
    __tablename__ = "poll_votes"

    id = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(
        db.Integer, db.ForeignKey("society_meetings.id"), nullable=False, index=True
    )
    flat_id = db.Column(db.Integer, db.ForeignKey("flats.id"), nullable=False)
    resident_id = db.Column(db.Integer, db.ForeignKey("residents.id"), nullable=False)
    vote_choice = db.Column(db.String(50), nullable=False)  # In Favor, Against, Abstain
<<<<<<< HEAD
    voted_at = db.Column(db.DateTime, default=utcnow)
=======
    voted_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


class EmergencyAlert(db.Model):
    __tablename__ = "emergency_alerts"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    alert_type = db.Column(
        db.String(50), nullable=False
    )  # FIRE, MEDICAL, SECURITY, WATER_LEAK, LIFT_TRAPPED
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.Text, nullable=False)
    location_details = db.Column(db.String(150), nullable=True)
    triggered_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
<<<<<<< HEAD
    triggered_at = db.Column(db.DateTime, default=utcnow)
=======
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    is_active = db.Column(db.Boolean, default=True)



