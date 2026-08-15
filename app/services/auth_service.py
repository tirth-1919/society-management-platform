from app.utils import utcnow
import random
import secrets
from datetime import timedelta
from app.models import db, UserSession, OTPLog, AuditLog


class AuthService:
    OTP_EXPIRY_MINUTES = 5

    @staticmethod
    def normalize_mobile(mobile):
        """Return the application's canonical mobile representation."""
        value = "".join(str(mobile or "").split())
        if value.startswith("+91"):
            value = value[3:]
        elif value.startswith("91") and len(value) == 12:
            value = value[2:]
        return value

    @staticmethod
    def generate_otp(mobile, purpose="LOGIN"):
        """Generates a 6-digit OTP code valid for 5 minutes."""
        mobile = AuthService.normalize_mobile(mobile)
        code = f"{random.randint(100000, 999999)}"
        expires_at = utcnow() + timedelta(
            minutes=AuthService.OTP_EXPIRY_MINUTES
        )

        # Invalidate previous unexpired OTPs for this mobile
        OTPLog.query.filter_by(mobile=mobile, is_used=False).update({"is_used": True})

        otp_entry = OTPLog(
            mobile=mobile,
            otp_code=code,
            purpose=purpose,
            expires_at=expires_at,
            is_used=False,
        )
        db.session.add(otp_entry)
        db.session.commit()
        return code

    @staticmethod
    def verify_otp(mobile, code, purpose="LOGIN"):
        """Verifies OTP code with expiry and single-use logic."""
        mobile = AuthService.normalize_mobile(mobile)
        otp_entry = (
            OTPLog.query.filter_by(
                mobile=mobile, otp_code=code, purpose=purpose, is_used=False
            )
            .order_by(OTPLog.created_at.desc())
            .first()
        )

        if not otp_entry:
            return False, "Invalid OTP code"

        if utcnow() > otp_entry.expires_at:
            return False, "OTP has expired"

        otp_entry.is_used = True
        db.session.commit()
        return True, "OTP verified successfully"

    @staticmethod
    def create_session(user, device_info="Web Browser", ip_address=None):
        """Creates a new tracked user session."""
        token = secrets.token_hex(32)
        expires_at = utcnow() + timedelta(days=7)

        user_session = UserSession(
            user_id=user.id,
            session_token=token,
            device_info=device_info,
            ip_address=ip_address,
            expires_at=expires_at,
            is_active=True,
        )
        db.session.add(user_session)

        # Record audit log
        audit = AuditLog(
            society_id=user.society_id,
            user_id=user.id,
            action="LOGIN_SUCCESS",
            details=f"Logged in from {device_info}",
            ip_address=ip_address,
        )
        db.session.add(audit)
        db.session.commit()
        return token

    @staticmethod
    def invalidate_session(session_token):
        """Logs out a single session."""
        s = UserSession.query.filter_by(
            session_token=session_token, is_active=True
        ).first()
        if s:
            s.is_active = False
            db.session.commit()

    @staticmethod
    def invalidate_all_user_sessions(user_id):
        """Logs out user from all devices."""
        UserSession.query.filter_by(user_id=user_id, is_active=True).update(
            {"is_active": False}
        )
        db.session.commit()

