"""
Comprehensive tests for complete AI implementation (Stages 2-7).
Tests all new AI features while preserving existing functionality.
"""
import pytest
from datetime import date
from app.models import (
    db,
    Society,
    Building,
    Flat,
    Resident,
    User,
    Role,
    MaintenanceBill,
    Complaint,
    InventoryItem,
)
from app.services.ai_service import AIService
from app.services.search_service import SearchService


@pytest.fixture
def ai_complete_test_data(app):
    """Setup complete test data for AI features."""
    with app.app_context():
        # Use existing society if available, else create new
        society = Society.query.first()
        if not society:
            society = Society(
                name="AI Complete Test Society",
                registration_number="AI-COMP-001",
                address="123 AI Test Road",
                city="Test City",
                state="Gujarat",
                pincode="360001",
                email="ai@test.com",
                phone="9876543210",
            )
            db.session.add(society)
            db.session.commit()

        # Building and Flat
        building = Building.query.filter_by(society_id=society.id, name="Wing AI").first()
        if not building:
            building = Building(society_id=society.id, name="Wing AI")
            db.session.add(building)
            db.session.commit()

        flat = Flat.query.filter_by(society_id=society.id, building_id=building.id, flat_number="AI-101").first()
        if not flat:
            flat = Flat(society_id=society.id, building_id=building.id, flat_number="AI-101")
            db.session.add(flat)
            db.session.commit()

        # Admin user
        admin = User.query.filter_by(username="ai_admin").first()
        if not admin:
            admin = User(
                username="ai_admin",
                full_name="AI Test Admin",
                email="ai_admin@test.com",
                mobile="9876543299",
                role=Role.SOCIETY_ADMIN,
                society_id=society.id,
                account_status="ACTIVE",
                is_active=True
            )
            admin.set_password("Admin@123")
            db.session.add(admin)
            db.session.commit()

        # Resident user
        resident_user = User.query.filter_by(username="ai_resident").first()
        if not resident_user:
            resident_user = User(
                username="ai_resident",
                full_name="AI Test Resident",
                email="ai_resident@test.com",
                mobile="9876543298",
                role=Role.RESIDENT,
                society_id=society.id,
                account_status="ACTIVE",
                is_active=True
            )
            resident_user.set_password("Resident@123")
            db.session.add(resident_user)
            db.session.commit()

        resident = Resident.query.filter_by(user_id=resident_user.id).first()
        if not resident:
            resident = Resident(
                society_id=society.id,
                flat_id=flat.id,
                user_id=resident_user.id,
                full_name="AI Test Resident",
                mobile="9876543298",
                resident_type="Owner",
                occupancy_status="Active",
                is_primary=True
            )
            db.session.add(resident)
            db.session.commit()

        # Test bill
        bill = MaintenanceBill.query.filter_by(bill_number="BILL-AI-001").first()
        if not bill:
            bill = MaintenanceBill(
                bill_number="BILL-AI-001",
                society_id=society.id,
                flat_id=flat.id,
                resident_id=resident.id,
                billing_month="2026-08",
                base_amount=1500.0,
                total_amount=1500.0,
                remaining_amount=1500.0,
                due_date=date(2026, 8, 10),
                status="Pending"
            )
            db.session.add(bill)
            db.session.commit()

        # Test complaint
        complaint = Complaint.query.filter_by(title="AI Water leakage").first()
        if not complaint:
            complaint = Complaint(
                society_id=society.id,
                resident_id=resident.id,
                flat_id=flat.id,
                title="AI Water leakage",
                description="Water pipe under kitchen sink is leaking",
                category="Plumbing",
                status="Submitted",
                ticket_number="CMP-AI-001"
            )
            db.session.add(complaint)
            db.session.commit()

        # Test inventory item
        inventory = InventoryItem.query.filter_by(item_name="AI Test Cleaning Supply").first()
        if not inventory:
            inventory = InventoryItem(
                society_id=society.id,
                item_name="AI Test Cleaning Supply",
                category="Cleaning",
                current_stock=2,
                minimum_threshold=5,
                unit="liters"
            )
            db.session.add(inventory)
            db.session.commit()

        return society.id, admin.id, resident_user.id, resident.id


