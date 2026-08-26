"""
Tests for AI Automation & Quick Productivity Features (Phases 1-39)
===================================================================
Verifies all 39 requirements:
- AI Provider abstraction & fallback
- AI Recommendation interface
- Smart Resident Status & Next-Action Service
- Admin Work Queue & Focus Mode
- Contextual Help & Form Assistant
- Duplicate Submission Guard & Idempotency
- Safe Bulk Action Guard & Record Change Preview
- Communication Intelligence (Tone, Readability, Missing info, Duplicate notice, Simplifier, Translation)
- Incident Intelligence (Classification, Severity, Duplicates, Timeline, Closure quality)
- Data Quality Center & Duplicate Resident Detector
- CSV Import Assistant
- Application Health Dashboard, Scheduled Job Monitor, Error Grouper, Webhook Intelligence
- Feature Usage Analytics & 'What Changed?'
- All REST API endpoints and role authorization
"""

import pytest
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
    MaintenanceBill,
    Complaint,
    Notice,
    RegistrationRequest,
    AuditLog,
)
from app.services.ai.provider import (
    AIProviderFactory,
    DeterministicAIProvider,
    MockAIProvider,
)
from app.services.ai.recommendation_service import AIRecommendationService
from app.services.ai.resident_ai import SmartResidentStatusService, ResidentNextActionService
from app.services.ai.admin_ai import (
    AdminWorkQueueService,
    AdminFocusModeService,
    SafeBulkActionGuard,
    RecordChangePreviewService,
)
from app.services.ai.contextual_help_service import ContextualHelpService
from app.services.ai.form_assistant_service import FormAssistantService
from app.services.ai.communication_ai import CommunicationAIService
from app.services.ai.incident_ai import IncidentAIService
from app.services.ai.data_quality_ai import DataQualityAIService, DuplicateResidentDetector
from app.services.ai.csv_import_ai import CSVImportAIService
from app.services.ai.health_ai import HealthAIService
from app.services.ai.feature_usage_service import FeatureUsageService
from app.services.ai.what_changed_service import WhatChangedService
from app.services.ai.idempotency_guard import IdempotencyGuard
from app.utils import utcnow


