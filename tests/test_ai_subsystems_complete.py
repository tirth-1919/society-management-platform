"""
Comprehensive Test Suite for AI Subsystems (Part 2)
===================================================
Tests:
8. AI Energy Intelligence (Meter logs, surge detection, time-series forecast, insufficient data fallback)
9. AI Parking Intelligence (Slot occupancy, duplicate plates across units, repeated violations, peak hours)
15. AI Complaint Intelligence (Triage, cluster detection, SLA recommendations)
17. AI Document Verification (Metadata extraction, expiry warnings, human verification, privacy)
18. AI Duplicate & Identity Resolution (Fuzzy match, non-destructive resolution, audit)
19. AI Fraud Investigation Workspace (Trigger scanning, case generation, timeline, status updates)
21. AI Society Digital Twin (Topology graph, entity inspector, cross-system correlation)
Security & Multi-Tenant Isolation (RBAC, Society 1 vs Society 2 boundary enforcement)
"""

import pytest
from datetime import timedelta
from app.models import (
    db,
    User,
    Role,
    Society,
    Building,
    Flat,
    Resident,
    ParkingSlot,
    Vehicle,
    Complaint,
    Document,
    ExpenseVoucher,
)
from app.models.ai_operations import (
    AIFinding,
    AIInvestigation,
    AIDocumentAnalysis,
    AIDuplicateCandidate,
    AIEnergyReading,
    AIParkingEvent,
)
from app.services.ai import (
    EnergyIntelligenceAIService,
    ParkingIntelligenceAIService,
    ComplaintIntelligenceAIService,
    DocumentVerificationAIService,
    DuplicateResolutionAIService,
    FraudInvestigationAIService,
    DigitalTwinAIService,
)
from app.utils import utcnow


@pytest.fixture
def sub_setup(app):
    with app.app_context():
        # Clear AI tables
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

        # Seed Flats
        b1 = Building.query.filter_by(society_id=s1.id).first()
        f1 = Flat.query.filter_by(society_id=s1.id).first()
        f2 = Flat(society_id=s1.id, building_id=b1.id, flat_number="A-102")
        db.session.add(f2)
        db.session.commit()

        # Seed Residents for Duplicate & Identity tests
        r1 = Resident(
            society_id=s1.id,
            flat_id=f1.id,
            full_name="Rajesh Kumar Patel",
            mobile="9825012345",
            email="rajesh.patel@example.com",
            occupancy_status="Active",
        )
        r2 = Resident(
            society_id=s1.id,
            flat_id=f1.id,
            full_name="Rajesh K Patel",
            mobile="9825012345",
            email="rajesh.patel@example.com",
            occupancy_status="Active",
        )
        db.session.add_all([r1, r2])
        db.session.commit()

        yield {"s1": s1, "s2": s2, "admin": admin, "f1": f1, "f2": f2, "r1": r1, "r2": r2}


def test_energy_intelligence_forecast_and_insufficient_data(app, sub_setup):
    """Verify energy forecasting handles insufficient data safely and detects consumption surges."""
    with app.app_context():
        s1 = sub_setup["s1"]

        # Case A: Insufficient data (<14 readings)
        for i in range(5):
            rd = AIEnergyReading(
                society_id=s1.id,
                meter_name="Main Grid Transformer",
                meter_type="COMMON_AREA",
                reading_date=utcnow().date() - timedelta(days=5 - i),
                units_kwh=100.0,
                cost_amount=850.0,
            )
            db.session.add(rd)
        db.session.commit()

        forecast_sparse = EnergyIntelligenceAIService.generate_energy_forecast(s1.id)
        assert forecast_sparse["has_sufficient_data"] is False
        assert "Insufficient historical data" in forecast_sparse["message"]

        # Case B: Sufficient data (>=14 readings) + Surge reading
        for i in range(15):
            rd = AIEnergyReading(
                society_id=s1.id,
                meter_name="Main Grid Transformer",
                meter_type="COMMON_AREA",
                reading_date=utcnow().date() - timedelta(days=20 - i),
                units_kwh=100.0,
                cost_amount=850.0,
            )
            db.session.add(rd)
        # Add a sudden surge reading
        rd_surge = AIEnergyReading(
            society_id=s1.id,
            meter_name="Main Grid Transformer",
            meter_type="COMMON_AREA",
            reading_date=utcnow().date(),
            units_kwh=180.0,  # 80% surge
            cost_amount=1530.0,
        )
        db.session.add(rd_surge)
        db.session.commit()

        forecast_full = EnergyIntelligenceAIService.generate_energy_forecast(s1.id)
        assert forecast_full["has_sufficient_data"] is True
        assert forecast_full["next_7_days_kwh"] > 0
        assert forecast_full["estimated_cost_inr"] > 0

        anomalies = EnergyIntelligenceAIService.analyze_consumption_anomalies(s1.id)
        assert len(anomalies) > 0
        assert anomalies[0]["difference_pct"] >= 20.0


