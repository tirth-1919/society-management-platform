"""
Extended automation tests for Stage 5 features.
Tests task escalation, expiry reminders, and low stock automation.
"""
import pytest
from datetime import timedelta
from app.models import (
    db,
    Society,
    Building,
    Flat,
    User,
    Resident,
    Role,
    InventoryItem,
    PreApprovedPass,
    AutomationExecution,
)
from app.services.automation_service import AutomationService
from app.utils import utcnow


@pytest.fixture
def automation_extended_data(app):
    """Setup test data for extended automation features."""
    with app.app_context():
        society = Society(
            name="Automation Extended Test",
            registration_number="AUTO-EXT-001",
            address="456 Automation Road",
            city="Test City",
            state="Gujarat",
            pincode="360001",
            email="auto@test.com",
            phone="9876543222",
        )
        db.session.add(society)
        db.session.commit()

        admin = User(
            username="auto_admin",
            full_name="Automation Admin",
            email="autoadmin@test.com",
            mobile="9876543222",
            role=Role.SOCIETY_ADMIN,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True
        )
        admin.set_password("Admin@123")
        db.session.add(admin)
        db.session.commit()

        # Building and Flat for visitor passes
        building = Building(society_id=society.id, name="Wing AUTO")
        db.session.add(building)
        db.session.commit()

        flat = Flat(society_id=society.id, building_id=building.id, flat_number="AUTO-101")
        db.session.add(flat)
        db.session.commit()

        resident_user = User(
            username="auto_resident",
            full_name="Automation Resident",
            email="autoresident@test.com",
            mobile="9876543223",
            role=Role.RESIDENT,
            society_id=society.id,
            account_status="ACTIVE",
            is_active=True,
        )
        resident_user.set_password("Resident@123")
        db.session.add(resident_user)
        db.session.commit()

        resident = Resident(
            society_id=society.id,
            flat_id=flat.id,
            user_id=resident_user.id,
            full_name="Automation Resident",
            mobile="9876543223",
            email="autoresident@test.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
        )
        db.session.add(resident)
        db.session.commit()

        # Low stock inventory item
        low_stock_item = InventoryItem(
            society_id=society.id,
            item_name="Test Supply Low",
            category="Cleaning",
            current_stock=2,
            minimum_threshold=5,
            unit="liters"
        )
        db.session.add(low_stock_item)
        db.session.commit()

        # Normal stock item
        normal_stock_item = InventoryItem(
            society_id=society.id,
            item_name="Test Supply Normal",
            category="Cleaning",
            current_stock=10,
            minimum_threshold=5,
            unit="liters"
        )
        db.session.add(normal_stock_item)
        db.session.commit()

        # Expired visitor pass
        expired_pass = PreApprovedPass(
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            visitor_name="Expired Visitor",
            mobile="9876543233",
            expected_date=utcnow().date() - timedelta(days=5),
            is_used=False,
            pass_code="EXP123",
            purpose="Guest"
        )
        db.session.add(expired_pass)
        db.session.commit()

        # Future visitor pass
        future_pass = PreApprovedPass(
            society_id=society.id,
            flat_id=flat.id,
            resident_id=resident.id,
            visitor_name="Future Visitor",
            mobile="9876543244",
            expected_date=utcnow().date() + timedelta(days=5),
            is_used=False,
            pass_code="FUT456",
            purpose="Guest"
        )
        db.session.add(future_pass)
        db.session.commit()

        return society.id, admin.id


def test_low_stock_detection(app, automation_extended_data):
    """Test low stock detection automation."""
    society_id, _ = automation_extended_data
    with app.app_context():
        from app.services.society_health_service import SocietyHealthService

        low_stock_count = SocietyHealthService.get_admin_daily_brief(society_id).get("low_inventory_count", 0)
        assert low_stock_count >= 1  # At least our low stock item