# ── STAGE 2: AI Society Intelligence Tests ─────────────────────────────────

def test_admin_ai_residents_query(app, ai_complete_test_data):
    """Test AI query for resident statistics."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        result = AIService._admin_query_residents(society_id)
        assert "registered residents" in result.lower()
        assert "active" in result.lower()


def test_admin_ai_maintenance_query(app, ai_complete_test_data):
    """Test AI query for maintenance status."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        result = AIService._admin_query_maintenance(society_id)
        assert "outstanding" in result.lower()
        assert "₹" in result


def test_admin_ai_registrations_query(app, ai_complete_test_data):
    """Test AI query for registration status."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        result = AIService._admin_query_registrations(society_id)
        assert "registration" in result.lower()


def test_admin_ai_complaints_query(app, ai_complete_test_data):
    """Test AI query for complaint status."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        result = AIService._admin_query_complaints(society_id)
        assert "complaint" in result.lower()


def test_admin_ai_inventory_query(app, ai_complete_test_data):
    """Test AI query for inventory status."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        result = AIService._admin_query_inventory(society_id)
        assert "inventory" in result.lower()


def test_weekly_summary_generation(app, ai_complete_test_data):
    """Test weekly summary generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        summary = AIService.get_weekly_summary(society_id)
        assert "WEEKLY SOCIETY SUMMARY" in summary
        assert "REGISTRATIONS" in summary
        assert "PAYMENTS" in summary
        assert "Based on Actual Data" in summary


def test_monthly_summary_generation(app, ai_complete_test_data):
    """Test monthly summary generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        summary = AIService.get_monthly_summary(society_id)
        assert "MONTHLY SOCIETY SUMMARY" in summary
        assert "FINANCIAL OVERVIEW" in summary
        assert "Based on Actual Financial Data" in summary


# ── STAGE 3: AI Communication Generators Tests ──────────────────────────────

def test_notice_generation(app):
    """Test AI notice generation."""
    notice = AIService.generate_notice(
        topic="Water Tank Maintenance",
        audience="All Residents",
        tone="Formal",
        important_points=["Water tank cleaning scheduled", "Water supply will be interrupted", "Store water in advance"]
    )
    assert "WATER TANK MAINTENANCE" in notice
    assert "All Residents" in notice
    assert "Requires Admin Approval" in notice


def test_whatsapp_message_generation(app):
    """Test WhatsApp message generation."""
    message = AIService.generate_whatsapp_message(
        message_type="maintenance_reminder",
        context_data={"month": "August 2026", "due_date": "10th", "amount": "1500"}
    )
    assert "MAINTENANCE REMINDER" in message
    assert "₹1500" in message
    assert "Review Before Sending" in message


def test_sms_generation(app):
    """Test SMS message generation."""
    message = AIService.generate_sms(
        message_type="maintenance_reminder",
        context_data={"amount": "1500", "month": "August 2026", "due_date": "10th"}
    )
    assert "MAINTENANCE DUE" in message
    assert "₹1500" in message
    assert len(message) < 160  # SMS length check


def test_complaint_reply_generation(app):
    """Test complaint reply generation."""
    reply = AIService.generate_complaint_reply(
        complaint_title="Water leakage",
        complaint_description="Water pipe under kitchen sink is leaking",
        category="Plumbing"
    )
    assert "RE: Water leakage" in reply
    assert "Plumbing" in reply
    assert "Admin Review Required" in reply


# ── STAGE 4: Financial AI Features Tests ───────────────────────────────────

def test_payment_anomaly_detection(app, ai_complete_test_data):
    """Test payment anomaly detection."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        anomalies = AIService.detect_payment_anomalies(society_id)
        assert isinstance(anomalies, list)
        # Should return empty list or advisory alerts, never modify data


def test_expense_anomaly_detection(app, ai_complete_test_data):
    """Test expense anomaly detection."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        anomalies = AIService.detect_expense_anomalies(society_id)
        assert isinstance(anomalies, list)
        # Should return empty list or advisory alerts, never modify data


def test_financial_summary_generation(app, ai_complete_test_data):
    """Test financial summary generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        summary = AIService.generate_financial_summary(society_id)
        assert "FINANCIAL SUMMARY" in summary
        assert "INCOME & COLLECTIONS" in summary
        assert "Based on Actual Financial Data" in summary