def test_parking_intelligence_duplicate_vehicles_and_occupancy(app, sub_setup):
    """Verify parking intelligence calculates occupancy and detects duplicate vehicle registrations."""
    with app.app_context():
        s1 = sub_setup["s1"]
        f1 = sub_setup["f1"]
        f2 = sub_setup["f2"]

        # Register same vehicle number plate under two different flats
        v1 = Vehicle(
            society_id=s1.id,
            flat_id=f1.id,
            vehicle_number="GJ-01-AB-1234",
            status="ACTIVE",
            make="Hyundai",
            model="Creta",
        )
        v2 = Vehicle(
            society_id=s1.id,
            flat_id=f2.id,
            vehicle_number="GJ01AB1234",  # normalized match
            status="ACTIVE",
            make="Hyundai",
            model="Creta",
        )
        db.session.add_all([v1, v2])

        # Seed slots
        s_slot = ParkingSlot(society_id=s1.id, slot_number="P1-A01", flat_id=f1.id, status="Allocated")
        db.session.add(s_slot)
        db.session.commit()

        overview = ParkingIntelligenceAIService.get_parking_overview_and_forecast(s1.id)
        assert overview["total_slots"] >= 1
        assert overview["occupancy_rate_pct"] > 0

        anomalies = ParkingIntelligenceAIService.scan_parking_anomalies(s1.id)
        assert len(anomalies) > 0
        dup_veh = [a for a in anomalies if a["type"] == "DUPLICATE_VEHICLE_REGISTRATION"]
        assert len(dup_veh) > 0


def test_complaint_intelligence_clusters(app, sub_setup):
    """Verify complaint intelligence detects duplicate ticket clusters."""
    with app.app_context():
        s1 = sub_setup["s1"]
        f1 = sub_setup["f1"]
        r1 = sub_setup["r1"]

        for i in range(4):
            c = Complaint(
                ticket_number=f"TCK-WATER-{i}",
                society_id=s1.id,
                flat_id=f1.id,
                resident_id=r1.id,
                category="Plumbing",
                title="Low water pressure in morning",
                description="Water pressure is very weak on 4th floor",
                status="Submitted",
                created_at=utcnow() - timedelta(days=2),
            )
            db.session.add(c)
        db.session.commit()

        clusters = ComplaintIntelligenceAIService.scan_complaint_clusters(s1.id)
        assert len(clusters) > 0
        assert clusters[0]["cluster_name"] == "Water Supply & Pressure"
        assert clusters[0]["count"] >= 3


def test_document_verification_and_expiry(app, sub_setup):
    """Verify document AI classification, expiry alerts, and human verification actions."""
    with app.app_context():
        s1 = sub_setup["s1"]
        admin = sub_setup["admin"]

        doc = Document(
            society_id=s1.id,
            title="Fire Safety Certificate 2024",
            category="Society Bye-Laws",
            file_path="docs/fire_cert.pdf",
            uploaded_by_id=admin.id,
        )
        db.session.add(doc)
        db.session.commit()

        sample_text = "Fire Safety Clearance Certificate. Valid Thru: 2024-01-01. Authority: State Fire Service"
        analysis = DocumentVerificationAIService.verify_document_ai(doc.id, s1.id, raw_text=sample_text)
        assert analysis.is_expired is True
        assert analysis.detected_category == "NOC / Statutory Certificate"

        # Human verification action
        verified_analysis = DocumentVerificationAIService.set_verification_status(
            analysis_id=analysis.id,
            society_id=s1.id,
            actor_id=admin.id,
            status="VERIFIED",
        )
        assert verified_analysis.verification_status == "VERIFIED"


def test_duplicate_identity_resolution(app, sub_setup):
    """Verify fuzzy duplicate resident identity resolution and non-destructive decision."""
    with app.app_context():
        s1 = sub_setup["s1"]
        admin = sub_setup["admin"]
        r1 = sub_setup["r1"]
        r2 = sub_setup["r2"]

        candidates = DuplicateResolutionAIService.scan_duplicate_residents(s1.id, actor_id=admin.id)
        assert len(candidates) > 0
        assert candidates[0]["confidence"] >= 0.70

        candidate_obj = AIDuplicateCandidate.query.filter_by(
            society_id=s1.id,
            primary_entity_id=r1.id,
            duplicate_entity_id=r2.id,
        ).first()
        assert candidate_obj is not None

        # Resolve candidate as NOT_DUPLICATE
        resolved = DuplicateResolutionAIService.resolve_candidate(
            candidate_id=candidate_obj.id,
            society_id=s1.id,
            actor_id=admin.id,
            action="NOT_DUPLICATE",
            notes="Verified distinct family members",
        )
        assert resolved.status == "NOT_DUPLICATE"


