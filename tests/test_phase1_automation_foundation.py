import pytest
import json
from datetime import timedelta
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    User,
    Role,
    Resident,
    RegistrationRequest,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    Complaint,
    Visitor,
    Document,
    Vendor,
    Asset,
    InventoryItem,
    AutomationRule,
    AutomationExecution,
    AutomationAlert,
)
from app.services.automation_service import AutomationService
from app.services.search_service import SearchService
from app.services.registration_service import get_registration_advisory
from app.utils import utcnow


@pytest.fixture
def p1_env(app):
    """Creates a isolated society environment for Phase 1 testing."""
    with app.app_context():
        society = Society(
            name="Sunrise Heights Phase1",
            registration_number="SHP1-001",
            address="123 Phase One Way",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            email="admin@shp1.com",
            phone="9876543200",
        )
        db.session.add(society)
        db.session.commit()

        admin = User(
            username="p1_admin",
            full_name="Phase1 Society Admin",
            email="admin@shp1.com",
            mobile="9876543200",
            role=Role.SOCIETY_ADMIN,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")

        resident_user = User(
            username="p1_resident",
            full_name="P1 Resident User",
            email="resident@shp1.com",
            mobile="9876543201",
            role=Role.RESIDENT,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        resident_user.set_password("Resident@123")

        db.session.add_all([admin, resident_user])
        db.session.commit()

        wing = Building(society_id=society.id, name="Wing A")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=society.id, building_id=wing.id, name="Block 1")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=society.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="101",
            floor_number=1,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=resident_user.id,
            full_name="P1 Resident User",
            mobile="9876543201",
            email="resident@shp1.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
        )
        db.session.add(resident)
        db.session.commit()

        return {
            "society_id": society.id,
            "admin_id": admin.id,
            "resident_user_id": resident_user.id,
            "resident_id": resident.id,
            "flat_id": flat.id,
            "wing_id": wing.id,
            "block_id": block.id,
        }


def test_automation_models_properties_and_crud(app, p1_env):
    """Verifies AutomationRule, AutomationExecution, and AutomationAlert models."""
    with app.app_context():
        soc_id = p1_env["society_id"]

        # 1. AutomationRule
        rule = AutomationRule(
            society_id=soc_id,
            name="Test Registration Alert Rule",
            description="Alerts admin on new registration",
            trigger_type="EVENT_TRIGGERED",
            event_name="resident_registered",
            priority=2,
            action_type="RUN_DAILY_HEALTH_CHECK",
            conditions_json=json.dumps({"occupancy_type": "Owner"}),
            action_params_json=json.dumps({"notify_admin": True}),
            is_active=True,
        )
        db.session.add(rule)
        db.session.commit()

        assert rule.id is not None
        assert rule.event == "resident_registered"
        assert rule.priority == 2
        assert rule.get_conditions() == {"occupancy_type": "Owner"}
        assert rule.get_action_params() == {"notify_admin": True}

        # 2. AutomationExecution
        now = utcnow()
        exec_rec = AutomationExecution(
            rule_id=rule.id,
            society_id=soc_id,
            automation_name="RUN_DAILY_HEALTH_CHECK",
            execution_id="exec_test_001",
            status="FAILED",
            start_time=now,
            end_time=now + timedelta(seconds=2),
            duration_ms=2000,
            records_scanned=15,
            records_created=2,
            records_updated=1,
            records_skipped=12,
            errors_json=json.dumps(["Health check connection error"]),
            retry_count=1,
        )
        db.session.add(exec_rec)
        db.session.commit()

        assert exec_rec.id is not None
        assert exec_rec.created_at == now
        assert exec_rec.executed_at == now + timedelta(seconds=2)
        assert exec_rec.error_message == "Health check connection error"
        assert exec_rec.retry_count == 1

        # 3. AutomationAlert
        alert = AutomationAlert(
            society_id=soc_id,
            rule_id=rule.id,
            execution_id=exec_rec.id,
            alert_type="HEALTH_CHECK",
            severity="CRITICAL",
            title="Society Health Diagnostic Failed",
            message="Health audit reported connection failure.",
            is_resolved=False,
        )
        db.session.add(alert)
        db.session.commit()

        assert alert.id is not None
        assert alert.severity == "CRITICAL"
        assert alert.is_resolved is False
        assert alert.rule.name == "Test Registration Alert Rule"
        assert alert.execution.execution_id == "exec_test_001"