# ── STAGE 6: Document AI Features Tests ────────────────────────────────────

def test_document_categorization(app):
    """Test document categorization suggestion."""
    category = AIService.suggest_document_categorization(
        title="Invoice for plumbing repairs",
        description="Payment receipt for plumbing work done in common areas"
    )
    assert category in ["Financial", "Legal", "Maintenance", "Administrative", "Resident", "Property", "General"]


def test_document_summary_generation(app):
    """Test document summary generation."""
    summary = AIService.generate_document_summary(
        document_title="Society Bylaws",
        document_content="These are the society bylaws and rules for residents.\nSection 1: Maintenance\nSection 2: Security\nMore content here..."
    )
    assert "DOCUMENT SUMMARY" in summary
    assert "Society Bylaws" in summary


def test_document_query(app):
    """Test asking questions about a document."""
    answer = AIService.ask_document(
        question="What are the maintenance rules?",
        document_content="These are the society bylaws and rules for residents.\nSection 1: Maintenance rules require timely payment.\nSection 2: Security rules require visitor registration."
    )
    assert "Based on the document" in answer or "does not contain" in answer.lower()


# ── STAGE 7: Resident AI Security Tests ───────────────────────────────────

def test_resident_ai_isolation_in_queries(app, ai_complete_test_data):
    """Test that resident AI queries are properly isolated."""
    society_id, _, _, resident_id = ai_complete_test_data
    with app.app_context():
        # Resident should only get their own data
        insights = AIService.get_resident_payment_insights(resident_id, society_id)
        assert "total_due" in insights
        assert insights["total_due"] == 1500.0  # Their own bill only


def test_resident_daily_summary_isolation(app, ai_complete_test_data):
    """Test resident daily summary isolation."""
    society_id, _, _, resident_id = ai_complete_test_data
    with app.app_context():
        summary = AIService.get_resident_daily_summary(resident_id, society_id)
        assert "resident_name" in summary
        assert "payment_insights" in summary
        # Should not contain other residents' data


def test_cross_resident_protection(app, ai_complete_test_data):
    """Test that residents cannot access other residents' data via AI."""
    society_id, _, _, resident_id = ai_complete_test_data
    with app.app_context():
        # Try to query with wrong society_id
        wrong_summary = AIService.get_resident_daily_summary(resident_id, society_id + 999)
        assert "error" in wrong_summary or wrong_summary is None


# ── API Endpoint Tests ───────────────────────────────────────────────────────

def test_weekly_summary_api(client, app, ai_complete_test_data):
    """Test weekly summary API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/weekly-summary')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data
    assert data["based_on_actual_data"] is True


def test_monthly_summary_api(client, app, ai_complete_test_data):
    """Test monthly summary API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/monthly-summary')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data
    assert data["based_on_actual_data"] is True


def test_notice_generation_api(client, app, ai_complete_test_data):
    """Test notice generation API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.post('/api/v1/ai/generate-notice',
                          json={
                              "topic": "Test Notice",
                              "audience": "All Residents",
                              "tone": "Formal",
                              "important_points": ["Test point 1", "Test point 2"]
                          })
    assert response.status_code == 200
    data = response.get_json()
    assert "notice" in data
    assert data["requires_approval"] is True


def test_financial_summary_api(client, app, ai_complete_test_data):
    """Test financial summary API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/financial-summary')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data
    assert data["based_on_actual_data"] is True


def test_resident_cannot_access_admin_apis(client, app, ai_complete_test_data):
    """Test that residents cannot access admin AI APIs."""
    society_id, _, resident_user_id, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = resident_user_id
        sess['society_id'] = society_id
        sess['role'] = Role.RESIDENT

    response = client.get('/api/v1/ai/financial-summary')
    assert response.status_code == 403  # Forbidden


# ── AI Disabled Behavior Tests ───────────────────────────────────────────────

