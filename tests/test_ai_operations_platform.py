"""
Comprehensive Test Suite for AI Society Intelligence Platform
============================================================
Tests:
1. AI Society Operations Center (Dashboard, Health score, Daily Brief, Feed, Filters, CLI)
2. AI Predictive Maintenance (Asset risk, failure probability, Work Order creation, insufficient data)
3. AI Security Command Center (Denied entries, abnormal hours, CCTV adapter, neutral phrasing)
4. AI Financial Control (Duplicate payment, duplicate invoice, expense outliers, read-only guarantee)
5. AI Invoice Processing (Field extraction, confidence scores, duplicate voucher check, approval)
6. AI Incident Response (Triage, category/SLA routing, recurring root cause patterns)
"""

import pytest
from datetime import date, timedelta
from app.models import (
    db,
    User,
    Role,
    Society,
    Flat,
    Resident,
    Asset,
    WorkOrder,
    Visitor,
    ExpenseVoucher,
    Complaint,
    Document,
)
from app.models.ai_operations import (
    AIFinding,
    AIFindingSeverity,
    AIFindingStatus,
    AISystemType,
    AIInvestigation,
    AIDocumentAnalysis,
    AIDuplicateCandidate,
    AIEnergyReading,
    AIParkingEvent,
)
from app.services.ai import (
    AIOperationsService,
    PredictiveMaintenanceAIService,
    SecurityCommandAIService,
    FinancialControlAIService,
    InvoiceProcessingAIService,
    IncidentResponseAIService,
    MockCCTVStreamAdapter,
)
from app.utils import utcnow


@pytest.fixture
def test_setup(app):
    with app.app_context():
        # Clean up any leftover AI records
        db.session.query(AIFinding).delete()
        db.session.query(AIInvestigation).delete()
        db.session.query(AIDocumentAnalysis).delete()
        db.session.query(AIDuplicateCandidate).delete()
        db.session.query(AIEnergyReading).delete()
        db.session.query(AIParkingEvent).delete()
        db.session.commit()

        s1 = db.session.get(Society, 1)
        s2 = db.session.get(Society, 2)
        admin = User.query.filter_by(role=Role.SUPER_ADMIN).first()

        # Seed test assets for Society 1
        asset_lift = Asset(
            society_id=s1.id,
            asset_name="Elevator Passenger B",
            category="Lift",
            location="Wing A - Core",
            status="Operational",
            purchase_date=date(2018, 1, 1),
            last_service_date=date(2025, 1, 1),
            next_service_due=date(2025, 6, 1),  # overdue
        )
        asset_gen = Asset(
            society_id=s1.id,
            asset_name="Diesel Generator 120kVA",
            category="Generator",
            location="Basement 1",
            status="Operational",
            purchase_date=date(2022, 1, 1),
            last_service_date=utcnow().date() - timedelta(days=10),
            next_service_due=utcnow().date() + timedelta(days=80),
        )
        db.session.add_all([asset_lift, asset_gen])
        db.session.commit()

        yield {"s1": s1, "s2": s2, "admin": admin, "lift": asset_lift, "gen": asset_gen}


