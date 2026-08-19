import pytest
from datetime import datetime, timedelta
from app.models import (
    db,
    AutomationRule,
    AutomationExecution,
    AutomationFailure,
    Society,
    User,
    Role,
)
from app.services.automation_service import AutomationService
from app.utils import utcnow


@pytest.fixture
def auth_admin(app):
    with app.app_context():
        society = Society(
            name="Automation Test Society",
            registration_number="AUT-SOC-001",
            address="123 Automation Way",
            city="Tech City",
            state="Gujarat",
            pincode="380001",
            email="admin@autosoc.com",
            phone="9876543210",
        )
        db.session.add(society)
        db.session.commit()

        user = User(
            username="autoadmin",
            full_name="Automation Admin",
            email="admin@autosoc.com",
            mobile="9876543210",
            role=Role.SOCIETY_ADMIN,
            society_id=society.id,
            account_status="ACTIVE",
        )
        user.set_password("Admin@123")
        db.session.add(user)
        db.session.commit()
        return user.id, society.id


def test_automation_job_execution_success(app, auth_admin):
    user_id, society_id = auth_admin
    with app.app_context():
        admin = db.session.get(User, user_id)

        # Register a test dummy action
        def dummy_job(society_id, params, executed_by):
            return {
                "records_scanned": 10,
                "records_created": 3,
                "records_updated": 2,
                "records_skipped": 5,
            }

        AutomationService.register_job("TEST_DUMMY_ACTION", dummy_job)

        res = AutomationService.execute_job(
            action_type="TEST_DUMMY_ACTION",
            society_id=society_id,
            executed_by=admin,
            trigger_source="TEST",
        )

        assert res["success"] is True
        assert res["status"] == "COMPLETED"
        assert res["stats"]["records_scanned"] == 10
        assert res["stats"]["records_created"] == 3

        # Verify DB execution record
        exec_record = AutomationExecution.query.filter_by(execution_id=res["execution_id"]).first()
        assert exec_record is not None
        assert exec_record.status == "COMPLETED"
        assert exec_record.records_created == 3
        assert exec_record.duration_ms >= 0


def test_automation_concurrency_lock(app, auth_admin):
    user_id, society_id = auth_admin
    with app.app_context():
        admin = db.session.get(User, user_id)

        # Create a synthetic RUNNING execution
        active_exec = AutomationExecution(
            society_id=society_id,
            automation_name="LOCKED_ACTION",
            execution_id="exec_locked_001",
            status="RUNNING",
            start_time=utcnow(),
        )
        db.session.add(active_exec)
        db.session.commit()

        # Attempt to run the same action concurrently
        res = AutomationService.execute_job(
            action_type="LOCKED_ACTION",
            society_id=society_id,
            executed_by=admin,
        )

        assert res["success"] is False
        assert res["status"] == "LOCKED"
        assert "already running" in res["message"]


def test_automation_failure_handling(app, auth_admin):
    user_id, society_id = auth_admin
    with app.app_context():
        admin = db.session.get(User, user_id)

        def failing_job(society_id, params, executed_by):
            raise RuntimeError("Database connection timed out during billing job")

        AutomationService.register_job("FAILING_ACTION", failing_job)

        res = AutomationService.execute_job(
            action_type="FAILING_ACTION",
            society_id=society_id,
            executed_by=admin,
        )

        assert res["success"] is False
        assert res["status"] == "FAILED"
        assert "Database connection timed out" in res["error"]

        # Verify failure record in DB
        failure_log = AutomationFailure.query.filter_by(society_id=society_id).first()
        assert failure_log is not None
        assert "Database connection timed out" in failure_log.error_message