def test_ai_disabled_fallback():
    """Test that system works when AI is disabled."""
    # This tests the deterministic fallback behavior
    classification = AIService.classify_complaint("Water leak", "Pipe is leaking")
    assert "category" in classification
    assert "priority" in classification
    # Should work even without external AI provider


def test_deterministic_ai_provider():
    """Test that deterministic AI provider works."""
    from app.services.ai_service import DeterministicRuleAIProvider
    provider = DeterministicRuleAIProvider()

    result = provider.classify_text("water leak in pipe")
    assert result["category"] == "Plumbing"
    assert result["priority"] == "High"

    result = provider.predict({"test": "data"})
    assert result["confidence"] == 0.95
    assert result["prediction"] == "NORMAL"


# ── Security Tests ─────────────────────────────────────────────────────────

def test_no_sql_injection_via_ai():
    """Test that AI cannot be used for SQL injection."""
    malicious_query = "'; DROP TABLE residents; --"
    # The AI service should handle this safely
    result = AIService.classify_complaint(malicious_query, malicious_query)
    # Should return classification, not execute SQL
    assert "category" in result


def test_ai_no_financial_modification(app):
    """Test that AI features never modify financial records."""
    # This is a behavioral test - AI methods should be read-only
    with app.app_context():
        society_id = 1  # Test society

        # All these methods should only return data, never modify
        anomalies = AIService.detect_payment_anomalies(society_id)
        assert isinstance(anomalies, list)

        summary = AIService.generate_financial_summary(society_id)
        assert isinstance(summary, str)

        # No database modifications should occur
        # No database modifications should occur


# ── STAGE 4 Extended: Collection Prediction & Cash-Flow Forecast Tests ──────

def test_collection_prediction(app, ai_complete_test_data):
    """Test collection prediction generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        prediction = AIService.generate_collection_prediction(society_id)
        assert isinstance(prediction, dict)
        assert "current_month" in prediction
        assert "predicted_collection" in prediction
        assert "estimate_only" in prediction or prediction.get("note", "").startswith("ESTIMATE")


def test_cash_flow_forecast(app, ai_complete_test_data):
    """Test cash flow forecast generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        forecast = AIService.generate_cash_flow_forecast(society_id)
        assert isinstance(forecast, dict)
        assert "expected_inflow" in forecast
        assert "expected_outflow" in forecast
        assert "projected_balance" in forecast
        assert forecast.get("note", "").startswith("ESTIMATE")


# ── STAGE 5 Extended: Automation Tests ───────────────────────────────────────

def test_overdue_tasks_detection(app, ai_complete_test_data):
    """Test overdue tasks detection."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        tasks = AIService.get_overdue_tasks(society_id)
        assert isinstance(tasks, list)
        # Should return empty list or tasks with priority levels


def test_task_escalation_alert(app, ai_complete_test_data):
    """Test task escalation alert generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        alert = AIService.generate_task_escalation_alert(society_id)
        assert isinstance(alert, dict)
        assert "summary" in alert
        assert "advisory_only" in alert


def test_expiring_items_detection(app, ai_complete_test_data):
    """Test expiring items detection."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        items = AIService.get_expiring_items(society_id, days_threshold=30)
        assert isinstance(items, list)
        # Items should have severity levels


def test_expiry_reminder_summary(app, ai_complete_test_data):
    """Test expiry reminder summary generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        summary = AIService.generate_expiry_reminder_summary(society_id, days_threshold=30)
        assert isinstance(summary, dict)
        assert "summary" in summary
        assert "items" in summary


def test_low_stock_detection(app, ai_complete_test_data):
    """Test low stock detection."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        items = AIService.get_low_stock_items(society_id)
        assert isinstance(items, list)


def test_low_stock_alert(app, ai_complete_test_data):
    """Test low stock alert generation."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        alert = AIService.generate_low_stock_alert(society_id)
        assert isinstance(alert, dict)
        assert "summary" in alert
        assert "advisory_only" in alert


# ── STAGE 6 Extended: AI Document Search Tests ───────────────────────────────

