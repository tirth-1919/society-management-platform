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
    Facility,
    PreApprovedPass,
    Staff,
    Vendor,
    Complaint,
    SocietyMeeting,
    ExpenseVoucher,
    Document,
    EmergencyContact,
    Dependent,
)
from app.services.facility_automation_service import FacilityAutomationService
from app.services.visitor_security_automation_service import VisitorSecurityAutomationService
from app.services.staff_attendance_automation_service import StaffAttendanceAutomationService
from app.services.complaint_lifecycle_automation_service import ComplaintLifecycleAutomationService
from app.services.voting_automation_service import VotingAutomationService
from app.services.emergency_automation_service import EmergencyAutomationService
from app.services.vendor_automation_service import VendorAutomationService
from app.services.utility_automation_service import UtilityAutomationService
from app.services.move_in_out_automation_service import MoveInOutAutomationService
from app.services.tenant_lease_automation_service import TenantLeaseAutomationService
from app.services.event_management_automation_service import EventManagementAutomationService
from app.services.sustainability_automation_service import SustainabilityAutomationService
from app.services.violation_penalty_automation_service import ViolationPenaltyAutomationService
from app.services.statutory_compliance_automation_service import StatutoryComplianceAutomationService
from app.services.digital_notice_automation_service import DigitalNoticeAutomationService
from app.services.household_directory_automation_service import HouseholdDirectoryAutomationService
from app.services.legal_vault_automation_service import LegalVaultAutomationService
from app.services.budgeting_automation_service import BudgetingAutomationService
from app.services.governance_automation_service import GovernanceAutomationService
from app.services.lost_found_automation_service import LostFoundAutomationService
from app.services.pet_policy_automation_service import PetPolicyAutomationService
from app.services.intercom_relay_automation_service import IntercomRelayAutomationService
from app.services.renovation_permit_automation_service import RenovationPermitAutomationService
from app.services.pwa_offline_automation_service import PWAOfflineAutomationService
from app.services.regional_localization_service import RegionalLocalizationService
from app.services.system_health_hardening_service import SystemHealthHardeningService
from app.services.automation_service import AutomationService
from app.utils import utcnow


