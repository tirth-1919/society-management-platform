import pytest
from datetime import datetime, timedelta
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    User,
    Role,
    Resident,
    Complaint,
    WorkOrder,
    Staff,
    Vendor,
    Asset,
    InventoryItem,
    InventoryTransaction,
    ParkingSlot,
    Vehicle,
    Document,
)
from app.services.operations_automation_service import OperationsAutomationService
from app.services.parking_automation_service import ParkingAutomationService
from app.services.inventory_automation_service import InventoryAutomationService
from app.services.asset_automation_service import AssetAutomationService
from app.services.document_automation_service import DocumentAutomationService
from app.services.notification_automation_service import NotificationAutomationService
from app.services.ai_prediction_service import AIPredictionService
from app.services.ai_communication_service import AICommunicationService
from app.utils import utcnow


@pytest.fixture
def full_env(app):
    """Creates a comprehensive test environment for Phases 6 through 13."""
    with app.app_context():
        soc = Society(
            name="Sunrise Heights Mega Complex",
            registration_number="AUT-MEGA-613",
            address="1000 Future Way",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            email="admin@mega.com",
            phone="9876543400",
            emergency_contact="9876543499",
        )
        db.session.add(soc)
        db.session.commit()

        admin = User(
            username="mega_admin",
            full_name="Mega Society Admin",
            email="admin@mega.com",
            mobile="9876543400",
            role=Role.SOCIETY_ADMIN,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")

        res_user = User(
            username="mega_resident",
            full_name="Mega Resident",
            email="resident@mega.com",
            mobile="9876543401",
            role=Role.RESIDENT,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("Resident@123")

        db.session.add_all([admin, res_user])
        db.session.commit()

        wing = Building(society_id=soc.id, name="Wing OMEGA")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=soc.id, building_id=wing.id, name="Block A")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="501",
            floor_number=5,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        resident = Resident(
            society_id=soc.id,
            flat_id=flat.id,
            user_id=res_user.id,
            full_name="Mega Resident",
            mobile="9876543401",
            email="resident@mega.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
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


def test_phase6_operations_automation_suite(app, full_env):
    """
    Tests Features 81–100:
    - Daily/weekly/monthly operations checklists (81, 82, 83)
    - Auto task assignment (84)
    - Overdue task detection & escalation (85, 86, 87)
    - Recurring inspection tasks (88–99)
    - Daily operations report (100)
    """
    with app.app_context():
        soc_id = full_env["society_id"]

        # Staff
        staff = Staff(society_id=soc_id, full_name="Ramesh Cleaner", role_type="Cleaner", phone="9876543411")
        tech = Staff(society_id=soc_id, full_name="Suresh Tech", role_type="Technician", phone="9876543412")
        db.session.add_all([staff, tech])
        db.session.commit()

        # Features 81, 82, 83: Checklists
        daily_chk = OperationsAutomationService.get_operations_checklist(soc_id, "daily")
        assert len(daily_chk["items"]) >= 4
        weekly_chk = OperationsAutomationService.get_operations_checklist(soc_id, "weekly")
        assert len(weekly_chk["items"]) >= 3
        monthly_chk = OperationsAutomationService.get_operations_checklist(soc_id, "monthly")
        assert len(monthly_chk["items"]) >= 3

        # Feature 84: Auto task assignment
        wo = OperationsAutomationService.auto_assign_maintenance_task(
            society_id=soc_id,
            title="Clean water fountain",
            description="Clean sediment from water fountain",
            category="Cleaner",
            priority="Medium",
        )
        assert wo.id is not None
        assert wo.assigned_staff_id == staff.id
        assert wo.status == "Assigned"

        # Features 85, 86, 87: Overdue task detection & escalation
        overdue_wo = WorkOrder(
            work_order_number="WO-OVERDUE-01",
            society_id=soc_id,
            title="Overdue Pump Repair",
            description="Fix pump valve",
            category="Plumber",
            priority="High",
            status="In Progress",
            due_date=utcnow().date() - timedelta(days=5),
        )
        db.session.add(overdue_wo)
        db.session.commit()

        overdue_res = OperationsAutomationService.detect_and_escalate_overdue_tasks(society_id=soc_id)
        assert overdue_res["overdue_tasks_count"] >= 1
        assert overdue_res["escalations_created"] >= 1

        # Features 88–99: Recurring inspection tasks
        for itype in ["lift", "generator", "fire_safety", "cctv", "electrical", "water_system", "housekeeping", "security", "pest_control", "plumbing", "common_area"]:
            rec_wo = OperationsAutomationService.create_recurring_inspection_task(society_id=soc_id, inspection_type=itype)
            assert rec_wo.id is not None
            assert rec_wo.category is not None

        # Feature 100: Daily Operations Report
        rep = OperationsAutomationService.generate_daily_operations_report(society_id=soc_id)
        assert "daily_checklist_items" in rep
        assert "open_work_orders" in rep


def test_phase7_parking_automation_suite(app, full_env):
    """
    Tests Features 101–110:
    - Allocation conflict detection (101)
    - Duplicate slot detection (102)
    - Availability report & vacant slot detection (105, 110)
    - Violation task & complaint processing (106, 107)
    - Parking notification & monthly report (108, 109)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        flat_id = full_env["flat_id"]
        res_user = db.session.get(User, full_env["resident_user_id"])

        slot1 = ParkingSlot(society_id=soc_id, slot_number="P-A101", location_block="Basement 1", slot_type="Car", flat_id=flat_id, status="Allocated")
        slot2 = ParkingSlot(society_id=soc_id, slot_number="P-A102", location_block="Basement 1", slot_type="Car", flat_id=None, status="Available")
        db.session.add_all([slot1, slot2])
        db.session.commit()

        veh = Vehicle(society_id=soc_id, flat_id=flat_id, vehicle_number="GJ-01-AB-1234", vehicle_type="Car", parking_slot_id=slot1.id)
        db.session.add(veh)
        db.session.commit()

        # Feature 101 & 102: Conflicts and Duplicate slots
        conflicts = ParkingAutomationService.detect_allocation_conflicts(society_id=soc_id)
        assert isinstance(conflicts, list)

        dupes = ParkingAutomationService.detect_duplicate_slots(society_id=soc_id)
        assert isinstance(dupes, list)

        # Feature 105: Availability Report
        avail = ParkingAutomationService.get_parking_availability_report(society_id=soc_id)
        assert avail["total_slots"] >= 2
        assert avail["allocated_slots"] >= 1
        assert avail["vacant_slots"] >= 1

        # Feature 110: Vacant Slots
        vacants = ParkingAutomationService.detect_vacant_slots(society_id=soc_id)
        assert len(vacants) >= 1

        # Feature 106 & 107: Unauthorized parking complaint & violation task
        comp = Complaint(
            society_id=soc_id,
            flat_id=flat_id,
            resident_id=full_env["resident_id"],
            ticket_number="TKT-PRK-99",
            title="Unauthorized Car in Slot P-A101",
            description="Unknown white sedan parked in my designated slot P-A101.",
            category="Parking",
            status="Submitted",
        )
        db.session.add(comp)
        db.session.commit()

        prk_res = ParkingAutomationService.process_parking_violations(society_id=soc_id)
        assert prk_res["violation_tasks_created"] >= 1

        # Feature 108: Notification
        notif_ok = ParkingAutomationService.send_parking_notification(res_user, "P-A101", "GJ-01-AB-1234")
        assert notif_ok is True

        # Feature 109: Monthly Parking Report
        prk_rep = ParkingAutomationService.generate_monthly_parking_report(society_id=soc_id)
        assert prk_rep["registered_vehicles"] >= 1


def test_phase8_inventory_automation_suite(app, full_env):
    """
    Tests Features 111–120:
    - Low/zero stock detection & reorder suggestions (111, 112, 113, 114)
    - Unusual consumption detection (115)
    - Inventory audit task creation (118)
    - Monthly inventory valuation report (117)
    """
    with app.app_context():
        soc_id = full_env["society_id"]

        # Low stock & zero stock items
        item_zero = InventoryItem(society_id=soc_id, item_name="LED Tubes 36W", category="Electrical", current_stock=0, minimum_threshold=10, unit="pcs", unit_cost=150.0)
        item_low = InventoryItem(society_id=soc_id, item_name="Floor Cleaner 5L", category="Cleaning", current_stock=3, minimum_threshold=5, unit="cans", unit_cost=300.0)
        item_ok = InventoryItem(society_id=soc_id, item_name="Trash Bags Large", category="Cleaning", current_stock=50, minimum_threshold=10, unit="rolls", unit_cost=80.0)
        db.session.add_all([item_zero, item_low, item_ok])
        db.session.commit()

        # Features 111, 112, 113, 114: Detection, Suggestions, Alerts
        stock_res = InventoryAutomationService.detect_low_and_zero_stock(society_id=soc_id)
        assert stock_res["zero_stock_count"] >= 1
        assert stock_res["low_stock_count"] >= 1
        assert len(stock_res["reorder_suggestions"]) >= 2
        assert stock_res["alerts_created"] >= 2

        # Feature 115: Unusual consumption
        txn = InventoryTransaction(
            society_id=soc_id,
            item_id=item_low.id,
            transaction_type="OUT",
            quantity=25,  # > 3x threshold
        )
        db.session.add(txn)
        db.session.commit()

        unusual = InventoryAutomationService.detect_unusual_consumption(society_id=soc_id)
        assert len(unusual) >= 1

        # Feature 118: Audit task
        audit_wo = InventoryAutomationService.create_inventory_audit_task(society_id=soc_id)
        assert audit_wo.id is not None
        assert audit_wo.category == "Inventory"

        # Feature 117: Monthly Inventory Report
        inv_rep = InventoryAutomationService.generate_monthly_inventory_report(society_id=soc_id)
        assert inv_rep["total_stock_valuation"] > 0
        assert inv_rep["total_items"] >= 3


def test_phase9_asset_automation_suite(app, full_env):
    """
    Tests Features 121–130:
    - Warranty & AMC expiry tracking (121, 122, 123, 124)
    - Overdue service detection & schedule (125, 126)
    - Depreciation calculation (127)
    - Missing info & asset health report (128, 130)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        now = utcnow().date()

        vendor = Vendor(society_id=soc_id, company_name="Schindler Elevator AMC", contact_person="Ravi", phone="9876543433", category="Lift", contract_end=now + timedelta(days=15))
        db.session.add(vendor)
        db.session.commit()

        asset1 = Asset(
            society_id=soc_id,
            asset_name="Main Passenger Lift 1",
            category="Lift",
            location="Wing A Shaft",
            purchase_date=now - timedelta(days=700),
            purchase_cost=800000.0,
            warranty_expiry=now + timedelta(days=20),
            vendor_id=vendor.id,
            last_service_date=now - timedelta(days=60),
            next_service_due=now - timedelta(days=5),  # Overdue
            status="Operational",
        )
        db.session.add(asset1)
        db.session.commit()

        # Features 121, 122, 123, 124, 125: Expiry & Service Due Scanner
        scan_res = AssetAutomationService.scan_expiries_and_service_due(society_id=soc_id, days_threshold=30)
        assert scan_res["expiring_warranties_count"] >= 1
        assert scan_res["expiring_amcs_count"] >= 1
        assert scan_res["overdue_services_count"] >= 1
        assert scan_res["tasks_created"] >= 1  # Pre-expiry inspection task

        # Feature 126: Maintenance schedule
        sched = AssetAutomationService.get_asset_maintenance_schedule(society_id=soc_id)
        assert len(sched) >= 1

        # Feature 127: Depreciation
        dep = AssetAutomationService.calculate_asset_depreciation(society_id=soc_id)
        assert len(dep) >= 1
        assert dep[0]["current_book_value"] < 800000.0

        # Feature 128: Missing info
        missing_info = AssetAutomationService.detect_missing_asset_info(society_id=soc_id)
        assert isinstance(missing_info, list)

        # Feature 130: Health Report
        health = AssetAutomationService.generate_asset_health_report(society_id=soc_id)
        assert health["asset_health_score"] == 100.0


def test_phase10_document_automation_suite(app, full_env):
    """
    Tests Features 131–140:
    - Auto categorization & type detection (131, 132)
    - Duplicate & missing required document detection (136, 137)
    - Document review task (138) & document inventory report (140)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        admin = db.session.get(User, full_env["admin_id"])

        # Feature 131 & 132: Categorization
        cat_res = DocumentAutomationService.auto_categorize_document("Annual Fire Safety NOC 2026", "fire_noc_2026.pdf")
        assert cat_res["inferred_category"] == "Compliance"
        assert cat_res["document_type"] == "pdf"

        # Seed document
        doc1 = Document(society_id=soc_id, title="Fire Safety Certificate", category="Compliance", file_path="docs/fire.pdf", uploaded_by_id=admin.id)
        db.session.add(doc1)
        db.session.commit()

        # Feature 136: Duplicate documents
        dupes = DocumentAutomationService.detect_duplicate_documents(society_id=soc_id)
        assert isinstance(dupes, list)

        # Feature 137: Missing required documents
        missing_req = DocumentAutomationService.detect_missing_required_documents(society_id=soc_id)
        assert len(missing_req) >= 1
        assert "Lift Fitness Certificate" in missing_req

        # Feature 138: Review task
        audit_task = DocumentAutomationService.create_document_review_task(society_id=soc_id)
        assert audit_task.id is not None
        assert audit_task.category == "Compliance"

        # Feature 140: Inventory report
        inv_rep = DocumentAutomationService.get_document_inventory_report(society_id=soc_id)
        assert inv_rep["total_documents"] >= 1


def test_phase11_notification_automation_suite(app, full_env):
    """
    Tests Features 141–150:
    - Priority & quiet hours check (141, 144)
    - Smart notification sending with deduplication (143)
    - Retry queue processing (145, 146)
    - Admin & resident digests (148, 149, 150)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        res_user_id = full_env["resident_user_id"]

        # Feature 144: Quiet hours check
        night_time = datetime(2026, 3, 30, 23, 30)
        day_time = datetime(2026, 3, 30, 14, 0)
        assert NotificationAutomationService.is_quiet_hours(night_time) is True
        assert NotificationAutomationService.is_quiet_hours(day_time) is False

        # Feature 141 & 143: Smart notification & deduplication
        msg = "Water supply will be shut down tomorrow between 2 PM and 5 PM for tank cleaning."
        n1 = NotificationAutomationService.send_smart_notification(res_user_id, soc_id, msg, priority="Normal")
        assert n1 is not None

        # Duplicate send within 24 hours should be suppressed / return existing
        n2 = NotificationAutomationService.send_smart_notification(res_user_id, soc_id, msg, priority="Normal")
        assert n2.id == n1.id

        # Feature 145 & 146: Retry queue
        retried = NotificationAutomationService.process_retry_queue(society_id=soc_id)
        assert isinstance(retried, list)

        # Feature 148: Admin digest
        digest = NotificationAutomationService.generate_admin_digest(society_id=soc_id)
        assert "Daily Society Admin Digest" in digest["digest_text"]

        # Feature 149 & 150: Resident summary
        res_summary = NotificationAutomationService.generate_weekly_resident_summary(res_user_id, soc_id)
        assert "unpaid_bills_count" in res_summary


def test_phase12_ai_prediction_suite(app, full_env):
    """
    Tests Features 151–170:
    - Overdue resident prediction & repeat late payers (151, 153)
    - Communication strategy recommendation (154, 155)
    - Complaint clustering, routing, and ETA predictions (161, 164, 165)
    - Complaint to suggested task conversion (163)
    - Vendor performance evaluation (168, 169)
    - Alert summarization & prioritization (159, 160)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        flat_id = full_env["flat_id"]
        res_id = full_env["resident_id"]

        # Feature 151 & 153: Predict overdue residents
        predictions = AIPredictionService.predict_overdue_residents(society_id=soc_id)
        assert len(predictions) >= 1
        assert "predicted_risk" in predictions[0]

        # Features 154 & 155: Strategy recommendation
        strat = AIPredictionService.recommend_communication_strategy(resident_id=res_id)
        assert strat["recommended_reminder_day"] == 5

        # Seed complaint
        comp = Complaint(
            society_id=soc_id,
            resident_id=res_id,
            flat_id=flat_id,
            ticket_number="TKT-ELEC-01",
            title="Corridor light sparking",
            description="Corridor light switch is sparking near Flat 501",
            category="Electrical",
            priority="High",
            status="Submitted",
        )
        db.session.add(comp)
        db.session.commit()

        # Features 161, 164, 165: Complaint AI Analysis
        comp_ai = AIPredictionService.analyze_complaints_ai(society_id=soc_id)
        assert "clusters_by_category" in comp_ai
        assert "Electrical" in comp_ai["clusters_by_category"]

        # Feature 163: Convert complaint to suggested task
        task_sugg = AIPredictionService.convert_complaint_to_suggested_task(comp.id)
        assert "suggested_task_title" in task_sugg

        # Features 168 & 169: Vendor performance analysis
        vendor_ratings = AIPredictionService.analyze_vendor_performance(society_id=soc_id)
        assert isinstance(vendor_ratings, list)

        # Features 159 & 160: Alert digest & prioritization
        alert_digest = AIPredictionService.summarize_and_prioritize_alerts(society_id=soc_id)
        assert "total_active_alerts" in alert_digest


def test_phase13_ai_communication_and_assistants(app, full_env):
    """
    Tests Features 171–190:
    - AI Invoice summary (171, 172)
    - AI Meeting summary & action items (176, 177, 178)
    - AI Agenda & circular generation (180, 181)
    - Multilingual translation (182)
    - Broadcast message generators (183, 184, 185)
    - AI Admin knowledge-base assistant (189)
    - AI Resident knowledge assistant (190)
    """
    with app.app_context():
        soc_id = full_env["society_id"]
        res_user_id = full_env["resident_user_id"]

        # Features 171 & 172: Invoice summary & data extraction
        inv_sum = AICommunicationService.summarize_invoice(
            vendor_name="Apex Elevators",
            invoice_number="INV-2026-99",
            amount=12500.0,
            items=["Quarterly Lift AMC Service", "Governor Rope Replacement"]
        )
        assert inv_sum["total_amount"] == 12500.0
        assert "Apex Elevators" in inv_sum["summary"]

        # Features 176, 177, 178: Meeting summary & action items
        notes = "Reviewed security guards performance.\n- Repair underground water pump immediately\n- Inspect basement parking illumination\n- Follow up on unpaid maintenance collections"
        meet_res = AICommunicationService.generate_meeting_summary_and_actions(
            meeting_title="March Monthly Committee Meeting",
            notes_text=notes,
        )
        assert meet_res["total_actions"] >= 2
        assert any(a["recommended_priority"] == "High" for a in meet_res["action_items"])

        # Features 180 & 181: Meeting agenda and circular
        agenda = AICommunicationService.generate_meeting_agenda(
            topic="Annual Budget & Monsoon Preparedness",
            discussion_points=["Waterproofing inspection", "Drainage cleaning", "Festival celebrations"]
        )
        assert "AGENDA ITEMS" in agenda["agenda_text"]

        circular = AICommunicationService.generate_society_circular(
            title="Monsoon Preparedness & Balcony Drainage",
            body="Please ensure balcony drain outlets are kept clear of leaves and debris."
        )
        assert "CIRCULAR:" in circular["circular_text"]

        # Feature 182: Multilingual translation
        trans_gu = AICommunicationService.translate_message("Society Maintenance Notice", "Gujarati")
        assert "ગુજરાતી" in trans_gu["translated_text"]

        trans_hi = AICommunicationService.translate_message("Society Maintenance Notice", "Hindi")
        assert "हिंदी" in trans_hi["translated_text"]

        # Features 183, 184, 185: Broadcast message drafts
        bcasts = AICommunicationService.generate_broadcast_messages(
            message_type="water_shutdown",
            context={"text": "Water shutdown tomorrow from 10 AM to 1 PM for overhead tank cleaning."}
        )
        assert "SOCIETY UPDATE" in bcasts["whatsapp_message"]
        assert len(bcasts["sms_message"]) <= 160
        assert "Attention all residents" in bcasts["voice_announcement_script"]

        # Feature 189: AI Admin Assistant Live Database Queries
        # 1. Residents query
        ans_res = AICommunicationService.answer_admin_assistant_query(soc_id, "How many residents are registered?")
        assert "registered resident" in ans_res.lower()

        # 2. Pending maintenance query
        ans_maint = AICommunicationService.answer_admin_assistant_query(soc_id, "How much maintenance is pending?")
        assert "pending maintenance" in ans_maint.lower() or "unpaid" in ans_maint.lower()

        # 3. Monthly collection query
        ans_coll = AICommunicationService.answer_admin_assistant_query(soc_id, "How much was collected this month?")
        assert "collected" in ans_coll.lower()

        # 4. Complaints query
        ans_comp = AICommunicationService.answer_admin_assistant_query(soc_id, "How many complaints are unresolved?")
        assert "unresolved complaint" in ans_comp.lower()

        # 5. Verification query
        ans_ver = AICommunicationService.answer_admin_assistant_query(soc_id, "Which payments need verification?")
        assert "unverified cash" in ans_ver.lower()

        # Feature 190: AI Resident Assistant Strictly Scoped Database Queries
        # 1. Pending amount
        res_due_ans = AICommunicationService.answer_resident_assistant_query(res_user_id, soc_id, "What is my pending amount?")
        assert "Mega Resident" in res_due_ans
        assert "outstanding maintenance" in res_due_ans

        # 2. Next due
        res_next_ans = AICommunicationService.answer_resident_assistant_query(res_user_id, soc_id, "When is my next bill due?")
        assert "maintenance" in res_next_ans

        # 3. Complaint help
        res_comp_ans = AICommunicationService.answer_resident_assistant_query(res_user_id, soc_id, "How do I submit a complaint?")
        assert "Complaint Desk" in res_comp_ans

        # 4. Receipt download help
        res_rcpt_ans = AICommunicationService.answer_resident_assistant_query(res_user_id, soc_id, "How do I download my receipt?")
        assert "Receipts" in res_rcpt_ans
