from app.models.tenant import db
from app.utils import utcnow


class NotificationPreference(db.Model):
    """One row per resident. Mandatory/security notifications (account
    status changes, password changes, payment success confirmations of
    record) are never gated by these flags â€” they only control optional,
    convenience notification types.
    """

    __tablename__ = "notification_preferences"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=False, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, unique=True, index=True
    )
    resident_id = db.Column(
        db.Integer, db.ForeignKey("residents.id"), nullable=True, index=True
    )

    maintenance_reminders = db.Column(db.Boolean, default=True, nullable=False)
    payment_reminders = db.Column(db.Boolean, default=True, nullable=False)
    payment_confirmations = db.Column(db.Boolean, default=True, nullable=False)
    announcements = db.Column(db.Boolean, default=True, nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    user = db.relationship(
        "User", backref=db.backref("notification_preference", uselist=False), lazy=True
    )

    @staticmethod
    def get_or_create(user_id, society_id, resident_id=None):
        """Read-or-default helper. Defaults preserve current (all-on)
        notification behaviour, so existing residents see no change until
        they actively opt out of something.
        """
        pref = NotificationPreference.query.filter_by(user_id=user_id).first()
        if pref:
            return pref
        pref = NotificationPreference(
            user_id=user_id, society_id=society_id, resident_id=resident_id
        )
        db.session.add(pref)
        db.session.commit()
        return pref



