import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "default-dev-saas-secret-key-3910283019")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'instance' / 'society_saas.db'}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth & Security
    OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", 5))
    MAX_LOGIN_ATTEMPTS = 5
    SESSION_COOKIE_NAME = os.environ.get("SESSION_COOKIE_NAME", "society_user_session")
    ADMIN_SESSION_COOKIE_NAME = os.environ.get(
        "ADMIN_SESSION_COOKIE_NAME", "society_admin_session"
    )
    SESSION_COOKIE_SAMESITE = "Lax"

    # Maintenance Billing Defaults (Centralized Configuration)
    MONTHLY_MAINTENANCE = float(os.environ.get("MONTHLY_MAINTENANCE", 1500.0))
    LATE_FEE_PER_MONTH = float(os.environ.get("LATE_FEE_PER_MONTH", 500.0))
    MAINTENANCE_DUE_DAY = int(os.environ.get("MAINTENANCE_DUE_DAY", 10))
    MAINTENANCE_REMINDER_DAYS = int(os.environ.get("MAINTENANCE_REMINDER_DAYS", 3))
    MAINTENANCE_DEFAULT_START_MONTH = os.environ.get("MAINTENANCE_DEFAULT_START_MONTH")
    ADMIN_DEV_PASSWORD = os.environ.get("ADMIN_DEV_PASSWORD", "admin@123")

    # Payment Provider Abstraction
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "Mock")
    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "mock_key_id")
    RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET", "mock_key_secret")

    # Public URL used for QR portal access. Left blank in development so the
    # QR route falls back to the incoming request's own host (works for
    # localhost and any ngrok tunnel automatically). Set explicitly in
    # production so the QR always encodes the real domain regardless of
    # what host header a request arrives on (e.g. behind a proxy).
    APP_URL = os.environ.get("APP_URL", "")

    # Directories
    INSTANCE_DIR = BASE_DIR / "instance"
    BACKUP_DIR = BASE_DIR / "instance" / "backups"
    DOCUMENT_STORAGE_DIR = BASE_DIR / "instance" / "documents"


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
