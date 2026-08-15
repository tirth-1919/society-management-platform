import pytest
from app.models import db, User, Role, Society, Building, Flat, RegistrationRequest


def test_cross_society_admin_approval_forbidden(client, app):
    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()
        b2 = Building.query.filter_by(society_id=s2.id).first()
        f2 = Flat.query.filter_by(building_id=b2.id).first()

        # Society Admin for Society 1
        soc1_admin = User(
            username="admin_soc1",
            full_name="Admin Soc 1",
            mobile="9111111111",
            role=Role.SOCIETY_ADMIN,
            society_id=s1.id,
            account_status="ACTIVE",
            is_active=True,
        )
        soc1_admin.set_password("Admin@123")
        db.session.add(soc1_admin)

        # User registering for Society 2
        u2 = User(
            full_name="User Soc 2",
            mobile="9222222222",
            role=Role.RESIDENT,
            society_id=s2.id,
            account_status="PENDING_APPROVAL",
            is_active=False,
        )
        u2.set_password("Pass123")
        db.session.add(u2)
        db.session.commit()

        req2 = RegistrationRequest(
            user_id=u2.id,
            society_id=s2.id,
            building_id=b2.id,
            flat_id=f2.id,
            full_name="User Soc 2",
            mobile="9222222222",
            occupancy_type="OWNER",
            status="PENDING_APPROVAL",
        )
        db.session.add(req2)
        db.session.commit()

        req2_id = req2.id
        admin1_id = soc1_admin.id
        s1_id = s1.id

    # Log in as Society 1 Admin
    with client.session_transaction() as sess:
        sess["user_id"] = admin1_id
        sess["society_id"] = s1_id
        sess["role"] = Role.SOCIETY_ADMIN

    # Try approving Society 2 registration -> MUST RETURN 403 Forbidden
    res = client.post(f"/admin/registrations/{req2_id}/approve")
    assert res.status_code == 403


def test_tenant_service_isolation_enforcement(app):
    from app.services.tenant_service import TenantService
    from werkzeug.exceptions import HTTPException

    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()

        user1 = User(
            full_name="User 1",
            mobile="9100000099",
            role=Role.RESIDENT,
            society_id=s1.id,
            account_status="ACTIVE",
        )
        sa = User(
            full_name="Super Admin",
            mobile="9000000099",
            role=Role.SUPER_ADMIN,
            society_id=None,
            account_status="ACTIVE",
        )

        # Super Admin can access any society
        assert TenantService.enforce_tenant_isolation(sa, s2.id) is True

        # User 1 accessing own society -> True
        assert TenantService.enforce_tenant_isolation(user1, s1.id) is True

        # User 1 accessing s2 -> Raises 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            TenantService.enforce_tenant_isolation(user1, s2.id)
        assert exc_info.value.code == 403
