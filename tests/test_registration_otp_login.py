<<<<<<< HEAD
from app.models import (
=======
﻿from app.models import (
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    db,
    User,
    Role,
    Society,
    Building,
    Block,
    Flat,
    RegistrationRequest,
)


def test_registration_otp_approval_then_password_login(client, app):
    with app.app_context():
        society = Society.query.first()
        building = Building.query.filter_by(society_id=society.id).first()
        block = Block.query.filter_by(building_id=building.id).first()
        flat = Flat.query.filter_by(block_id=block.id).first()
        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id
        society_id, building_id, block_id, flat_id = (
            society.id,
            building.id,
            block.id,
            flat.id,
        )

    registration = client.post(
        "/register",
        data={
            "full_name": "Complete Flow Resident",
            "mobile": "+91 98765 43210",
            "email": "complete-flow@example.com",
            "society_id": society_id,
            "building_id": building_id,
            "block_id": block_id,
            "flat_id": flat_id,
            "occupancy_type": "OWNER",
            "password": "FlowPassword123",
        },
    )
    assert registration.status_code == 302

    with app.app_context():
        user = User.query.filter_by(mobile="9876543210").one()
        request_id = RegistrationRequest.query.filter_by(user_id=user.id).one().id
        assert user.password_hash
        assert user.check_password("FlowPassword123")
        assert user.account_status == "PENDING_APPROVAL"

    otp_response = client.post("/otp-login", json={"mobile": "+91 98765 43210"})
    assert otp_response.status_code == 200
    otp_verify = client.post(
        "/verify-otp",
        data={
            "mobile": "91 98765 43210",
            "otp_code": otp_response.get_json()["dev_otp"],
        },
    )
    assert otp_verify.status_code == 302

    client.get("/logout")
    with client.session_transaction() as session:
        session["user_id"] = admin_id
        session["society_id"] = None
        session["role"] = Role.SUPER_ADMIN
    assert client.post(f"/admin/registrations/{request_id}/approve").status_code == 302

    with app.app_context():
        approved_user = db.session.get(User, user.id)
        assert approved_user.account_status == "ACTIVE"
        assert approved_user.is_active is True
        assert approved_user.check_password("FlowPassword123")
        assert approved_user.mobile == "9876543210"

    client.get("/logout")
    login = client.post(
        "/login",
        data={
            "mobile": "+91 98765 43210",
            "password": "FlowPassword123",
        },
    )
    assert login.status_code == 302
    assert login.headers["Location"].endswith("/dashboard")


def test_wrong_password_and_wrong_mobile_are_rejected(client, app):
    with app.app_context():
        user = User(
            full_name="Known Login User",
            mobile="9876501234",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        user.set_password("CorrectPassword123")
        db.session.add(user)
        db.session.commit()

    wrong_password = client.post(
        "/login",
        data={"mobile": "9876501234", "password": "WrongPassword123"},
        follow_redirects=True,
    )
    assert b"Invalid mobile number or password" in wrong_password.data
    wrong_mobile = client.post(
        "/login",
        data={"mobile": "9876509999", "password": "CorrectPassword123"},
        follow_redirects=True,
    )
    assert b"Invalid mobile number or password" in wrong_mobile.data


def test_pending_user_cannot_login_with_correct_password(client, app):
    with app.app_context():
        user = User(
            full_name="Pending Login User",
            mobile="9876505678",
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        user.set_password("CorrectPassword123")
        db.session.add(user)
        db.session.commit()

    response = client.post(
        "/login",
        data={"mobile": "9876505678", "password": "CorrectPassword123"},
        follow_redirects=True,
    )
    assert b"pending approval" in response.data.lower()


