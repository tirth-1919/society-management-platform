from werkzeug.security import generate_password_hash, check_password_hash
from app.models.tenant import db
from app.utils import utcnow


class Role:
    SUPER_ADMIN = "Super Admin"
    SOCIETY_ADMIN = "Society Admin"
    ADMIN = "Society Admin"
    RESIDENT = "Resident"
    SECURITY = "Security Staff"
    MAINTENANCE = "Maintenance Staff"
    VENDOR = "Vendor"

    ALL_ROLES = [SUPER_ADMIN, SOCIETY_ADMIN, RESIDENT, SECURITY, MAINTENANCE, VENDOR]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(
        db.String(80), unique=True, nullable=True
    )  # admin username, optional for residents
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )  # None for Super Admin
    full_name = db.Column(db.String(120), nullable=False)
    mobile = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default=Role.RESIDENT)
    is_active = db.Column(db.Boolean, default=True)
    account_status = db.Column(db.String(30), nullable=False, default="ACTIVE")
    last_login_at = db.Column(db.DateTime, nullable=True)
    two_factor_secret = db.Column(db.String(64), nullable=True)
    is_2fa_enabled = db.Column(db.Boolean, default=False)
    failed_login_attempts = db.Column(db.Integer, default=0)
    maintenance_start_month = db.Column(
        db.String(7), nullable=True
    )  # Format YYYY-MM e.g. 2026-08

    locked_until = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    society = db.relationship("Society", backref="users", lazy=True)
    residents = db.relationship("Resident", backref="user", lazy=True)
    sessions = db.relationship(
        "UserSession", backref="user", lazy=True, cascade="all, delete-orphan"
    )
    registration_requests = db.relationship(
        "RegistrationRequest",
        foreign_keys="RegistrationRequest.user_id",
        backref="user",
        lazy=True,
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class UserSession(db.Model):
    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    session_token = db.Column(db.String(128), unique=True, nullable=False, index=True)
    device_info = db.Column(db.String(255), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


class OTPLog(db.Model):
    __tablename__ = "otp_logs"

    id = db.Column(db.Integer, primary_key=True)
    mobile = db.Column(db.String(20), nullable=False, index=True)
    otp_code = db.Column(db.String(10), nullable=False)
    purpose = db.Column(db.String(50), default="LOGIN")  # LOGIN, PASS_RESET, 2FA
    created_at = db.Column(db.DateTime, default=utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    attempts = db.Column(db.Integer, default=0)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True
    )
    action = db.Column(
        db.String(100), nullable=False
    )  # LOGIN, BILL_CREATE, PAYMENT_RECORD, etc.
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    user = db.relationship("User", backref="audit_logs", lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
