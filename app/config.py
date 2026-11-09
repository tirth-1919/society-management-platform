import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from project root.
# Existing system environment variables take priority.
load_dotenv(BASE_DIR / ".env", override=False)


class Config:
    # Never use a predictable production signing key.
    SECRET_KEY = os.environ.get("SECRET_KEY") or (
        "development-only-" + os.urandom(32).hex()
    )

    # Database Configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'instance' / 'society_saas.db'}"
    )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Auth & Security
    OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", 5))
    MAX_LOGIN_ATTEMPTS = 5

    SESSION_COOKIE_NAME = os.environ.get(
        "SESSION_COOKIE_NAME",
        "society_user_session"
    )

    ADMIN_SESSION_COOKIE_NAME = os.environ.get(
        "ADMIN_SESSION_COOKIE_NAME",
        "society_admin_session"
    )

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800

    # Maintenance Billing Defaults
    MONTHLY_MAINTENANCE = float(
        os.environ.get("MONTHLY_MAINTENANCE", 1500.0)
    )
    LATE_FEE_PER_MONTH = float(
        os.environ.get("LATE_FEE_PER_MONTH", 500.0)
    )
    MAINTENANCE_DUE_DAY = int(
        os.environ.get("MAINTENANCE_DUE_DAY", 10)
    )
    MAINTENANCE_REMINDER_DAYS = int(
        os.environ.get("MAINTENANCE_REMINDER_DAYS", 3)
    )
    MAINTENANCE_DEFAULT_START_MONTH = os.environ.get(
        "MAINTENANCE_DEFAULT_START_MONTH"
    )

    ADMIN_DEV_PASSWORD = os.environ.get("ADMIN_DEV_PASSWORD")

    # Optional single-society restriction.
    # Configure only if the application requires it.
    SINGLE_SOCIETY_ID = (
        int(os.environ["SINGLE_SOCIETY_ID"])
        if os.environ.get("SINGLE_SOCIETY_ID")
        else None
    )

    # Payment Provider Configuration
    PAYMENT_PROVIDER = os.environ.get("PAYMENT_PROVIDER", "Mock")

    RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID", "mock_key_id")
    RAZORPAY_KEY_SECRET = os.environ.get(
        "RAZORPAY_KEY_SECRET",
        "mock_key_secret"
    )
    RAZORPAY_WEBHOOK_SECRET = os.environ.get(
        "RAZORPAY_WEBHOOK_SECRET",
        ""
    )

    CASHFREE_APP_ID = os.environ.get("CASHFREE_APP_ID", "")
    CASHFREE_SECRET_KEY = os.environ.get("CASHFREE_SECRET_KEY", "")

    PAYU_MERCHANT_KEY = os.environ.get("PAYU_MERCHANT_KEY", "")
    PAYU_MERCHANT_SALT = os.environ.get("PAYU_MERCHANT_SALT", "")

    # Public Application URL
    APP_URL = os.environ.get("APP_URL", "")

    # OTP & Notification Configuration
    NOTIFICATION_PROVIDER = os.environ.get(
        "NOTIFICATION_PROVIDER",
        "Console"
    )

    # Storage Directories
    INSTANCE_DIR = BASE_DIR / "instance"

    BACKUP_DIR = Path(
        os.environ.get("BACKUP_DIR", str(INSTANCE_DIR / "backups"))
    )

    DOCUMENT_STORAGE_DIR = Path(
        os.environ.get(
            "DOCUMENT_STORAGE_DIR",
            str(INSTANCE_DIR / "documents")
        )
    )

    EVENT_PHOTO_STORAGE_DIR = Path(
        os.environ.get(
            "EVENT_PHOTO_STORAGE_DIR",
            str(INSTANCE_DIR / "event_photos")
        )
    )

    EVENT_PHOTO_MAX_SIZE_MB = int(
        os.environ.get("EVENT_PHOTO_MAX_SIZE_MB", 10)
    )
    EVENT_PHOTO_MAX_PER_UPLOAD = int(
        os.environ.get("EVENT_PHOTO_MAX_PER_UPLOAD", 10)
    )
    EVENT_PHOTO_ALLOWED_EXTENSIONS = frozenset(
        os.environ.get(
            "EVENT_PHOTO_ALLOWED_EXTENSIONS",
            "jpg,jpeg,png,webp"
        ).lower().split(",")
    )

    EVENT_VIDEO_MAX_SIZE_MB = int(
        os.environ.get("EVENT_VIDEO_MAX_SIZE_MB", 100)
    )
    EVENT_VIDEO_ALLOWED_EXTENSIONS = frozenset(
        os.environ.get(
            "EVENT_VIDEO_ALLOWED_EXTENSIONS",
            "mp4,webm,mov"
        ).lower().split(",")
    )
    EVENT_VIDEO_ALLOWED_MIME_TYPES = frozenset(
        os.environ.get(
            "EVENT_VIDEO_ALLOWED_MIME_TYPES",
            "video/mp4,video/webm,video/quicktime"
        ).lower().split(",")
    )

    EVENT_PHOTO_MAX_PER_USER_EVENT = int(
        os.environ.get("EVENT_PHOTO_MAX_PER_USER_EVENT", 50)
    )
    EVENT_PHOTO_MAX_EVENT_TOTAL = int(
        os.environ.get("EVENT_PHOTO_MAX_EVENT_TOTAL", 0)
    )
    EVENT_PHOTO_STORAGE_QUOTA_MB = int(
        os.environ.get("EVENT_PHOTO_STORAGE_QUOTA_MB", 0)
    )
    EVENT_PHOTO_MAX_WIDTH = int(
        os.environ.get("EVENT_PHOTO_MAX_WIDTH", 8000)
    )
    EVENT_PHOTO_MAX_HEIGHT = int(
        os.environ.get("EVENT_PHOTO_MAX_HEIGHT", 8000)
    )

    # AI Configuration
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "deterministic")
    AI_API_KEY = os.environ.get("AI_API_KEY", "")
    AI_MODEL = os.environ.get("AI_MODEL", "gpt-3.5-turbo")
    AI_TEMPERATURE = float(os.environ.get("AI_TEMPERATURE", "0.7"))
    AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "500"))
    AI_TIMEOUT_SECONDS = int(
        os.environ.get("AI_TIMEOUT_SECONDS", "30")
    )


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
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True


config = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}