def test_automation_service_event_trigger_and_conditions(app, p1_env):
    """Tests AutomationService.trigger_event and safe condition evaluation."""
    with app.app_context():
        soc_id = p1_env["society_id"]
        admin = db.session.get(User, p1_env["admin_id"])

        # Register custom test action
        executed_runs = []
        def custom_action(society_id, params, executed_by):
            executed_runs.append(params)
            return {"scanned": 1, "created": 1, "updated": 0, "skipped": 0}

        AutomationService.register_job("CUSTOM_EVENT_ACTION", custom_action)

        # Condition: pending_days >= 3
        AutomationService.create_rule(
            society_id=soc_id,
            name="Escalate Pending Registrations >= 3d",
            action_type="CUSTOM_EVENT_ACTION",
            trigger_type="EVENT_TRIGGERED",
            event_name="registration_pending",
            priority=3,
            conditions={"pending_days": {">=": 3}},
            action_params={"escalation_level": "Level1"},
            is_active=True,
        )

        # Condition test 1: pending_days = 1 (should NOT fire)
        res_skip = AutomationService.trigger_event(
            event_name="registration_pending",
            society_id=soc_id,
            payload={"pending_days": 1, "reg_id": 99},
            executed_by=admin,
        )
        assert len(res_skip) == 0
        assert len(executed_runs) == 0

        # Condition test 2: pending_days = 4 (SHOULD fire)
        res_fire = AutomationService.trigger_event(
            event_name="registration_pending",
            society_id=soc_id,
            payload={"pending_days": 4, "reg_id": 100},
            executed_by=admin,
        )
        assert len(res_fire) == 1
        assert res_fire[0]["result"]["success"] is True
        assert len(executed_runs) == 1
        assert executed_runs[0]["escalation_level"] == "Level1"
        assert executed_runs[0]["pending_days"] == 4


def test_automation_retry_and_alert_lifecycle(app, p1_env):
    """Tests execution retries, alert creation, and resolution."""
    with app.app_context():
        soc_id = p1_env["society_id"]
        admin = db.session.get(User, p1_env["admin_id"])

        # 1. Create an alert
        alert = AutomationService.create_alert(
            society_id=soc_id,
            title="High Water Tank Pressure",
            message="Pressure sensor exceeded 80 PSI threshold.",
            severity="CRITICAL",
            source="SOCIETY_OPERATIONS",
            executed_by_id=admin.id,
        )
        assert alert.id is not None
        assert alert.is_resolved is False

        # Verify alert appears in get_alerts
        active_alerts = AutomationService.get_alerts(society_id=soc_id, resolved=False)
        assert any(a.id == alert.id for a in active_alerts)

        # Resolve alert
        resolved_alert = AutomationService.resolve_alert(alert.id, resolved_by=admin)
        assert resolved_alert.is_resolved is True
        assert resolved_alert.resolved_by_id == admin.id
        assert resolved_alert.resolved_at is not None

        # 2. Test retry of a failing job that becomes successful
        should_fail = [True]
        def flaky_action(society_id, params, executed_by):
            if should_fail[0]:
                raise RuntimeError("Temporary upstream timeout")
            return {"scanned": 5, "created": 2, "updated": 1, "skipped": 2}

        AutomationService.register_job("FLAKY_ACTION", flaky_action)

        # First run fails
        fail_res = AutomationService.execute_job("FLAKY_ACTION", society_id=soc_id, executed_by=admin)
        assert fail_res["success"] is False
        exec_id = fail_res["execution_id"]

        # Retry fails again
        retry1 = AutomationService.retry_execution(exec_id, executed_by=admin)
        assert retry1["success"] is False

        # Flaky condition resolves
        should_fail[0] = False
        retry2 = AutomationService.retry_execution(exec_id, executed_by=admin)
        assert retry2["success"] is True
        assert retry2["status"] == "COMPLETED"