def test_fraud_investigation_workspace(app, sub_setup):
    """Verify fraud investigation trigger scanning, case creation, and status progression."""
    with app.app_context():
        s1 = sub_setup["s1"]
        admin = sub_setup["admin"]

        # Seed repeated expense vouchers with duplicate invoice numbers for high value
        for i in range(4):
            v = ExpenseVoucher(
                voucher_number=f"EV-FRAUD-{i}",
                society_id=s1.id,
                category="Repairs",
                amount=12000.0,
                payee_name="XYZ Building Fixers",
                description="Roof leakage repair",
                invoice_number="XYZ-INV-001",  # duplicate invoice number
                expense_date=utcnow().date(),
            )
            db.session.add(v)
        db.session.commit()

        cases = FraudInvestigationAIService.scan_for_investigation_triggers(s1.id, actor_id=admin.id)
        assert len(cases) > 0
        case = cases[0]
        assert case.case_id.startswith("INV-")
        assert case.status == "OPEN"
        assert len(case.get_timeline()) > 0

        # Update case status
        updated = FraudInvestigationAIService.update_case_status(
            case_id_or_pk=case.id,
            society_id=s1.id,
            actor_id=admin.id,
            status="UNDER_REVIEW",
            admin_notes="Assigned auditor to contact vendor.",
        )
        assert updated.status == "UNDER_REVIEW"
        assert "Assigned auditor" in updated.admin_notes


def test_digital_twin_topology_and_isolation(app, sub_setup):
    """Verify Digital Twin graph synthesis, entity relationships, and strict tenant isolation."""
    with app.app_context():
        s1 = sub_setup["s1"]
        s2 = sub_setup["s2"]
        f1 = sub_setup["f1"]

        # Society 1 Graph
        graph1 = DigitalTwinAIService.get_society_overview_graph(s1.id)
        assert graph1["society"]["id"] == s1.id
        assert graph1["metrics"]["total_flats"] >= 2
        assert len(graph1["nodes"]) >= 2

        # Entity detail view
        flat_detail = DigitalTwinAIService.get_entity_detail_view("FLAT", f1.id, s1.id)
        assert flat_detail["title"] == f"Flat {f1.flat_number}"
        assert len(flat_detail["residents"]) >= 2

        # Cross-society isolation check: Society 2 cannot view Society 1's flat
        flat_isolation = DigitalTwinAIService.get_entity_detail_view("FLAT", f1.id, s2.id)
        assert "error" in flat_isolation


def test_ai_routes_rbac_and_isolation(client, app, sub_setup):
    """Verify residents cannot access admin AI dashboards, and cross-society leaks are blocked."""
    with app.app_context():
        s1 = sub_setup["s1"]

        # Create a resident user
        res_user = User(
            username="resident_user",
            full_name="Regular Resident",
            mobile="9800000001",
            email="resident@test.com",
            role=Role.RESIDENT,
            society_id=s1.id,
            account_status="ACTIVE",
            is_active=True,
        )
        res_user.set_password("Resident@123")
        db.session.add(res_user)
        db.session.commit()

        # Login as resident
        with client.session_transaction() as sess:
            sess["user_id"] = res_user.id
            sess["role"] = Role.RESIDENT
            sess["society_id"] = s1.id

        # Resident attempts to access admin AI operations dashboard -> 403 Forbidden
        resp1 = client.get("/admin/ai")
        assert resp1.status_code in [403, 302]

        resp2 = client.get("/admin/ai/investigations")
        assert resp2.status_code in [403, 302]

        resp3 = client.get("/admin/ai/findings")
        assert resp3.status_code in [403, 302]

        resp4 = client.get("/api/v1/ai/operations/dashboard")
        assert resp4.status_code in [403, 401]

        # Login as Super Admin
        admin = sub_setup["admin"]
        with client.session_transaction() as sess:
            sess["user_id"] = admin.id
            sess["role"] = Role.SUPER_ADMIN
            sess["society_id"] = s1.id

        resp_admin = client.get("/admin/ai")
        assert resp_admin.status_code == 200
        assert b"Society Operations Intelligence Platform" in resp_admin.data
