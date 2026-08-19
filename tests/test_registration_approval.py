<<<<<<< HEAD
from app.models import db, User, Role, Society, Building, Flat, RegistrationRequest
=======
﻿from app.models import db, User, Role, Society, Building, Flat, RegistrationRequest
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


def test_registration_request_no_password(client, app):
    with app.app_context():
        s = Society.query.first()
        b = Building.query.filter_by(society_id=s.id).first()
        f = Flat.query.filter_by(building_id=b.id).first()
        sid, bid, fid = s.id, b.id, f.id

    res = client.post(
        "/register",
        data={
            "full_name": "New Resident",
            "mobile": "9898989898",
            "email": "newres@test.com",
            "society_id": sid,
            "building_id": bid,
            "flat_id": fid,
            "occupancy_type": "OWNER",
            "password": "MySecretPassword123",
        },
        follow_redirects=True,
    )
    assert res.status_code == 200

    with app.app_context():
        req = RegistrationRequest.query.filter_by(mobile="9898989898").first()
        assert req is not None
        assert req.status == "PENDING_APPROVAL"
        # Verify RegistrationRequest table has no password attribute
        assert not hasattr(req, "password")
        assert not hasattr(req, "password_hash")

        # Verify password is in User model
        user = db.session.get(User, req.user_id)
        assert user is not None
        assert user.account_status == "PENDING_APPROVAL"
        assert user.check_password("MySecretPassword123")


def test_hierarchy_mismatch_returns_403(client, app):
    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()
        b2 = Building.query.filter_by(society_id=s2.id).first()
        f2 = Flat.query.filter_by(building_id=b2.id).first()

    # Pass s1.id with b2.id (b2 belongs to s2, not s1) -> MUST RETURN 403
    res = client.post(
        "/register",
        data={
            "full_name": "Hacker",
            "mobile": "9998887776",
            "society_id": s1.id,
            "building_id": b2.id,
            "flat_id": f2.id,
            "occupancy_type": "TENANT",
            "password": "Password123",
        },
    )
    assert res.status_code == 403


def test_admin_approve_and_reject_flow(client, app):
    with app.app_context():
        s = Society.query.first()
        b = Building.query.filter_by(society_id=s.id).first()
        f = Flat.query.filter_by(building_id=b.id).first()

        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id

        # Registration 1: for approval
        u1 = User(
            full_name="Approve Test",
            mobile="9797979797",
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        u1.set_password("Pass123")
        db.session.add(u1)

        # Registration 2: for rejection
        u2 = User(
            full_name="Reject Test",
            mobile="9696969696",
            role=Role.RESIDENT,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        u2.set_password("Pass123")
        db.session.add(u2)
        db.session.commit()

        req1 = RegistrationRequest(
            user_id=u1.id,
            society_id=s.id,
            building_id=b.id,
            flat_id=f.id,
            full_name="Approve Test",
            mobile="9797979797",
            occupancy_type="TENANT",
            status="PENDING_APPROVAL",
        )
        req2 = RegistrationRequest(
            user_id=u2.id,
            society_id=s.id,
            building_id=b.id,
            flat_id=f.id,
            full_name="Reject Test",
            mobile="9696969696",
            occupancy_type="FAMILY_MEMBER",
            status="PENDING_APPROVAL",
        )
        db.session.add_all([req1, req2])
        db.session.commit()

        req1_id = req1.id
        req2_id = req2.id

    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["role"] = Role.SUPER_ADMIN

    # Test Approve
    res_app = client.post(
        f"/admin/registrations/{req1_id}/approve", follow_redirects=True
    )
    assert res_app.status_code == 200

    with app.app_context():
        req1_updated = db.session.get(RegistrationRequest, req1_id)
        assert req1_updated.status == "APPROVED"
        u1_updated = db.session.get(User, req1_updated.user_id)
        assert u1_updated.account_status == "ACTIVE"
        assert u1_updated.is_active is True

    # Test Reject
    res_rej = client.post(
        f"/admin/registrations/{req2_id}/reject",
        data={"rejection_reason": "Invalid document"},
        follow_redirects=True,
    )
    assert res_rej.status_code == 200

    with app.app_context():
        req2_updated = db.session.get(RegistrationRequest, req2_id)
        assert req2_updated.status == "REJECTED"
        assert req2_updated.rejection_reason == "Invalid document"
        u2_updated = db.session.get(User, req2_updated.user_id)
        assert u2_updated.account_status == "REJECTED"
        assert u2_updated.is_active is False


def test_duplicate_active_mobile_blocked(client, app):
    with app.app_context():
        s = Society.query.first()
        b = Building.query.filter_by(society_id=s.id).first()
        f = Flat.query.filter_by(building_id=b.id).first()
        sid, bid, fid = s.id, b.id, f.id

        u = User(
            full_name="Existing Active",
            mobile="9595959595",
            role=Role.RESIDENT,
            account_status="ACTIVE",
            is_active=True,
        )
        u.set_password("Pass123")
        db.session.add(u)
        db.session.commit()

    res = client.post(
        "/register",
        data={
            "full_name": "Duplicate Person",
            "mobile": "9595959595",
            "society_id": sid,
            "building_id": bid,
            "flat_id": fid,
            "occupancy_type": "OWNER",
            "password": "Pass1234",
        },
        follow_redirects=True,
    )
    assert b"Mobile number already registered and active" in res.data