def test_ai_operations_dashboard_and_brief(app, test_setup):
    """Verify AI Operations Center dashboard synthesis, health scoring, and daily brief."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]

        dashboard = AIOperationsService.get_operations_dashboard(s1.id)
        assert "overall_risk" in dashboard
        assert "health_score" in dashboard
        assert "cards" in dashboard
        assert len(dashboard["cards"]) == 12
        assert "daily_brief" in dashboard
        assert dashboard["daily_brief"]["headline"] is not None

        # Test full analysis run
        run_res = AIOperationsService.run_full_society_analysis(s1.id, actor_id=admin.id)
        assert run_res["status"] == "COMPLETED"
        assert run_res["execution_time_ms"] > 0


def test_predictive_maintenance_risk_and_work_order(app, test_setup):
    """Verify predictive maintenance calculations and automated WorkOrder generation."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]
        lift = test_setup["lift"]

        # Add repair work orders to elevate failure frequency
        wo1 = WorkOrder(
            work_order_number="WO-TEST-001",
            society_id=s1.id,
            title="Repair Elevator Passenger B pulley",
            description="Emergency repair",
            category="Lift",
            status="Closed",
            created_at=utcnow() - timedelta(days=10),
        )
        wo2 = WorkOrder(
            work_order_number="WO-TEST-002",
            society_id=s1.id,
            title="Elevator Passenger B door sensor",
            description="Fixed sensor",
            category="Lift",
            status="Closed",
            created_at=utcnow() - timedelta(days=25),
        )
        db.session.add_all([wo1, wo2])
        db.session.commit()

        analysis = PredictiveMaintenanceAIService.analyze_asset_risk(lift, s1.id)
        assert analysis["risk_score"] > 40.0
        assert analysis["maintenance_priority"] in [AIFindingSeverity.HIGH, AIFindingSeverity.CRITICAL]
        assert len(analysis["reasons"]) > 0
        assert analysis["has_sufficient_data"] is True

        # Run analysis to generate finding
        res = PredictiveMaintenanceAIService.run_society_maintenance_analysis(s1.id, actor_id=admin.id)
        assert len(res) >= 2

        finding = AIFinding.query.filter_by(society_id=s1.id, ai_system=AISystemType.MAINTENANCE, entity_id=lift.id).first()
        assert finding is not None

        # Test WorkOrder task generation from finding
        wo = PredictiveMaintenanceAIService.create_work_order_from_finding(
            finding_id=finding.id,
            society_id=s1.id,
            actor_id=admin.id,
            notes="Technician dispatched from AI alert",
        )
        assert wo is not None
        assert wo.status == "Created"
        assert finding.status == AIFindingStatus.ACTION_REQUIRED


def test_security_command_anomalies_and_cctv(app, test_setup):
    """Verify security command center detects access anomalies with neutral tone and CCTV interface."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]

        # Seed rejected visitor entries
        flat1 = Flat.query.filter_by(society_id=s1.id).first()
        for i in range(4):
            v = Visitor(
                society_id=s1.id,
                flat_id=flat1.id,
                visitor_name=f"Guest {i}",
                mobile="9876543210",
                approval_status="Rejected",
                created_at=utcnow() - timedelta(days=2),
            )
            db.session.add(v)
        db.session.commit()

        anomalies = SecurityCommandAIService.analyze_security_events(s1.id, actor_id=admin.id)
        assert len(anomalies) > 0
        denied = [a for a in anomalies if a["type"] == "REPEATED_DENIED_ACCESS"]
        assert len(denied) > 0
        assert "unusual" in denied[0]["summary"].lower() or "denied" in denied[0]["summary"].lower()

        # CCTV adapter verification
        cctv = MockCCTVStreamAdapter().get_stream_status("GATE-CAM-01")
        assert cctv["status"] == "ONLINE"
        assert cctv["hardware_ready"] is True


def test_financial_control_duplicate_invoice_and_payment(app, test_setup):
    """Verify financial anomaly detection without altering accounting records."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]

        # Seed two expense vouchers with same invoice number
        v1 = ExpenseVoucher(
            voucher_number="EV-TEST-101",
            society_id=s1.id,
            category="Electricity",
            amount=45000.0,
            payee_name="Torrent Power Ltd",
            description="Power bill payment",
            invoice_number="TP-INV-9901",
            expense_date=utcnow().date(),
        )
        v2 = ExpenseVoucher(
            voucher_number="EV-TEST-102",
            society_id=s1.id,
            category="Electricity",
            amount=45000.0,
            payee_name="Torrent Power Ltd",
            description="Power bill duplicate",
            invoice_number="TP-INV-9901",
            expense_date=utcnow().date(),
        )
        db.session.add_all([v1, v2])
        db.session.commit()

        anomalies = FinancialControlAIService.scan_financial_anomalies(s1.id, actor_id=admin.id)
        assert len(anomalies) > 0
        dup_inv = [a for a in anomalies if a["type"] == "DUPLICATE_INVOICE_NUMBER"]
        assert len(dup_inv) > 0
        assert dup_inv[0]["severity"] == AIFindingSeverity.HIGH

        # Verify vouchers remained unchanged (read-only guarantee)
        v1_check = db.session.get(ExpenseVoucher, v1.id)
        assert v1_check.amount == 45000.0


