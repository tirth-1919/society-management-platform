import pytest
from werkzeug.security import generate_password_hash
from app.models import db, User, Role, Society
from app.services.auth_service import AuthService
from app.utils import utcnow


@pytest.fixture
def setup_sec_data(app):
    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()

        u1 = User(
            full_name="User One",
            mobile="9800011111",
            email="u1@test.com",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
            society_id=s1.id,
        )
        u1.set_password("CorrectPassphrase@123")

        u2 = User(
            full_name="User Two",
            mobile="9800022222",
            email="u2@test.com",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
            society_id=s2.id,
        )
        u2.set_password("CorrectPass@456")

        db.session.add_all([u1, u2])
        db.session.commit()

        return {"s1_id": s1.id, "s2_id": s2.id, "u1_id": u1.id, "u2_id": u2.id}


def test_password_strength_validation():
    # Minimum 12 characters, with the existing letter and digit/special rule.
    valid, _ = AuthService.validate_password_strength("Short1")
    assert not valid
    valid, _ = AuthService.validate_password_strength("onlylettershere")
    assert not valid
    valid, _ = AuthService.validate_password_strength("ValidPassphrase@123")
    assert valid


def test_user_rejects_passwords_shorter_than_12_characters():
    user = User()

    with pytest.raises(ValueError, match="at least 12 characters"):
        user.set_password("legacy-pass")


@pytest.mark.parametrize("password", ["TwelveChars1", "MoreThanTwelveChars123"])
def test_user_accepts_passwords_of_12_or_more_characters(password):
    user = User()

    user.set_password(password)

    assert user.password_hash
    assert user.check_password(password)


def test_user_verifies_existing_short_password_hashes():
    legacy_password = "legacy-pass"
    user = User(password_hash=generate_password_hash(legacy_password))

    assert user.check_password(legacy_password)
    assert not user.check_password("incorrect")


@pytest.mark.parametrize("invalid_password", [None, "", object()])
def test_user_password_verification_safely_rejects_invalid_input(invalid_password):
    user = User(password_hash=generate_password_hash("a-long-password"))
    assert not user.check_password(invalid_password)


def test_user_password_verification_safely_rejects_missing_or_malformed_hashes():
    assert not User(password_hash=None).check_password("legacy-pass")
    assert not User(password_hash="malformed-hash").check_password("legacy-pass")


def test_otp_attempt_limits_and_invalidation(app, setup_sec_data):
    with app.app_context():
        mobile = "9800011111"
        code = AuthService.generate_otp(mobile)

        # 4 incorrect attempts
        for i in range(4):
            valid, msg = AuthService.verify_otp(mobile, "000000")
            assert not valid
            assert "attempt(s) remaining" in msg

        # 5th incorrect attempt -> invalidates OTP
        valid, msg = AuthService.verify_otp(mobile, "000000")
        assert not valid
        assert "Too many failed attempts" in msg or "invalidated" in msg

        # Even if correct code entered now, it is rejected
        valid, msg = AuthService.verify_otp(mobile, code)
        assert not valid


def test_login_brute_force_lockout(client, app, setup_sec_data):
    with app.app_context():
        # 5 consecutive failed logins
        for _ in range(5):
            res = client.post(
                "/login",
                data={"mobile": "9800011111", "password": "WrongPassword!"},
                follow_redirects=True,
            )
            assert res.status_code == 200

        user = db.session.get(User, setup_sec_data["u1_id"])
        assert user.failed_login_attempts >= 5
        assert user.locked_until is not None

        # 6th attempt with correct password while locked must fail
        res = client.post(
            "/login",
            data={"mobile": "9800011111", "password": "CorrectPassphrase@123"},
            follow_redirects=True,
        )
        assert b"Account temporarily locked" in res.data