def test_expiry_reminder_automation(app, automation_extended_data):
    """Test visitor pass expiry automation."""
    society_id, admin_id = automation_extended_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        # Run the expiry automation
        result = AutomationService.execute_job(
            action_type="EXPIRE_VISITOR_PASSES",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )

        assert result["success"] is True
        assert result["status"] in ["COMPLETED", "WARNING"]

        # Check that expired pass was marked as used
        from app.models import PreApprovedPass
        expired_pass = PreApprovedPass.query.filter_by(
            society_id=society_id,
            visitor_name="Expired Visitor"
        ).first()

        assert expired_pass.is_used is True

        # Future pass should remain unused
        future_pass = PreApprovedPass.query.filter_by(
            society_id=society_id,
            visitor_name="Future Visitor"
        ).first()
        assert future_pass.is_used is False


def test_task_escalation_automation(app, automation_extended_data):
    """Test defaulter task escalation automation."""
    society_id, admin_id = automation_extended_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        # Run the defaulter recovery automation
        result = AutomationService.execute_job(
            action_type="PROCESS_DEFAULTER_RECOVERY",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )

        assert result["success"] is True
        assert result["status"] in ["COMPLETED", "WARNING"]


def test_automation_concurrency_protection(app, automation_extended_data):
    """Test that automation jobs have concurrency protection."""
    society_id, admin_id = automation_extended_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        # First execution
        result1 = AutomationService.execute_job(
            action_type="EXPIRE_VISITOR_PASSES",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )
        assert result1["success"] is True

        # Immediate second execution should be locked
        result2 = AutomationService.execute_job(
            action_type="EXPIRE_VISITOR_PASSES",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )
        assert result2["success"] is False
        assert result2["status"] == "LOCKED"


def test_automation_failure_logging(app, automation_extended_data):
    """Test that automation failures are properly logged."""
    society_id, admin_id = automation_extended_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        # Register a failing job
        def failing_job(society_id, params, executed_by):
            raise RuntimeError("Test automation failure")

        AutomationService.register_job("TEST_FAILING_JOB", failing_job)

        result = AutomationService.execute_job(
            action_type="TEST_FAILING_JOB",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )

        assert result["success"] is False
        assert result["status"] == "FAILED"

        # Check failure was logged
        from app.models import AutomationFailure
        failure = AutomationFailure.query.filter_by(society_id=society_id).first()
        assert failure is not None
        assert "Test automation failure" in failure.error_message


def test_inventory_stock_protection(app, automation_extended_data):
    """Test that inventory automation doesn't automatically modify quantities."""
    society_id, _ = automation_extended_data
    with app.app_context():
        from app.services.inventory_service import InventoryService

        low_stock_item = InventoryItem.query.filter_by(
            society_id=society_id,
            item_name="Test Supply Low"
        ).first()

        original_stock = low_stock_item.current_stock

        # Try to take out more than available (should fail)
        with pytest.raises(ValueError, match="Insufficient stock"):
            InventoryService.process_stock_transaction(
                item_id=low_stock_item.id,
                society_id=society_id,
                transaction_type="OUT",
                quantity=10,  # More than available (2)
                user_id=None
            )

        # Stock should remain unchanged
        low_stock_item = db.session.get(InventoryItem, low_stock_item.id)
        assert low_stock_item.current_stock == original_stock


def test_automation_audit_trail(app, automation_extended_data):
    """Test that automation creates proper audit trails."""
    society_id, admin_id = automation_extended_data
    with app.app_context():
        admin = db.session.get(User, admin_id)

        # Run an automation
        AutomationService.execute_job(
            action_type="EXPIRE_VISITOR_PASSES",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST"
        )

        # Check execution record
        execution = AutomationExecution.query.filter_by(
            society_id=society_id,
            automation_name="EXPIRE_VISITOR_PASSES"
        ).first()

        assert execution is not None
        assert execution.status in ["COMPLETED", "WARNING"]
        assert execution.executed_by_id == admin_id
        assert execution.trigger_source == "TEST"

        # Check audit log
        from app.models import AuditLog
        audit = AuditLog.query.filter_by(
            society_id=society_id,
            action="AUTOMATION_EXECUTION_SUCCESS"
        ).first()

        assert audit is not None
        assert audit.user_id == admin_id