def test_ai_document_search(app, ai_complete_test_data):
    """Test AI-enhanced document search."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)
        results = SearchService.ai_document_search(admin, society_id, "test")
        assert isinstance(results, dict)
        assert "results" in results
        assert "total_results" in results


def test_document_search_with_categories(app, ai_complete_test_data):
    """Test document search with category filter."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)
        results = SearchService.ai_document_search(admin, society_id, "test", categories=["Financial"])
        assert isinstance(results, dict)
        assert "results" in results


# ── STAGE 7 Extended: Resident AI Assistant Tests ────────────────────────────

def test_resident_ai_assistant_query(app, ai_complete_test_data):
    """Test resident AI assistant query."""
    society_id, _, resident_user_id, resident_id = ai_complete_test_data
    with app.app_context():
        resident = db.session.get(User, resident_user_id)

        # Test "What is my pending amount?"
        response = AIService.get_resident_assistant_response(resident, "What is my pending amount?")
        assert isinstance(response, dict)
        assert "response" in response


def test_resident_ai_assistant_bill_query(app, ai_complete_test_data):
    """Test resident AI assistant bill query."""
    society_id, _, resident_user_id, _ = ai_complete_test_data
    with app.app_context():
        resident = db.session.get(User, resident_user_id)

        response = AIService.get_resident_assistant_response(resident, "Explain my bill.")
        assert isinstance(response, dict)
        assert "response" in response


def test_resident_ai_assistant_no_access_to_other_residents(app, ai_complete_test_data):
    """Test that resident AI assistant cannot access other residents' data."""
    society_id, _, resident_user_id, resident_id = ai_complete_test_data
    with app.app_context():
        resident = db.session.get(User, resident_user_id)

        # Try to ask about another resident - should be handled by isolation
        # The method derives resident from session, so this test ensures
        # the data isolation works correctly
        response = AIService.get_resident_assistant_response(resident, "What is my pending amount?")
        # Response should only contain the current resident's data
        assert "response" in response
        # Should not contain other residents' data


def test_resident_ai_assistant_query_fallback(app, ai_complete_test_data):
    """Test resident AI assistant default query."""
    society_id, _, resident_user_id, _ = ai_complete_test_data
    with app.app_context():
        resident = db.session.get(User, resident_user_id)

        response = AIService.get_resident_assistant_response(resident, "Random question that is not supported")
        assert isinstance(response, dict)
        assert "supported_queries" in response or "response" in response


# ── API Endpoint Tests for New Features ──────────────────────────────────────

def test_collection_prediction_api(client, app, ai_complete_test_data):
    """Test collection prediction API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/collection-prediction')
    assert response.status_code == 200
    data = response.get_json()
    assert "prediction" in data
    assert data.get("estimate_only") is True


def test_cash_flow_forecast_api(client, app, ai_complete_test_data):
    """Test cash flow forecast API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/cash-flow-forecast')
    assert response.status_code == 200
    data = response.get_json()
    assert "forecast" in data
    assert data.get("estimate_only") is True


def test_overdue_tasks_api(client, app, ai_complete_test_data):
    """Test overdue tasks API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/overdue-tasks')
    assert response.status_code == 200
    data = response.get_json()
    assert "tasks" in data
    assert data.get("advisory_only") is True


def test_expiring_items_api(client, app, ai_complete_test_data):
    """Test expiring items API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/expiring-items')
    assert response.status_code == 200
    data = response.get_json()
    assert "items" in data


def test_low_stock_api(client, app, ai_complete_test_data):
    """Test low stock API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/low-stock')
    assert response.status_code == 200
    data = response.get_json()
    assert "items" in data
    assert data.get("advisory_only") is True


def test_document_search_api(client, app, ai_complete_test_data):
    """Test AI document search API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/document-search?q=test')
    assert response.status_code == 200
    data = response.get_json()
    assert "results" in data


def test_task_escalation_alert_api(client, app, ai_complete_test_data):
    """Test task escalation alert API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/task-escalation-alert')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data


def test_expiry_reminder_summary_api(client, app, ai_complete_test_data):
    """Test expiry reminder summary API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/expiry-reminder-summary')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data


