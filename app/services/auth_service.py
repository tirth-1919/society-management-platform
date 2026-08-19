<<<<<<< HEAD
from app.utils import utcnow
import secrets
import re
=======
﻿from app.utils import utcnow
import random
import secrets
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
from datetime import timedelta
from app.models import db, UserSession, OTPLog, AuditLog


class AuthService:
    OTP_EXPIRY_MINUTES = 5
<<<<<<< HEAD
    OTP_COOLDOWN_SECONDS = 60
    MAX_HOURLY_OTPS = 10
    MAX_OTP_ATTEMPTS = 5
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

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
<<<<<<< HEAD
    def validate_password_strength(password):
        """Validates password meets minimum security requirements."""
        if not password or len(password) < 8:
            return False, "Password must be at least 8 characters long."
        if not re.search(r"[A-Za-z]", password):
            return False, "Password must contain at least one letter."
        if not re.search(r"[\d@$!%*#?&]", password):
            return False, "Password must contain at least one number or special character."
        return True, "Password is valid."

    @staticmethod
    def generate_otp(mobile, purpose="LOGIN"):
        """Generates a 6-digit cryptographically secure OTP code valid for 5 minutes."""
        mobile = AuthService.normalize_mobile(mobile)

        # Check cooldown
        recent_otp = (
            OTPLog.query.filter_by(mobile=mobile, is_used=False)
            .order_by(OTPLog.created_at.desc())
            .first()
        )
        if recent_otp and (utcnow() - recent_otp.created_at).total_seconds() < AuthService.OTP_COOLDOWN_SECONDS:
            raise ValueError(f"Please wait {AuthService.OTP_COOLDOWN_SECONDS} seconds before requesting another OTP.")

        # Rate limit per hour
        one_hour_ago = utcnow() - timedelta(hours=1)
        recent_count = OTPLog.query.filter(
            OTPLog.mobile == mobile, OTPLog.created_at >= one_hour_ago
        ).count()
        if recent_count >= AuthService.MAX_HOURLY_OTPS:
            raise ValueError("Too many OTP requests. Please try again later.")

        code = f"{secrets.randbelow(900000) + 100000:06d}"
=======
    def generate_otp(mobile, purpose="LOGIN"):
        """Generates a 6-digit OTP code valid for 5 minutes."""
        mobile = AuthService.normalize_mobile(mobile)
        code = f"{random.randint(100000, 999999)}"
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
            attempts=0,
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        )
        db.session.add(otp_entry)
        db.session.commit()
        return code

    @staticmethod
    def verify_otp(mobile, code, purpose="LOGIN"):
<<<<<<< HEAD
        """Verifies OTP code with expiry, attempt limit, and single-use logic."""
        mobile = AuthService.normalize_mobile(mobile)
        otp_entry = (
            OTPLog.query.filter_by(
                mobile=mobile, purpose=purpose, is_used=False
=======
        """Verifies OTP code with expiry and single-use logic."""
        mobile = AuthService.normalize_mobile(mobile)
        otp_entry = (
            OTPLog.query.filter_by(
                mobile=mobile, otp_code=code, purpose=purpose, is_used=False
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            )
            .order_by(OTPLog.created_at.desc())
            .first()
        )

        if not otp_entry:
            return False, "Invalid OTP code"

        if utcnow() > otp_entry.expires_at:
<<<<<<< HEAD
            otp_entry.is_used = True
            db.session.commit()
            return False, "OTP has expired"

        otp_entry.attempts = (otp_entry.attempts or 0) + 1

        if str(otp_entry.otp_code).strip() != str(code or "").strip():
            if otp_entry.attempts >= AuthService.MAX_OTP_ATTEMPTS:
                otp_entry.is_used = True
                db.session.commit()
                return False, "Too many failed attempts. OTP has been invalidated. Please request a new OTP."
            db.session.commit()
            remaining = AuthService.MAX_OTP_ATTEMPTS - otp_entry.attempts
            return False, f"Invalid OTP code. {remaining} attempt(s) remaining."

=======
            return False, "OTP has expired"

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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