@pytest.fixture
def enterprise_env(app):
    """Creates an isolated enterprise society test environment for Phases 14-39."""
    with app.app_context():
        soc = Society(
            name="Sunrise Heights Smart City Phase 14-39",
            registration_number="ENT-SOC-1439",
            address="500 Enterprise Way",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            email="admin@smartcity.com",
            phone="9876543500",
            emergency_contact="9876543599",
        )
        db.session.add(soc)
        db.session.commit()

        admin = User(
            username="ent_admin",
            full_name="Enterprise Admin",
            email="admin@smartcity.com",
            mobile="9876543500",
            role=Role.SOCIETY_ADMIN,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")

        res_user = User(
            username="ent_resident",
            full_name="Enterprise Resident",
            email="resident@smartcity.com",
            mobile="9876543501",
            role=Role.RESIDENT,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("Resident@123")

        db.session.add_all([admin, res_user])
        db.session.commit()

        wing = Building(society_id=soc.id, name="Wing ENTERPRISE")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=soc.id, building_id=wing.id, name="Block E")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="801",
            floor_number=8,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        resident = Resident(
            society_id=soc.id,
            flat_id=flat.id,
            user_id=res_user.id,
            full_name="Enterprise Resident",
            mobile="9876543501",
            email="resident@smartcity.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
            move_in_date=utcnow().date() - timedelta(days=60),
        )
        db.session.add(resident)
        db.session.commit()

        return {
            "society_id": soc.id,
            "admin_id": admin.id,
            "resident_user_id": res_user.id,
            "resident_id": resident.id,
            "flat_id": flat.id,
            "wing_id": wing.id,
            "block_id": block.id,
        }


def test_phase14_to_19_community_and_security(app, enterprise_env):
    """
    Tests Phases 14–19:
    - Phase 14: Facility booking & slot availability
    - Phase 15: Visitor pass validation & overstay detection
    - Phase 16: Staff attendance & payroll calculation
    - Phase 17: Complaint SLA tracking & resolution
    - Phase 18: Poll voting & quorum tallying
    - Phase 19: Emergency SOS broadcast
    """
    with app.app_context():
        soc_id = enterprise_env["society_id"]
        flat_id = enterprise_env["flat_id"]
        res_id = enterprise_env["resident_id"]
        admin_id = enterprise_env["admin_id"]
        now = utcnow().date()

        # Phase 14: Facility Booking
        fac = Facility(society_id=soc_id, name="Tennis Court", hourly_rate=200.0, requires_approval=False, is_active=True)
        db.session.add(fac)
        db.session.commit()

        avail = FacilityAutomationService.check_slot_availability(fac.id, now, "07:00", "09:00")
        assert avail["available"] is True

        booking = FacilityAutomationService.auto_book_facility(soc_id, fac.id, flat_id, res_id, now, "07:00", "09:00")
        assert booking.id is not None
        assert booking.status == "Confirmed"
        assert booking.total_cost == 400.0

        util_rep = FacilityAutomationService.get_facility_utilization_report(soc_id)
        assert len(util_rep["facilities"]) >= 1

        # Phase 15: Visitor Security & Overstay
        pass_code = "ENT-PASS-99"
        p_pass = PreApprovedPass(
            pass_code=pass_code,
            society_id=soc_id,
            flat_id=flat_id,
            resident_id=res_id,
            visitor_name="Delivery Executive",
            mobile="9876543588",
            expected_date=now,
            purpose="Delivery",
            is_used=False,
        )
        db.session.add(p_pass)
        db.session.commit()

        val = VisitorSecurityAutomationService.validate_pre_approved_pass(pass_code, soc_id)
        assert val["valid"] is True

        vis_entry = VisitorSecurityAutomationService.process_pass_entry(pass_code, soc_id)
        assert vis_entry.id is not None
        assert vis_entry.approval_status == "Approved"

        # Overstay detection test
        vis_entry.entry_time = utcnow() - timedelta(hours=8)
        db.session.commit()
        overstay_res = VisitorSecurityAutomationService.detect_overstaying_visitors(soc_id, hours_threshold=6)
        assert overstay_res["overstaying_count"] >= 1

        # Phase 16: Staff Attendance & Payroll
        guard = Staff(society_id=soc_id, full_name="Bahadur Guard", role_type="Security", phone="9876543577", salary_amount=16000.0)
        db.session.add(guard)
        db.session.commit()

        att_sum = StaffAttendanceAutomationService.get_daily_staff_attendance_summary(soc_id)
        assert att_sum["total_staff_count"] >= 1

        payroll = StaffAttendanceAutomationService.calculate_monthly_salary_estimate(soc_id)
        assert payroll["total_monthly_payroll"] >= 16000.0

        # Phase 17: Complaint SLA & Escalation
        comp = Complaint(
            society_id=soc_id,
            flat_id=flat_id,
            resident_id=res_id,
            ticket_number="TKT-ENT-001",
            title="Main line water leakage",
            description="Major pipeline burst in basement",
            category="Plumbing",
            priority="Emergency",
            status="Submitted",
            created_at=utcnow() - timedelta(hours=6),  # 6h > 4h emergency SLA
        )
        db.session.add(comp)
        db.session.commit()

        sla_audit = ComplaintLifecycleAutomationService.audit_sla_and_escalate_breaches(soc_id)
        assert sla_audit["sla_breached_count"] >= 1
        assert "TKT-ENT-001" in sla_audit["breached_tickets"]

        resolved_comp = ComplaintLifecycleAutomationService.resolve_complaint(comp.id, "Pipeline welded and water restored")
        assert resolved_comp.status == "Resolved"

        # Phase 18: Poll Voting & Quorum
        meeting = SocietyMeeting(
            society_id=soc_id,
            title="Solar Rooftop Installation Resolution",
            agenda="Vote to install 50kVA solar panels on Wing OMEGA rooftop",
            meeting_date=utcnow() + timedelta(days=2),
        )
        db.session.add(meeting)
        db.session.commit()

        vote = VotingAutomationService.cast_vote(meeting.id, flat_id, res_id, "In Favor")
        assert vote.id is not None

        tally = VotingAutomationService.tally_meeting_votes(meeting.id)
        assert tally["total_votes_cast"] == 1
        assert tally["in_favor_count"] == 1

        # Phase 19: Emergency SOS Broadcast
        sos = EmergencyAutomationService.trigger_emergency_sos(
            society_id=soc_id,
            user_id=admin_id,
            alert_type="FIRE",
            title="Basement Smoke Alarm Triggered",
            message="Smoke detected near electrical panel in Basement 1.",
            location_details="Basement 1 Electrical Room",
        )
        assert sos.id is not None
        assert sos.is_active is True

        active_sos = EmergencyAutomationService.get_active_emergencies(soc_id)
        assert len(active_sos) >= 1

        resolved_ok = EmergencyAutomationService.resolve_emergency(sos.id)
        assert resolved_ok is True


def test_phase20_to_25_operations_and_utilities(app, enterprise_env):
    """
    Tests Phases 20–25:
    - Phase 20: Vendor contract audit & SLA compliance
    - Phase 21: Water & utility management
    - Phase 22: Move-out clearance & NOC verification
    - Phase 23: Tenant ratio & police verification tracking
    - Phase 24: Event management & festival circulars
    - Phase 25: Green society sustainability index
    """
    with app.app_context():
        soc_id = enterprise_env["society_id"]
        res_id = enterprise_env["resident_id"]
        now = utcnow().date()

        # Phase 20: Vendor Contracts & SLA
        vendor = Vendor(
            society_id=soc_id,
            company_name="CleanTech Waste Management",
            contact_person="Manoj",
            phone="9876543566",
            category="Waste Management",
            contract_end=now + timedelta(days=10),  # Expiring soon
            contract_amount=18000.0,
            status="Active",
        )
        db.session.add(vendor)
        db.session.commit()

        vnd_audit = VendorAutomationService.audit_vendor_contracts(soc_id, days_threshold=30)
        assert vnd_audit["expiring_count"] >= 1

        scorecard = VendorAutomationService.get_vendor_compliance_scorecard(soc_id)
        assert len(scorecard) >= 1

        # Phase 21: Utilities
        water_exp = ExpenseVoucher(
            voucher_number="VCHR-WAT-01",
            society_id=soc_id,
            category="Water",
            amount=6500.0,
            payee_name="Gujarat Water Supply Tankers",
            description="5 tanker deliveries",
            expense_date=now,
            status="Approved",
        )
        db.session.add(water_exp)
        db.session.commit()

        water_sum = UtilityAutomationService.get_water_management_summary(soc_id)
        assert water_sum["total_water_expenditure"] >= 6500.0

        # Phase 22: Move-Out Clearance & NOC
        noc = MoveInOutAutomationService.verify_dues_clearance_for_noc(res_id, soc_id)
        assert noc["eligible_for_noc"] is True

        move_out_res = MoveInOutAutomationService.process_move_out_clearance(res_id, soc_id, reason="Relocating abroad")
        assert move_out_res["status"] == "Moved Out"

        # Phase 23: Tenancy Breakdown & Police Verification
        tenancy_rep = TenantLeaseAutomationService.get_tenancy_breakdown_report(soc_id)
        assert "tenant_percentage" in tenancy_rep

        # Phase 24: Event Management & Circular
        evt_res = EventManagementAutomationService.calculate_event_financials(soc_id, "Festival")
        assert "total_event_expenditure" in evt_res

        evt_notice = EventManagementAutomationService.create_event_broadcast_notice(soc_id, "Diwali Grand Gathering", "10 November 2026")
        assert evt_notice.id is not None

        # Phase 25: Sustainability Green Score
        green = SustainabilityAutomationService.calculate_green_society_score(soc_id)
        assert green["green_score"] >= 50
        assert "tier" in green


def test_phase26_to_31_governance_and_compliance(app, enterprise_env):
    """
    Tests Phases 26–31:
    - Phase 26: Violation logging & security task
    - Phase 27: Statutory Form I member register
    - Phase 28: Digital notice publication & broadcast
    - Phase 29: Household profile & directory compilation
    - Phase 30: Legal document vault & access logging
    - Phase 31: Budget variance analysis & sinking fund
    """
    with app.app_context():
        soc_id = enterprise_env["society_id"]
        flat_id = enterprise_env["flat_id"]
        res_id = enterprise_env["resident_id"]
        admin_id = enterprise_env["admin_id"]

        # Phase 26: Violations
        viol = ViolationPenaltyAutomationService.log_violation(soc_id, flat_id, "Noise after 10 PM", "Loud music reported by neighbor")
        assert "alert_id" in viol
        assert "work_order_id" in viol

        # Phase 27: Statutory Member Register
        reg = StatutoryComplianceAutomationService.get_statutory_member_register(soc_id)
        assert reg["total_registered_members"] >= 1
        agm_stat = StatutoryComplianceAutomationService.get_agm_compliance_status(soc_id)
        assert "compliance_status" in agm_stat

        # Phase 28: Digital Notice Board
        notice = DigitalNoticeAutomationService.publish_digital_notice(
            soc_id, "Power Shutdown for Transformer Maintenance", "Transformer maintenance on Sunday 10 AM - 1 PM", audience="All"
        )
        assert notice.id is not None
        active_notices = DigitalNoticeAutomationService.get_active_notices(soc_id)
        assert len(active_notices) >= 1

        # Phase 29: Household Directory & Profile
        emg = EmergencyContact(society_id=soc_id, resident_id=res_id, name="Dr. Mehta", relation="Doctor", phone="9876543555")
        dep = Dependent(resident_id=res_id, name="Aarav Resident", relation="Son", age=8)
        db.session.add_all([emg, dep])
        db.session.commit()

        hh_profile = HouseholdDirectoryAutomationService.get_unit_household_profile(flat_id, soc_id)
        assert hh_profile is not None
        assert len(hh_profile["emergency_contacts"]) >= 1
        assert len(hh_profile["dependents"]) >= 1

        directory = HouseholdDirectoryAutomationService.get_society_member_directory(soc_id)
        assert len(directory) >= 1

        # Phase 30: Legal Vault & Access Logging
        doc = Document(
            society_id=soc_id,
            title="Society Conveyance Deed 2026",
            category="Legal",
            file_path="legal/conveyance_2026.pdf",
            uploaded_by_id=admin_id,
        )
        db.session.add(doc)
        db.session.commit()

        access_log = LegalVaultAutomationService.log_document_access(doc.id, admin_id)
        assert access_log.id is not None
        legal_catalog = LegalVaultAutomationService.get_legal_documents_catalog(soc_id)
        assert len(legal_catalog) >= 1

        # Phase 31: Budgeting & Sinking Fund
        b_var = BudgetingAutomationService.get_budget_variance_analysis(soc_id)
        assert "total_budget" in b_var
        assert len(b_var["categories"]) >= 5

        sinking = BudgetingAutomationService.calculate_sinking_fund_reserve(soc_id, sinking_fund_rate_per_flat=300.0)
        assert "projected_annual_sinking_fund" in sinking


def test_phase32_to_39_lifestyle_and_system_hardening(app, enterprise_env):
    """
    Tests Phases 32–39:
    - Phase 32: Multi-wing governance ranking
    - Phase 33: Lost & found registry
    - Phase 34: Pet policy compliance audit
    - Phase 35: Intercom call relay dispatch
    - Phase 36: Renovation work permit issuance
    - Phase 37: PWA manifest & offline action sync
    - Phase 38: INR currency formatting & localized languages
    - Phase 39: System health hardening & orphaned record scanner
    """
    with app.app_context():
        soc_id = enterprise_env["society_id"]
        flat_id = enterprise_env["flat_id"]
        admin_id = enterprise_env["admin_id"]

        # Phase 32: Multi-Wing Governance Report
        gov_rep = GovernanceAutomationService.get_wing_governance_report(soc_id)
        assert gov_rep["total_wings"] >= 1

        # Phase 33: Lost & Found
        lf = LostFoundAutomationService.report_lost_found_item(soc_id, "Car Key Fob (Toyota)", item_type="FOUND", location="Basement Lift Lobby")
        assert lf["status"] == "LOGGED_AND_BROADCAST"

        # Phase 34: Pet Policy Compliance
        pet_audit = PetPolicyAutomationService.audit_pet_compliance(soc_id)
        assert pet_audit["compliance_rate"] == 100.0

        # Phase 35: Intercom Call Relay
        call_res = IntercomRelayAutomationService.dispatch_gate_visitor_call(flat_id, "Courier Boy", soc_id)
        assert "dispatched" in call_res

        # Phase 36: Renovation Permit
        ren_permit = RenovationPermitAutomationService.issue_renovation_permit(
            soc_id, flat_id, "Urban Interiors Ltd", start_date=utcnow().date(), end_date=utcnow().date() + timedelta(days=15)
        )
        assert "permit_number" in ren_permit
        assert "09:00 AM" in ren_permit["work_hours"]

        # Phase 37: PWA & Offline Sync
        manifest = PWAOfflineAutomationService.get_pwa_app_manifest()
        assert manifest["short_name"] == "SocietyERP"

        sync_res = PWAOfflineAutomationService.process_offline_synced_actions(
            [{"action_type": "LOG_VISITOR"}, {"action_type": "SUBMIT_COMPLAINT"}], user_id=admin_id, society_id=soc_id
        )
        assert sync_res["processed_count"] == 2

        # Phase 38: Regional Localization & INR Currency Formatting
        inr_1 = RegionalLocalizationService.format_inr_currency(1500.0)
        assert inr_1 == "₹1,500.00"
        inr_2 = RegionalLocalizationService.format_inr_currency(1500000.50)
        assert inr_2 == "₹15,00,000.50"

        langs = RegionalLocalizationService.get_supported_languages()
        assert "gu" in langs
        assert "hi" in langs

        # Phase 39: System Health, Self-Healing & Hardening
        orphans = SystemHealthHardeningService.scan_orphaned_records(soc_id)
        assert "status" in orphans

        counts = SystemHealthHardeningService.get_table_row_counts(soc_id)
        assert counts["flats"] >= 1

        # Test self-healing pipeline
        admin_u = db.session.get(User, admin_id)
        heal_res = SystemHealthHardeningService.run_self_healing_maintenance_pipeline(soc_id, admin_user=admin_u)
        assert heal_res["status"] == "SELF_HEALED_SUCCESSFULLY"
        assert heal_res["system_health"]["health_score"] >= 80

        # Run self-healing via AutomationService
        auto_heal = AutomationService.execute_job("RUN_SELF_HEALING_PIPELINE", society_id=soc_id, executed_by=admin_u)
        assert auto_heal["success"] is True

        hardening = SystemHealthHardeningService.get_full_system_hardening_status(soc_id)
        assert hardening["csrf_protection_enabled"] is True
        assert hardening["single_society_isolation_enforced"] is True
        assert hardening["security_tier"] == "ENTERPRISE_HARDENED"