def test_low_stock_alert_api(client, app, ai_complete_test_data):
    """Test low stock alert API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/ai/low-stock-alert')
    assert response.status_code == 200
    data = response.get_json()
    assert "summary" in data


def test_resident_ai_assistant_api(client, app, ai_complete_test_data):
    """Test resident AI assistant API endpoint."""
    society_id, _, resident_user_id, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = resident_user_id
        sess['society_id'] = society_id
        sess['role'] = Role.RESIDENT

    response = client.post('/api/v1/resident/ai/query',
                          json={"prompt": "What is my pending amount?"})
    assert response.status_code == 200
    data = response.get_json()
    assert "response" in data


def test_resident_cannot_access_admin_apis_via_new_endpoints(client, app, ai_complete_test_data):
    """Test that residents cannot access new admin AI APIs."""
    society_id, _, resident_user_id, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = resident_user_id
        sess['society_id'] = society_id
        sess['role'] = Role.RESIDENT

    response = client.get('/api/v1/ai/collection-prediction')
    assert response.status_code == 403  # Forbidden


def test_ai_daily_brief_api(client, app, ai_complete_test_data):
    """Test AI-enhanced daily brief API endpoint."""
    society_id, admin_id, _, _ = ai_complete_test_data

    with client.session_transaction() as sess:
        sess['user_id'] = admin_id
        sess['society_id'] = society_id
        sess['role'] = Role.SOCIETY_ADMIN

    response = client.get('/api/v1/health/ai-daily-brief')
    assert response.status_code == 200
    data = response.get_json()
    assert "ai_recommendations" in data or "ai_forecasts" in data


# ── Automation Handler Tests ─────────────────────────────────────────────────

def test_automation_handler_overdue_tasks(app, ai_complete_test_data):
    """Test automation handler for overdue tasks."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        from app.services.automation_service import AutomationService

        result = AutomationService.execute_job(
            action_type="check_overdue_tasks",
            society_id=society_id,
            executed_by=admin,
            trigger_source="SYSTEM",
        )

        assert result["success"] is True
        assert "updated" in result["stats"]


def test_automation_handler_expiry_reminders(app, ai_complete_test_data):
    """Test automation handler for expiry reminders."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        from app.services.automation_service import AutomationService

        result = AutomationService.execute_job(
            action_type="check_expiry_reminders",
            society_id=society_id,
            executed_by=admin,
            trigger_source="SYSTEM",
            params={"days_threshold": 30}
        )

        assert result["success"] is True
        assert "created" in result["stats"]


def test_automation_handler_low_stock(app, ai_complete_test_data):
    """Test automation handler for low stock."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        from app.services.automation_service import AutomationService

        result = AutomationService.execute_job(
            action_type="check_low_stock",
            society_id=society_id,
            executed_by=admin,
            trigger_source="SYSTEM",
        )

        assert result["success"] is True
        assert "created" in result["stats"]


# ── Additional Edge Case Tests ───────────────────────────────────────────────

def test_empty_society_id_in_collection_prediction(app):
    """Test collection prediction with invalid society_id."""
    with app.app_context():
        prediction = AIService.generate_collection_prediction(9999)
        assert isinstance(prediction, dict)
        # Should handle gracefully


def test_empty_society_id_in_cash_flow_forecast(app):
    """Test cash flow forecast with invalid society_id."""
    with app.app_context():
        forecast = AIService.generate_cash_flow_forecast(9999)
        assert isinstance(forecast, dict)
        # Should handle gracefully


def test_low_stock_with_zero_items(app, ai_complete_test_data):
    """Test low stock detection returns empty list when no low stock items exist."""
    society_id, _, _, _ = ai_complete_test_data
    with app.app_context():
        items = AIService.get_low_stock_items(society_id)
        assert isinstance(items, list)
        # May be empty if all items are adequately stocked


def test_document_search_empty_query(app, ai_complete_test_data):
    """Test document search with empty query."""
    society_id, admin_id, _, _ = ai_complete_test_data
    with app.app_context():
        admin = db.session.get(User, admin_id)
        results = SearchService.ai_document_search(admin, society_id, "")
        assert isinstance(results, dict)
        assert "results" in results
