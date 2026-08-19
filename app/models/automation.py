from app.models.tenant import db
from app.utils import utcnow
import json


class AutomationRule(db.Model):
    __tablename__ = "automation_rules"

    id = db.Column(db.Integer, primary_key=True)
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )
    name = db.Column(db.String(150), nullable=False, unique=True, index=True)
    description = db.Column(db.String(255), nullable=True)
    trigger_type = db.Column(
        db.String(50), nullable=False, default="SCHEDULED"
    )  # SCHEDULED, EVENT_TRIGGERED, MANUAL
    schedule_cron = db.Column(db.String(50), nullable=True)
    conditions_json = db.Column(db.Text, nullable=True)
    action_type = db.Column(db.String(100), nullable=False)
    action_params_json = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    cooldown_seconds = db.Column(db.Integer, default=60)
    retry_limit = db.Column(db.Integer, default=3)
    last_run_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    executions = db.relationship(
        "AutomationExecution", backref="rule", lazy=True, cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)

    def get_conditions(self):
        try:
            return json.loads(self.conditions_json or "{}")
        except Exception:
            return {}

    def get_action_params(self):
        try:
            return json.loads(self.action_params_json or "{}")
        except Exception:
            return {}


class AutomationExecution(db.Model):
    __tablename__ = "automation_executions"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(
        db.Integer, db.ForeignKey("automation_rules.id"), nullable=True, index=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )
    automation_name = db.Column(db.String(150), nullable=False, index=True)
    execution_id = db.Column(db.String(100), unique=True, nullable=False, index=True)

    # State: PENDING, RUNNING, COMPLETED, FAILED, WARNING, CANCELLED, RETRYING
    status = db.Column(db.String(30), nullable=False, default="PENDING", index=True)

    start_time = db.Column(db.DateTime, default=utcnow)
    end_time = db.Column(db.DateTime, nullable=True)
    duration_ms = db.Column(db.Integer, default=0)

    records_scanned = db.Column(db.Integer, default=0)
    records_created = db.Column(db.Integer, default=0)
    records_updated = db.Column(db.Integer, default=0)
    records_skipped = db.Column(db.Integer, default=0)

    warnings_json = db.Column(db.Text, nullable=True)
    errors_json = db.Column(db.Text, nullable=True)
    trigger_source = db.Column(
        db.String(50), default="SYSTEM"
    )  # SYSTEM, CRON, ADMIN_UI, API, WEBHOOK
    executed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)

    executed_by = db.relationship("User", foreign_keys=[executed_by_id], lazy=True)
    failures = db.relationship(
        "AutomationFailure", backref="execution", lazy=True, cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)


class AutomationFailure(db.Model):
    __tablename__ = "automation_failures"

    id = db.Column(db.Integer, primary_key=True)
    execution_id = db.Column(
        db.Integer, db.ForeignKey("automation_executions.id"), nullable=False, index=True
    )
    rule_id = db.Column(
        db.Integer, db.ForeignKey("automation_rules.id"), nullable=True, index=True
    )
    society_id = db.Column(
        db.Integer, db.ForeignKey("societies.id"), nullable=True, index=True
    )
    error_message = db.Column(db.Text, nullable=False)
    stack_trace = db.Column(db.Text, nullable=True)
    retry_count = db.Column(db.Integer, default=0)
    is_resolved = db.Column(db.Boolean, default=False, index=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    resolved_by = db.relationship("User", foreign_keys=[resolved_by_id], lazy=True)

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