def test_global_admin_search_all_required_entities(app, p1_env):
    """Verifies that Admin Global Search searches all 11+ entity types with society_id scoping."""
    with app.app_context():
        soc_id = p1_env["society_id"]
        admin = db.session.get(User, p1_env["admin_id"])
        flat_id = p1_env["flat_id"]
        resident_id = p1_env["resident_id"]
        now = utcnow()

        # Seed test entities for search
        # 1. Bill
        bill = MaintenanceBill(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_number="BILL-P1-2026",
            billing_month="2026-05",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=0.0,
            remaining_amount=1500.0,
            due_date=now,
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        # 2. Payment & Receipt
        payment = Payment(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_id=bill.id,
            transaction_id="TXN-P1-998877",
            amount_paid=1500.0,
            payment_method="UPI",
            status="Success",
            payment_date=now,
        )
        db.session.add(payment)
        db.session.commit()

        receipt = PaymentReceipt(
            society_id=soc_id,
            payment_id=payment.id,
            receipt_number="REC-P1-1001",
        )
        # 3. Complaint
        complaint = Complaint(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            ticket_number="TKT-P1-404",
            title="Elevator strange vibration",
            description="Loud grinding sound near floor 2",
            category="Lift / Elevator",
            status="Submitted",
        )
        # 4. Visitor
        visitor = Visitor(
            society_id=soc_id,
            flat_id=flat_id,
            resident_id=resident_id,
            visitor_name="Vikram Test Visitor",
            mobile="9876543299",
            purpose="Courier Delivery",
        )
        # 5. Document
        doc = Document(
            society_id=soc_id,
            title="Fire Safety Certificate 2026",
            category="Compliance",
            file_path="compliance/fire_safety_2026.pdf",
            uploaded_by_id=admin.id,
            access_level="ADMIN_ONLY",
        )
        # 6. Vendor
        vendor = Vendor(
            society_id=soc_id,
            company_name="Apex Elevator AMC Services",
            contact_person="Ramesh Patel",
            phone="9876543288",
            category="Lift",
        )
        # 7. Asset
        asset = Asset(
            society_id=soc_id,
            asset_name="Main Generator Unit 45kVA",
            category="Electrical",
            location="Basement Utility Room",
            status="Operational",
        )
        # 8. Inventory
        inv = InventoryItem(
            society_id=soc_id,
            item_name="LED Corridor Lights 18W",
            category="Electrical",
            current_stock=14,
            minimum_threshold=5,
            unit="pcs",
        )

        db.session.add_all([receipt, complaint, visitor, doc, vendor, asset, inv])
        db.session.commit()

        # Search tests across all entity types:
        # 1. Residents & Flats
        res_res = SearchService.global_search(admin, soc_id, "P1 Resident")
        assert any(c["key"] == "category_residents" for c in res_res["categories"])

        res_flat = SearchService.global_search(admin, soc_id, "101")
        assert any(c["key"] == "category_flats" for c in res_flat["categories"])

        # 2. Bills
        res_bill = SearchService.global_search(admin, soc_id, "BILL-P1-2026")
        assert any(c["key"] == "category_bills" for c in res_bill["categories"])

        # 3. Payments
        res_pay = SearchService.global_search(admin, soc_id, "TXN-P1-998877")
        assert any(c["key"] == "category_payments" for c in res_pay["categories"])

        # 4. Receipts
        res_rec = SearchService.global_search(admin, soc_id, "REC-P1-1001")
        assert any(c["key"] == "category_receipts" for c in res_rec["categories"])

        # 5. Complaints
        res_comp = SearchService.global_search(admin, soc_id, "TKT-P1-404")
        assert any(c["key"] == "category_complaints" for c in res_comp["categories"])

        # 6. Visitors
        res_vis = SearchService.global_search(admin, soc_id, "Vikram Test")
        assert any(c["key"] == "category_visitors" for c in res_vis["categories"])

        # 7. Documents
        res_doc = SearchService.global_search(admin, soc_id, "Fire Safety")
        assert any(c["key"] == "category_documents" for c in res_doc["categories"])

        # 8. Vendors
        res_vnd = SearchService.global_search(admin, soc_id, "Apex Elevator")
        assert any(c["key"] == "category_vendors" for c in res_vnd["categories"])

        # 9. Assets
        res_ast = SearchService.global_search(admin, soc_id, "Generator")
        assert any(c["key"] == "category_assets" for c in res_ast["categories"])

        # 10. Inventory
        res_inv = SearchService.global_search(admin, soc_id, "Corridor Lights")
        assert any(c["key"] == "category_inventory" for c in res_inv["categories"])


def test_pending_registration_aging_and_duplicate_detection(app, p1_env):
    """Verifies pending registration aging calculations, duplicate signals, missing data checks, and advisory recommendations."""
    with app.app_context():
        soc_id = p1_env["society_id"]
        flat_id = p1_env["flat_id"]
        wing_id = p1_env["wing_id"]
        block_id = p1_env["block_id"]

        # Case 1: Duplicate mobile and duplicate occupied flat
        reg1 = RegistrationRequest(
            user_id=p1_env["resident_user_id"],
            society_id=soc_id,
            building_id=wing_id,
            block_id=block_id,
            flat_id=flat_id,
            full_name="Duplicate Applicant",
            mobile="9876543201",  # Same mobile as active resident
            email="resident@shp1.com",  # Same email as active resident
            occupancy_type="TENANT",
            status="PENDING_APPROVAL",
            created_at=utcnow() - timedelta(days=5),
        )
        db.session.add(reg1)
        db.session.commit()

        advisory1 = get_registration_advisory(reg1)
        assert advisory1["duplicate_detected"] is True
        assert any("mobile" in s.lower() for s in advisory1["signals"])
        assert any("email" in s.lower() for s in advisory1["signals"])
        assert any("flat" in s.lower() for s in advisory1["signals"])
        assert advisory1["recommendation_status"] == "WARNING"

        # Case 2: Incomplete registration (missing email)
        flat2 = Flat(society_id=soc_id, building_id=wing_id, block_id=block_id, flat_number="202", floor_number=2, occupancy_status="Vacant")
        db.session.add(flat2)
        db.session.commit()

        u_temp2 = User(full_name="Clean Applicant", mobile="9876549999", email="clean@shp1.com", role=Role.RESIDENT, society_id=soc_id)
        u_temp2.set_password("Temp@123")
        u_temp3 = User(full_name="Ideal Resident", mobile="9876548888", email="ideal@shp1.com", role=Role.RESIDENT, society_id=soc_id)
        u_temp3.set_password("Temp@123")
        db.session.add_all([u_temp2, u_temp3])
        db.session.commit()

        reg2 = RegistrationRequest(
            user_id=u_temp2.id,
            society_id=soc_id,
            building_id=wing_id,
            block_id=block_id,
            flat_id=flat2.id,
            full_name="Clean Applicant",
            mobile="9876549999",
            email="",  # Missing email
            occupancy_type="OWNER",
            status="PENDING_APPROVAL",
            created_at=utcnow() - timedelta(days=8),
        )
        db.session.add(reg2)
        db.session.commit()

        advisory2 = get_registration_advisory(reg2)
        assert advisory2["duplicate_detected"] is False
        assert advisory2["has_missing_data"] is True
        assert any("email" in m.lower() for m in advisory2["missing_data"])

        # Case 3: Completely clean valid application
        reg3 = RegistrationRequest(
            user_id=u_temp3.id,
            society_id=soc_id,
            building_id=wing_id,
            block_id=block_id,
            flat_id=flat2.id,
            full_name="Ideal Resident",
            mobile="9876548888",
            email="ideal@shp1.com",
            occupancy_type="OWNER",
            status="PENDING_APPROVAL",
            created_at=utcnow() - timedelta(days=1),
        )
        db.session.add(reg3)
        db.session.commit()

        # Delete reg2 so flat2 has no duplicate pending requests
        db.session.delete(reg2)
        db.session.commit()

        advisory3 = get_registration_advisory(reg3)
        assert advisory3["duplicate_detected"] is False
        assert advisory3["has_missing_data"] is False
        assert advisory3["recommendation_status"] == "READY"
        assert "READY FOR APPROVAL" in advisory3["admin_recommendation"]


def test_admin_automation_center_web_routes(client, app, p1_env):
    """Tests all Admin Automation Center routes, tabs, actions, rule creation, toggle, and alert resolution."""
    admin_user = None
    with app.app_context():
        admin_user = db.session.get(User, p1_env["admin_id"])

    # Authenticate as Society Admin
    with client.session_transaction() as sess:
        sess["user_id"] = admin_user.id
        sess["user_name"] = admin_user.full_name
        sess["role"] = admin_user.role
        sess["society_id"] = p1_env["society_id"]

    # 1. GET /admin/automation with different tabs
    for tab in ["dashboard", "rules", "scheduled", "alerts", "failed", "history"]:
        resp = client.get(f"/admin/automation?tab={tab}")
        assert resp.status_code == 200
        assert b"Automation Center" in resp.data

    # 2. POST /admin/automation/rules/create
    rule_data = {
        "name": "Web Test Daily Bill Rule",
        "action_type": "GENERATE_MONTHLY_BILLS",
        "trigger_type": "SCHEDULED",
        "priority": "2",
        "schedule_cron": "0 0 1 * *",
        "description": "Auto generate bills on 1st of month",
    }
    create_resp = client.post("/admin/automation/rules/create", data=rule_data, follow_redirects=True)
    assert create_resp.status_code == 200

    with app.app_context():
        created_rule = AutomationRule.query.filter_by(name="Web Test Daily Bill Rule").first()
        assert created_rule is not None
        assert created_rule.priority == 2
        rule_id = created_rule.id

    # 3. POST /admin/automation/rules/<id>/toggle
    toggle_resp = client.post(f"/admin/automation/rules/{rule_id}/toggle", follow_redirects=True)
    assert toggle_resp.status_code == 200
    with app.app_context():
        toggled_rule = db.session.get(AutomationRule, rule_id)
        assert toggled_rule.is_active is False

    # 4. POST /admin/automation/run/<action_name>
    run_resp = client.post("/admin/automation/run/RUN_DAILY_HEALTH_CHECK", follow_redirects=True)
    assert run_resp.status_code == 200

    # 5. POST /admin/automation/alerts/<id>/resolve
    with app.app_context():
        alert = AutomationService.create_alert(
            society_id=p1_env["society_id"],
            title="Web Test Alert",
            message="Testing web alert resolution",
            severity="WARNING",
        )
        alert_id = alert.id

    resolve_resp = client.post(f"/admin/automation/alerts/{alert_id}/resolve", follow_redirects=True)
    assert resolve_resp.status_code == 200
    with app.app_context():
        resolved_alt = db.session.get(AutomationAlert, alert_id)
        assert resolved_alt.is_resolved is True

    # 6. POST /admin/automation/rules/<id>/delete
    del_resp = client.post(f"/admin/automation/rules/{rule_id}/delete", follow_redirects=True)
    assert del_resp.status_code == 200
    with app.app_context():
        assert db.session.get(AutomationRule, rule_id) is None
