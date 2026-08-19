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
<<<<<<< HEAD


def test_cross_society_and_idor_bill_access(client, app):
    """Ensure Resident A in Soc 1 cannot access or pay bills of Soc 2 or Resident B."""
    from datetime import date
    from app.models import MaintenanceBill, Resident

    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()
        b1 = Building.query.filter_by(society_id=s1.id).first()
        f1 = Flat.query.filter_by(building_id=b1.id).first()
        b2 = Building.query.filter_by(society_id=s2.id).first()
        f2 = Flat.query.filter_by(building_id=b2.id).first()

        # User 1 (Soc 1)
        u1 = User(
            full_name="Resident S1",
            mobile="9800000001",
            role=Role.RESIDENT,
            society_id=s1.id,
            account_status="ACTIVE",
            is_active=True,
        )
        u1.set_password("Pass@123")
        db.session.add(u1)
        db.session.flush()

        r1 = Resident(
            society_id=s1.id,
            flat_id=f1.id,
            user_id=u1.id,
            full_name=u1.full_name,
            mobile=u1.mobile,
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
        )
        db.session.add(r1)

        # User 2 (Soc 2)
        u2 = User(
            full_name="Resident S2",
            mobile="9800000002",
            role=Role.RESIDENT,
            society_id=s2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        u2.set_password("Pass@123")
        db.session.add(u2)
        db.session.flush()

        r2 = Resident(
            society_id=s2.id,
            flat_id=f2.id,
            user_id=u2.id,
            full_name=u2.full_name,
            mobile=u2.mobile,
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
        )
        db.session.add(r2)
        db.session.flush()

        # Bill for Soc 2 resident
        bill2 = MaintenanceBill(
            bill_number="BILL-S2-TEST-01",
            society_id=s2.id,
            flat_id=f2.id,
            resident_id=r2.id,
            billing_month="2026-09",
            base_amount=1500,
            total_amount=1500,
            remaining_amount=1500,
            amount_paid=0,
            due_date=date(2026, 9, 10),
            status="Pending",
        )
        db.session.add(bill2)
        db.session.commit()

        u1_id = u1.id
        s1_id = s1.id
        bill2_id = bill2.id

    # Log in as User 1 (Soc 1)
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["society_id"] = s1_id
        sess["role"] = Role.RESIDENT

    # Try accessing bill2 detail -> 404 or 403
    res = client.get(f"/bills/{bill2_id}")
    assert res.status_code in [403, 404]

    # Try paying bill2 -> 403 or 404
    res = client.get(f"/pay/{bill2_id}")
    assert res.status_code in [403, 404]


def test_cross_society_document_download_forbidden(client, app, tmp_path):
    """Ensure Soc 1 user cannot download Soc 2 documents."""
    from app.models import Document

    test_file = tmp_path / "secret_s2_doc.pdf"
    test_file.write_text("Confidential Soc 2 Info")

    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()

        u1_admin = User(
            full_name="Admin S1",
            mobile="9800000003",
            role=Role.SOCIETY_ADMIN,
            society_id=s1.id,
            account_status="ACTIVE",
            is_active=True,
        )
        u1_admin.set_password("Admin@123")
        db.session.add(u1_admin)
        db.session.flush()

        doc2 = Document(
            society_id=s2.id,
            title="Soc 2 Private Audit",
            category="Audit",
            file_path=str(test_file),
            file_size_bytes=1024,
            file_type="pdf",
            uploaded_by_id=u1_admin.id,
            access_level="ADMIN_ONLY",
        )
        db.session.add(doc2)
        db.session.commit()

        u1_id = u1_admin.id
        s1_id = s1.id
        doc2_id = doc2.id

    # Log in as Soc 1 Admin
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["society_id"] = s1_id
        sess["role"] = Role.SOCIETY_ADMIN

    # Download Soc 2 document -> MUST RETURN 403 Forbidden
    res = client.get(f"/documents/download/{doc2_id}")
    assert res.status_code == 403


def test_cross_society_facility_booking_and_cancellation_idor(client, app):
    """Ensure User in Soc 1 cannot cancel or book Soc 2 facilities."""
    from datetime import date
    from app.models import Facility, FacilityBooking, Resident

    with app.app_context():
        s1 = Society.query.filter_by(registration_number="REG-001").first()
        s2 = Society.query.filter_by(registration_number="REG-002").first()
        b2 = Building.query.filter_by(society_id=s2.id).first()
        f2 = Flat.query.filter_by(building_id=b2.id).first()

        u1 = User(
            full_name="User S1 Fac",
            mobile="9800000005",
            role=Role.RESIDENT,
            society_id=s1.id,
            account_status="ACTIVE",
            is_active=True,
        )
        u1.set_password("Pass@123")
        db.session.add(u1)

        u2 = User(
            full_name="User S2 Fac",
            mobile="9800000006",
            role=Role.RESIDENT,
            society_id=s2.id,
            account_status="ACTIVE",
            is_active=True,
        )
        u2.set_password("Pass@123")
        db.session.add(u2)
        db.session.flush()

        r2 = Resident(
            society_id=s2.id,
            flat_id=f2.id,
            user_id=u2.id,
            full_name=u2.full_name,
            mobile=u2.mobile,
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
        )
        db.session.add(r2)

        fac2 = Facility(
            society_id=s2.id,
            name="Clubhouse Soc 2",
            capacity=50,
            is_active=True,
        )
        db.session.add(fac2)
        db.session.flush()

        booking2 = FacilityBooking(
            society_id=s2.id,
            facility_id=fac2.id,
            flat_id=f2.id,
            resident_id=r2.id,
            booking_date=date(2026, 10, 1),
            start_time="10:00",
            end_time="12:00",
            status="Confirmed",
        )
        db.session.add(booking2)
        db.session.commit()

        u1_id = u1.id
        s1_id = s1.id
        booking2_id = booking2.id

    # Log in as User 1
    with client.session_transaction() as sess:
        sess["user_id"] = u1_id
        sess["society_id"] = s1_id
        sess["role"] = Role.RESIDENT

    # Try cancelling booking of Soc 2 -> 403 or 404
    res = client.post(f"/facilities/{booking2_id}/cancel")
    assert res.status_code in [403, 404]

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
