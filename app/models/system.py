from datetime import datetime
from app.models.tenant import db


class BackupLog(db.Model):
    __tablename__ = "backup_logs"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(150), nullable=False)
    file_path = db.Column(db.String(255), nullable=False)
    file_size_bytes = db.Column(db.Integer, default=0)
    backup_type = db.Column(db.String(30), default="Scheduled")  # Scheduled, Manual
    status = db.Column(db.String(20), default="Completed")  # Completed, Failed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class NotificationLog(db.Model):
    __tablename__ = "notification_logs"
    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "billing_month",
            "notification_type",
            name="uq_notification_log_user_month_type",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    recipient_mobile_or_email = db.Column(db.String(120), nullable=False)
    channel = db.Column(
        db.String(20), nullable=False
    )  # Email, SMS, Push, WhatsApp, In-App
    notification_type = db.Column(
        db.String(50), nullable=True, index=True
    )  # MONTHLY_BILL, UPCOMING_REMINDER, OVERDUE_REMINDER, PAYMENT_CONFIRMATION
    billing_month = db.Column(db.String(7), nullable=True, index=True)  # Format YYYY-MM
    subject = db.Column(db.String(150), nullable=True)
    message = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="Sent")  # Sent, Delivered, Failed
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    retry_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship("User", backref="notification_logs", lazy=True)


class SystemSetting(db.Model):
    __tablename__ = "system_settings"

    id = db.Column(db.Integer, primary_key=True)
    setting_key = db.Column(db.String(100), unique=True, nullable=False)
    setting_value = db.Column(db.Text, nullable=True)
    description = db.Column(db.String(255), nullable=True)