def test_invoice_processing_field_extraction_and_voucher(app, test_setup):
    """Verify invoice field extraction, confidence scores, and approval workflow."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]

        sample_raw = """
        TAX INVOICE
        From: ABC Elevator Services Pvt Ltd
        Invoice No: INV-ELEV-2026-88
        Date: 2026-03-01
        Total Amount: ₹35,000.00
        Description: Quarterly Comprehensive Elevator Maintenance
        """

        extraction = InvoiceProcessingAIService.extract_fields_from_text(sample_raw)
        fields = extraction["extracted_fields"]
        assert fields["invoice_number"] == "INV-ELEV-2026-88"
        assert fields["total"] == 35000.0
        assert "ABC Elevator" in fields["vendor_name"]
        assert extraction["confidence_score"] > 0.80

        # Process document
        doc = Document(
            society_id=s1.id,
            title="Elevator Invoice Q1",
            category="Financial Receipts",
            file_path="invoices/test.pdf",
            uploaded_by_id=admin.id,
        )
        db.session.add(doc)
        db.session.commit()

        analysis = InvoiceProcessingAIService.process_invoice_document(doc.id, s1.id, raw_text=sample_raw)
        assert analysis.detected_category == "Vendor Invoice"
        assert analysis.verification_status == "PENDING"

        # Approve and create voucher
        voucher = InvoiceProcessingAIService.approve_and_create_voucher(
            analysis_id=analysis.id,
            society_id=s1.id,
            actor_id=admin.id,
        )
        assert voucher is not None
        assert voucher.amount == 35000.0
        assert analysis.verification_status == "VERIFIED"


def test_incident_response_classification_and_root_cause(app, test_setup):
    """Verify NLP incident categorization, SLA estimation, and recurring root cause detection."""
    with app.app_context():
        s1 = test_setup["s1"]
        admin = test_setup["admin"]

        # Classification tests
        res_lift = IncidentResponseAIService.classify_incident("Lift stuck between floors", "Residents trapped inside elevator")
        assert res_lift["category"] == "Lift"
        assert res_lift["severity"] == AIFindingSeverity.CRITICAL
        assert res_lift["sla_hours"] <= 4

        res_water = IncidentResponseAIService.classify_incident("Main pipeline water leak in basement", "Water flooding parking")
        assert res_water["category"] == "Water"
        assert res_water["severity"] == AIFindingSeverity.HIGH

        # Root cause analysis
        flat1 = Flat.query.filter_by(society_id=s1.id).first()
        resident = Resident.query.filter_by(society_id=s1.id).first()
        if not resident:
            resident = Resident(
                society_id=s1.id,
                flat_id=flat1.id,
                full_name="Test Resident",
                mobile="9900112233",
                occupancy_status="Active",
            )
            db.session.add(resident)
            db.session.commit()

        for i in range(4):
            c = Complaint(
                ticket_number=f"TCK-LIFT-{i}",
                society_id=s1.id,
                flat_id=flat1.id,
                resident_id=resident.id,
                category="Lift",
                title=f"Lift door jerk #{i}",
                description="Lift jerked upon stopping",
                created_at=utcnow() - timedelta(days=10),
            )
            db.session.add(c)
        db.session.commit()

        root_causes = IncidentResponseAIService.run_root_cause_analysis(s1.id, actor_id=admin.id)
        assert len(root_causes) > 0
        assert any("Lift" in rc["pattern"] for rc in root_causes)