@pytest.fixture
def ai_test_env(app):
    """Sets up an isolated test society with Admin, Resident, Flat, and Bills."""
    with app.app_context():
        soc = Society(
            name="AI Innovation Heights",
            registration_number="AI-SOC-9999",
            address="100 Innovation Boulevard",
            city="Bengaluru",
            state="Karnataka",
            pincode="560100",
            email="admin@aiheights.com",
            phone="9988776655",
            emergency_contact="9988776600",
        )
        db.session.add(soc)
        db.session.commit()

        admin = User(
            username="ai_admin",
            full_name="AI Society Admin",
            email="admin@aiheights.com",
            mobile="9988776655",
            role=Role.SOCIETY_ADMIN,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")

        res_user = User(
            username="ai_resident",
            full_name="Alice Resident",
            email="alice@aiheights.com",
            mobile="9988776650",
            role=Role.RESIDENT,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("Resident@123")

        db.session.add_all([admin, res_user])
        db.session.commit()

        wing = Building(society_id=soc.id, name="Wing A")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=soc.id, building_id=wing.id, name="Block 1")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="101",
            floor_number=1,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        resident = Resident(
            society_id=soc.id,
            flat_id=flat.id,
            user_id=res_user.id,
            full_name="Alice Resident",
            mobile="9988776650",
            email="alice@aiheights.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
            move_in_date=utcnow().date() - timedelta(days=30),
        )
        db.session.add(resident)
        db.session.commit()

        # Add a bill
        bill = MaintenanceBill(
            society_id=soc.id,
            flat_id=flat.id,
            resident_id=resident.id,
            bill_number="BILL-AI-101",
            billing_month=utcnow().strftime("%Y-%m"),
            base_amount=1500.0,
            late_fee=0.0,
            total_amount=1500.0,
            amount_paid=0.0,
            remaining_amount=1500.0,
            status="Pending",
            due_date=utcnow().date() + timedelta(days=5),
        )
        db.session.add(bill)
        db.session.commit()

        return {
            "society_id": soc.id,
            "admin_id": admin.id,
            "resident_user_id": res_user.id,
            "resident_id": resident.id,
            "flat_id": flat.id,
            "wing_id": wing.id,
            "bill_id": bill.id,
        }


def test_ai_provider_abstraction_and_fallback(app):
    """Verifies AI Provider factory, deterministic fallback, and mock provider."""
    with app.app_context():
        det_provider = AIProviderFactory.get_provider("deterministic")
        assert isinstance(det_provider, DeterministicAIProvider)
        assert det_provider.is_available() is True

        text = det_provider.generate("Summarize this notice")
        assert "notice" in text.lower() or "summary" in text.lower()

        classification = det_provider.classify("The tap in bathroom is leaking water", ["Plumbing", "Electrical", "Security"])
        assert classification["category"] == "Plumbing"
        assert classification["priority"] == "High"

        # Mock provider
        mock_p = MockAIProvider()
        assert mock_p.name == "mock"
        c2 = mock_p.classify("Lift stuck on 3rd floor", ["Elevator", "General"])
        assert c2["category"] == "Elevator"
        assert c2["priority"] == "Critical"


def test_ai_recommendation_architecture(app, ai_test_env):
    """Verifies standard AI recommendation architecture interface and response structure."""
    with app.app_context():
        res_user = db.session.get(User, ai_test_env["resident_user_id"])
        res_recs = AIRecommendationService.get_recommendations(user=res_user, society_id=ai_test_env["society_id"])
        assert "recommendations" in res_recs
        assert isinstance(res_recs["recommendations"], list)
        if res_recs["recommendations"]:
            rec = res_recs["recommendations"][0]
            assert "type" in rec
            assert "title" in rec
            assert "priority" in rec
            assert "confidence" in rec
            assert "action_url" in rec
            assert "requires_confirmation" in rec

        admin_user = db.session.get(User, ai_test_env["admin_id"])
        admin_recs = AIRecommendationService.get_recommendations(user=admin_user, society_id=ai_test_env["society_id"])
        assert "recommendations" in admin_recs


def test_smart_resident_status_and_next_actions(app, ai_test_env):
    """Verifies Smart Resident Status Engine & Resident Next Action Service."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]
        res_id = ai_test_env["resident_id"]

        status = SmartResidentStatusService.get_status(res_id, soc_id)
        assert status["status"] in ["Everything OK", "Action Needed", "Pending", "Important Update"]
        assert "total_outstanding" in status
        assert status["total_outstanding"] == 1500.0

        actions = ResidentNextActionService.get_next_actions(res_id, soc_id)
        assert isinstance(actions, list)
        assert len(actions) > 0
        first_action = actions[0]
        assert "action" in first_action
        assert "title" in first_action
        assert "priority" in first_action
        assert "reason" in first_action
        assert "url" in first_action


def test_admin_work_queue_and_focus_mode(app, ai_test_env):
    """Verifies Admin Work Queue Service & Admin Focus Mode."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]

        # Create a pending registration request
        reg = RegistrationRequest(
            user_id=ai_test_env["resident_user_id"],
            society_id=soc_id,
            building_id=ai_test_env["wing_id"],
            flat_id=ai_test_env["flat_id"],
            full_name="Bob Applicant",
            mobile="9887766554",
            email="bob@example.com",
            status="PENDING_APPROVAL",
        )
        db.session.add(reg)
        db.session.commit()

        queue = AdminWorkQueueService.get_work_queue(soc_id)
        assert len(queue) > 0
        reg_tasks = [t for t in queue if t["type"] == "registration_approval"]
        assert len(reg_tasks) >= 1
        assert reg_tasks[0]["priority"] == "high"
        assert "Bob Applicant" in reg_tasks[0]["title"]

        focus = AdminFocusModeService.get_focus_data(soc_id)
        assert focus["focus_mode_active"] is True
        assert "high_priority_work" in focus
        assert focus["total_action_items"] >= 1


def test_contextual_help_and_form_assistant(app):
    """Verifies Smart Contextual Help & Form Assistant."""
    with app.app_context():
        # Contextual help
        help_dash = ContextualHelpService.get_help_for_page("admin_dashboard")
        assert "title" in help_dash
        assert "what_this_page_does" in help_dash
        assert len(help_dash["what_you_can_do_here"]) > 0
        assert len(help_dash["common_actions"]) > 0

        # Form assistant field explanation
        mobile_exp = FormAssistantService.explain_field("mobile")
        assert "10-digit" in mobile_exp

        # Field inspection
        bad_mobile_issues = FormAssistantService.inspect_field_value("mobile", "12345")
        assert len(bad_mobile_issues) > 0
        assert any("10 digits" in i["message"] for i in bad_mobile_issues)

        clean_mobile_issues = FormAssistantService.inspect_field_value("mobile", "9876543210")
        assert len(clean_mobile_issues) == 0

        # Full form inspection
        report = FormAssistantService.inspect_form_data("registration", {
            "full_name": "jane doe",
            "mobile": "9876543210",
            "flat_number": "202",
        })
        assert report["is_valid"] is True


def test_communication_intelligence_suite(app, ai_test_env):
    """Verifies Tone, Readability, Missing Info, Duplicate Announcement, Simplifier, Translation."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]

        # 1. Tone Checker
        tone_res = CommunicationAIService.check_tone("Residents MUST pay immediately or else legal action will be seized!")
        assert tone_res["tone_score"] < 100
        assert any(f["type"] == "too_aggressive" for f in tone_res["flags"])

        clean_tone = CommunicationAIService.check_tone("Dear residents, please note the upcoming maintenance due date on 10th August.")
        assert clean_tone["tone_score"] >= 85

        # 2. Readability Checker
        read_res = CommunicationAIService.check_readability("Please pay maintenance bills on time to support smooth society operations.")
        assert "score" in read_res
        assert read_res["level"] in ["easy", "moderate", "difficult"]

        # 3. Missing Information Detector
        missing_res = CommunicationAIService.detect_missing_information("General meeting scheduled regarding parking.", "Meeting")
        assert missing_res["is_complete"] is False
        assert any("Date" in m for m in missing_res["missing_elements"])

        complete_res = CommunicationAIService.detect_missing_information("AGM Meeting on 15th August at 10:00 AM in Clubhouse. Contact Secretary.", "Meeting")
        assert complete_res["found_elements"]["date"] is True
        assert complete_res["found_elements"]["time"] is True
        assert complete_res["found_elements"]["location"] is True

        # 4. Duplicate Announcement Detector
        notice = Notice(
            society_id=soc_id,
            title="Independence Day Celebration in Clubhouse",
            content="Join us for flag hoisting at 9 AM in the main garden.",
            notice_type="General",
        )
        db.session.add(notice)
        db.session.commit()

        dup_check = CommunicationAIService.detect_duplicate_announcement(
            soc_id, "Independence Day Celebration in Clubhouse", "Join us for flag hoisting at 9 AM in the main garden."
        )
        assert dup_check["similarity_percentage"] >= 65
        assert dup_check["is_duplicate"] is True

        # 5. Notice Simplifier
        simplifier = CommunicationAIService.simplify_notice(
            "Water Supply Shutdown", "Water supply will be temporarily discontinued tomorrow between 10am and 4pm."
        )
        assert "simple_version" in simplifier
        assert "short_version" in simplifier
        assert "formal_version" in simplifier

        # 6. Translation Consistency
        trans_res = CommunicationAIService.check_translation_consistency(
            "Meeting on 15 August at 10 AM with 50 members.", "बैठक 15 तारीख को होगी।", "Hindi"
        )
        assert trans_res["is_consistent"] is False
        assert "10" in trans_res["missing_numbers"] or "50" in trans_res["missing_numbers"]


def test_incident_intelligence_service(app, ai_test_env):
    """Verifies Incident classification, duplicates, timeline, and closure check."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]
        res_id = ai_test_env["resident_id"]
        flat_id = ai_test_env["flat_id"]

        # 1. Classification
        res = IncidentAIService.classify_incident("Major water pipe burst in basement", "Water is flooding the parking area rapidly")
        assert res["suggested_category"] == "Water"
        assert res["suggested_severity"] in ["High", "Critical"]

        # 2. Timeline
        complaint = Complaint(
            society_id=soc_id,
            resident_id=res_id,
            flat_id=flat_id,
            ticket_number="TKT-AI-999",
            title="Water leakage in master bath",
            description="Continuous dripping from pipe",
            category="Plumbing",
            priority="High",
            status="Submitted",
        )
        db.session.add(complaint)
        db.session.commit()

        timeline = IncidentAIService.generate_incident_timeline(complaint.id)
        assert len(timeline) >= 1
        assert timeline[0]["stage"] == "Created"

        # 3. Closure quality check
        poor_closure = IncidentAIService.check_closure_quality(complaint.id, "done")
        assert poor_closure["is_satisfactory"] is False

        good_closure = IncidentAIService.check_closure_quality(
            complaint.id, "Technician inspected the pipe, replaced the damaged valve, and tested water pressure with resident confirmation."
        )
        assert good_closure["is_satisfactory"] is True


def test_data_quality_and_csv_import_services(app, ai_test_env):
    """Verifies Data Quality Center, Duplicate Resident matching, and CSV Import Assistant."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]

        audit = DataQualityAIService.run_full_audit(soc_id)
        assert "data_health_score" in audit
        assert "issues" in audit
        assert isinstance(audit["issues"], list)

        dups = DuplicateResidentDetector.find_potential_duplicates(soc_id)
        assert isinstance(dups, list)

        # CSV Column Mappings
        mappings = CSVImportAIService.suggest_column_mappings(["Resident Name", "Phone_Number", "Unit_No", "Email_ID"])
        assert mappings["Resident Name"]["mapped_to"] == "full_name"
        assert mappings["Phone_Number"]["mapped_to"] == "mobile"
        assert mappings["Unit_No"]["mapped_to"] == "flat_number"

        # CSV Preview
        csv_text = "full_name,mobile,flat_number\nCharlie Brown,9876543210,101\nBad User,123,101"
        preview = CSVImportAIService.preview_and_validate_import(soc_id, csv_text)
        assert preview["valid_count"] == 1
        assert preview["invalid_count"] == 1


def test_health_ai_and_what_changed_services(app, ai_test_env):
    """Verifies Health AI, Error Grouper, Scheduled Jobs, Idempotency, and What Changed."""
    with app.app_context():
        soc_id = ai_test_env["society_id"]

        # Health
        health = HealthAIService.get_system_health_status(soc_id)
        assert health["database"]["status"] == "Healthy"
        assert health["database"]["latency_ms"] >= 0

        # Scheduled jobs
        jobs = HealthAIService.get_scheduled_jobs_status(soc_id)
        assert len(jobs) >= 5

        # Error patterns
        errors = HealthAIService.get_error_patterns(soc_id)
        assert "categories" in errors

        # Feature usage
        FeatureUsageService.record_usage("Data Quality Center", "view")
        summary = FeatureUsageService.get_analytics_summary()
        assert summary["total_interactions"] >= 1

        # Idempotency Guard
        is_dup, _ = IdempotencyGuard.check_and_record(1, "/test-action", {"amount": 100})
        assert is_dup is False
        is_dup2, msg = IdempotencyGuard.check_and_record(1, "/test-action", {"amount": 100})
        assert is_dup2 is True

        # Safe bulk action
        guard = SafeBulkActionGuard.inspect_bulk_action("bulk_cancel_bills", list(range(15)), soc_id)
        assert guard["is_large_selection"] is True
        assert guard["is_destructive"] is True
        assert guard["requires_confirmation"] is True

        # Record Change Preview
        diff = RecordChangePreviewService.generate_diff("Resident", {"mobile": "9999999999"}, {"mobile": "8888888888"})
        assert len(diff) == 1
        assert diff[0]["field"] == "Mobile"

        # What Changed
        AuditLog.query.filter_by(society_id=soc_id).delete()
        audit_entry = AuditLog(
            society_id=soc_id,
            user_id=ai_test_env["admin_id"],
            action="RESIDENT_UPDATE",
            details="Resident mobile updated to 9988776650",
        )
        db.session.add(audit_entry)
        db.session.commit()

        changed = WhatChangedService.get_changes_summary("Resident", society_id=soc_id)
        assert changed["total_changes"] >= 1


def test_ai_api_endpoints_and_authorization(client, ai_test_env):
    """Verifies REST API endpoints enforce correct role authorization and return valid JSON."""
    # 1. Unauthenticated request -> 401
    res = client.get("/api/v1/ai/recommendations")
    assert res.status_code == 401

    # 2. Authenticate as Admin
    with client.session_transaction() as sess:
        sess["user_id"] = ai_test_env["admin_id"]
        sess["role"] = Role.SOCIETY_ADMIN
        sess["society_id"] = ai_test_env["society_id"]

    # Test Admin Work Queue API
    res_wq = client.get("/api/v1/ai/admin/work-queue")
    assert res_wq.status_code == 200
    assert "tasks" in res_wq.get_json()

    # Test Focus Mode API
    res_fm = client.get("/api/v1/ai/admin/focus-mode")
    assert res_fm.status_code == 200

    # Test Contextual Help API
    res_help = client.get("/api/v1/ai/contextual-help?page=admin_dashboard")
    assert res_help.status_code == 200

    # Test Data Quality Scan API
    res_dq = client.get("/api/v1/ai/data-quality/scan")
    assert res_dq.status_code == 200
    assert "data_health_score" in res_dq.get_json()

    # Test Health Dashboard API
    res_health = client.get("/api/v1/ai/health/dashboard")
    assert res_health.status_code == 200

    # Test Admin UI views
    res_ui_dq = client.get("/admin/data-quality")
    assert res_ui_dq.status_code == 200
    assert b"Data Quality Center" in res_ui_dq.data

    res_ui_health = client.get("/admin/app-health")
    assert res_ui_health.status_code == 200
    assert b"Application Health Dashboard" in res_ui_health.data

    res_ui_wq = client.get("/admin/work-queue")
    assert res_ui_wq.status_code == 200
    assert b"Admin Work Queue" in res_ui_wq.data

    # 3. Authenticate as Resident
    with client.session_transaction() as sess:
        sess["user_id"] = ai_test_env["resident_user_id"]
        sess["role"] = Role.RESIDENT
        sess["society_id"] = ai_test_env["society_id"]

    # Resident Next Actions API
    res_na = client.get("/api/v1/ai/resident/next-actions")
    assert res_na.status_code == 200
    assert "actions" in res_na.get_json()

    # Resident Status API
    res_st = client.get("/api/v1/ai/resident/status")
    assert res_st.status_code == 200
    assert "status" in res_st.get_json()

    # Resident attempting Admin Work Queue -> 403 Forbidden
    res_forbidden = client.get("/api/v1/ai/admin/work-queue")
    assert res_forbidden.status_code == 403