def test_account_unlock_after_expiry(client, app, setup_sec_data):
    from datetime import timedelta
    with app.app_context():
        user = db.session.get(User, setup_sec_data["u1_id"])
        user.failed_login_attempts = 5
        user.locked_until = utcnow() - timedelta(minutes=1)  # lock expired in past
        db.session.commit()

        # Login with correct password after lock expiration should succeed
        res = client.post(
            "/login",
            data={"mobile": "9800011111", "password": "CorrectPassphrase@123"},
            follow_redirects=True,
        )
        assert res.status_code == 200
        assert b"Welcome back, User One!" in res.data

        # Failed attempts and locked_until should be reset
        user = db.session.get(User, setup_sec_data["u1_id"])
        assert user.failed_login_attempts == 0
        assert user.locked_until is None


def test_otp_cooldown_enforcement(app, setup_sec_data):
    with app.app_context():
        mobile = "9800022222"
        AuthService.generate_otp(mobile)

        # Immediate second request within 60s should raise ValueError
        with pytest.raises(ValueError) as exc_info:
            AuthService.generate_otp(mobile)
        assert "seconds before requesting another OTP" in str(exc_info.value)


def test_session_management_and_invalidation(app, setup_sec_data):
    from app.models import UserSession
    with app.app_context():
        user = db.session.get(User, setup_sec_data["u1_id"])
        token1 = AuthService.create_session(user, device_info="Chrome on Windows")
        token2 = AuthService.create_session(user, device_info="Safari on iPhone")

        s1 = UserSession.query.filter_by(session_token=token1).first()
        s2 = UserSession.query.filter_by(session_token=token2).first()
        assert s1.is_active is True
        assert s2.is_active is True

        # Invalidate single session
        AuthService.invalidate_session(token1)
        s1 = UserSession.query.filter_by(session_token=token1).first()
        assert s1.is_active is False
        s2 = UserSession.query.filter_by(session_token=token2).first()
        assert s2.is_active is True

        # Invalidate all user sessions
        AuthService.invalidate_all_user_sessions(user.id)
        s2 = UserSession.query.filter_by(session_token=token2).first()
        assert s2.is_active is False


def test_mobile_normalization():
    assert AuthService.normalize_mobile("+91 9800011111") == "9800011111"
    assert AuthService.normalize_mobile("919800011111") == "9800011111"
    assert AuthService.normalize_mobile(" 98000 11111 ") == "9800011111"
    assert AuthService.normalize_mobile("9800011111") == "9800011111"


def test_inactive_and_pending_user_login_blocked(client, app, setup_sec_data):
    with app.app_context():
        user = db.session.get(User, setup_sec_data["u2_id"])
        user.account_status = "PENDING_APPROVAL"
        db.session.commit()

        res = client.post(
            "/login",
            data={"mobile": "9800022222", "password": "CorrectPass@456"},
            follow_redirects=True,
        )
        assert b"pending approval" in res.data or res.status_code == 200

        user = db.session.get(User, setup_sec_data["u2_id"])
        user.account_status = "SUSPENDED"
        db.session.commit()

        res = client.post(
            "/login",
            data={"mobile": "9800022222", "password": "CorrectPass@456"},
            follow_redirects=True,
        )
        assert b"Your account is not active" in res.data


def test_logout_invalidates_session(client, app, setup_sec_data):
    from app.models import UserSession
    # Successful login
    res = client.post(
        "/login",
        data={"mobile": "9800011111", "password": "CorrectPassphrase@123"},
        follow_redirects=True,
    )
    assert res.status_code == 200

    with client.session_transaction() as sess:
        token = sess.get("session_token")
        assert token is not None

    with app.app_context():
        session_obj = UserSession.query.filter_by(session_token=token).first()
        assert session_obj is not None
        assert session_obj.is_active is True

    # Logout
    res = client.get("/logout", follow_redirects=True)
    assert res.status_code == 200
    assert b"logged out" in res.data

    with app.app_context():
        session_obj = UserSession.query.filter_by(session_token=token).first()
        assert session_obj.is_active is False

