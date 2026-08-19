import json
import time
import uuid
import traceback
from datetime import timedelta
from app.models import (
    db,
    AutomationRule,
    AutomationExecution,
    AutomationFailure,
    AuditLog,
)
from app.utils import utcnow


class AutomationService:
    # Supported automation job registry
    JOB_REGISTRY = {}

    @classmethod
    def register_job(cls, action_type, handler):
        """Registers a Python function handler for an action type."""
        cls.JOB_REGISTRY[action_type] = handler

    @staticmethod
    def execute_job(
        action_type,
        society_id=None,
        executed_by=None,
        trigger_source="SYSTEM",
        rule_id=None,
        params=None,
    ):
        """
        Executes an automation job with atomic state transitions, concurrency locking,
        metric recording, failure tracking, and audit logging.
        """
        params = params or {}
        execution_id = f"exec_{uuid.uuid4().hex[:12]}"
        now = utcnow()

        # Check concurrency lock: is there an active RUNNING execution for this job in the last 10 minutes,
        # or a COMPLETED execution within cooldown window?
        cooldown_sec = 60
        if rule_id:
            rule = db.session.get(AutomationRule, rule_id)
            if rule and rule.cooldown_seconds is not None:
                cooldown_sec = rule.cooldown_seconds

        existing_running = AutomationExecution.query.filter(
            AutomationExecution.automation_name == action_type,
            (
                (AutomationExecution.status == "RUNNING") & (AutomationExecution.start_time >= now - timedelta(minutes=10))
            ) | (
                (AutomationExecution.status == "COMPLETED") & (AutomationExecution.start_time >= now - timedelta(seconds=cooldown_sec))
            )
        )
        if society_id:
            existing_running = existing_running.filter(
                (AutomationExecution.society_id == society_id) | (AutomationExecution.society_id.is_(None))
            )
        if existing_running.first():
            return {
                "success": False,
                "status": "LOCKED",
                "message": f"Job {action_type} is already running or in cooldown. Duplicate concurrent execution prevented.",
                "execution_id": None,
            }

        # Create execution record
        execution = AutomationExecution(
            rule_id=rule_id,
            society_id=society_id,
            automation_name=action_type,
            execution_id=execution_id,
            status="RUNNING",
            start_time=now,
            trigger_source=trigger_source,
            executed_by_id=executed_by.id if executed_by else None,
        )
        db.session.add(execution)
        db.session.commit()

        start_tick = time.perf_counter()
        warnings = []
        errors = []
        result_stats = {
            "records_scanned": 0,
            "records_created": 0,
            "records_updated": 0,
            "records_skipped": 0,
            "scanned": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
        }

        try:
            handler = AutomationService._get_handler(action_type)
            if not handler:
                raise ValueError(f"Unknown automation action type: {action_type}")

            job_output = handler(society_id=society_id, params=params, executed_by=executed_by)
            if isinstance(job_output, dict):
                scanned = job_output.get("scanned", job_output.get("records_scanned", 0))
                created = job_output.get("created", job_output.get("records_created", 0))
                updated = job_output.get("updated", job_output.get("records_updated", 0))
                skipped = job_output.get("skipped", job_output.get("records_skipped", 0))
                result_stats["records_scanned"] = scanned
                result_stats["records_created"] = created
                result_stats["records_updated"] = updated
                result_stats["records_skipped"] = skipped
                result_stats["scanned"] = scanned
                result_stats["created"] = created
                result_stats["updated"] = updated
                result_stats["skipped"] = skipped
                if "warnings" in job_output and job_output["warnings"]:
                    warnings = job_output["warnings"] if isinstance(job_output["warnings"], list) else [job_output["warnings"]]
                if "errors" in job_output and job_output["errors"]:
                    errors = job_output["errors"] if isinstance(job_output["errors"], list) else [job_output["errors"]]

            duration_ms = int((time.perf_counter() - start_tick) * 1000)
            status = "WARNING" if warnings else "COMPLETED"

            execution.status = status
            execution.end_time = utcnow()
            execution.duration_ms = duration_ms
            execution.records_scanned = result_stats["records_scanned"]
            execution.records_created = result_stats["records_created"]
            execution.records_updated = result_stats["records_updated"]
            execution.records_skipped = result_stats["records_skipped"]
            execution.warnings_json = json.dumps(warnings) if warnings else None
            execution.errors_json = json.dumps(errors) if errors else None

            # Update rule if linked
            if rule_id:
                rule = db.session.get(AutomationRule, rule_id)
                if rule:
                    rule.last_run_at = utcnow()

            # Audit success
            audit = AuditLog(
                user_id=executed_by.id if executed_by else None,
                action="AUTOMATION_EXECUTION_SUCCESS",
                details=f"Automation '{action_type}' finished with status {status}. Created: {execution.records_created}, Updated: {execution.records_updated}.",
            )
            db.session.add(audit)
            db.session.commit()

            return {
                "success": True,
                "status": status,
                "execution_id": execution_id,
                "duration_ms": duration_ms,
                "stats": result_stats,
                "warnings": warnings,
                "errors": errors,
            }

        except Exception as e:
            duration_ms = int((time.perf_counter() - start_tick) * 1000)
            err_msg = str(e)
            stack = traceback.format_exc()

            execution.status = "FAILED"
            execution.end_time = utcnow()
            execution.duration_ms = duration_ms
            execution.errors_json = json.dumps([err_msg])

            failure = AutomationFailure(
                execution_id=execution.id,
                rule_id=rule_id,
                society_id=society_id,
                error_message=err_msg,
                stack_trace=stack,
                retry_count=0,
                is_resolved=False,
            )
            db.session.add(failure)

            audit = AuditLog(
                user_id=executed_by.id if executed_by else None,
                action="AUTOMATION_EXECUTION_FAILURE",
                details=f"Automation '{action_type}' failed: {err_msg}",
            )
            db.session.add(audit)
            db.session.commit()

            return {
                "success": False,
                "status": "FAILED",
                "execution_id": execution_id,
                "error": err_msg,
                "duration_ms": duration_ms,
            }

    @staticmethod
    def _get_handler(action_type):
        """Resolves the function handler for an action type."""
        # Built-in handlers
        if action_type == "RECONCILE_PAYMENTS" or action_type == "reconcile_payments":
            from app.services.reconciliation_service import PaymentReconciliationService
            return lambda society_id, params, executed_by: PaymentReconciliationService.reconcile_all(
                society_id=society_id, executed_by=executed_by
            )

        if action_type == "GENERATE_MONTHLY_BILLS" or action_type == "generate_monthly_bills":
            from app.services.billing_service import BillingService
            return lambda society_id, params, executed_by: BillingService.generate_missing_bills_summary(
                society_id=society_id, month=params.get("month")
            )

        if action_type == "APPLY_LATE_FEES" or action_type == "apply_late_fees":
            from app.services.billing_service import BillingService
            return lambda society_id, params, executed_by: {
                "updated": len(BillingService.apply_due_late_fees(society_id=society_id)),
                "scanned": 100,
            }

        if action_type == "RUN_DAILY_HEALTH_CHECK" or action_type == "run_daily_health_check":
            from app.services.society_health_service import SocietyHealthService
            return lambda society_id, params, executed_by: SocietyHealthService.run_full_society_audit(
                society_id=society_id
            )

        if action_type == "SEND_DUE_REMINDERS" or action_type == "send_due_reminders":
            from app.services.notification_service import NotificationService
            return lambda society_id, params, executed_by: {
                "created": len(NotificationService.send_maintenance_reminders(society_id=society_id)),
                "scanned": 50,
            }

        if action_type == "EXPIRE_VISITOR_PASSES" or action_type == "expire_visitor_passes":
            from app.models import PreApprovedPass
            def _expire(society_id, params, executed_by):
                q = PreApprovedPass.query.filter(
                    PreApprovedPass.is_used.is_(False),
                    PreApprovedPass.expected_date < utcnow().date(),
                )
                if society_id:
                    q = q.filter(PreApprovedPass.society_id == society_id)
                passes = q.all()
                for p in passes:
                    p.is_used = True
                db.session.commit()
                return {"updated": len(passes), "scanned": len(passes)}
            return _expire

        if action_type == "PROCESS_DEFAULTER_RECOVERY" or action_type == "process_defaulter_recovery":
            from app.services.billing_service import BillingService
            from app.services.notification_service import NotificationService
            from app.services.payment_service import PaymentService
            from app.models import Resident, DefaulterFollowUp, DefaulterStateTransition, MaintenanceBill

            def _recovery(society_id, params, executed_by):
                defaulters = BillingService.get_defaulters_list(society_id=society_id)
                scanned = len(defaulters)
                created = 0
                updated = 0
                skipped = 0

                for d in defaulters:
                    res_id = d["resident_id"]
                    res = db.session.get(Resident, res_id)
                    if not res or not res.user:
                        skipped += 1
                        continue

                    user = res.user
                    risk = d["risk_level"]
                    stage = d["stage"]

                    # Get the primary bill for context
                    bill = MaintenanceBill.query.filter(
                        MaintenanceBill.resident_id == res_id,
                        MaintenanceBill.billing_month == d["pending_months"][0]
                    ).first() if d["pending_months"] else None

                    # State transition
                    transition = DefaulterStateTransition(
                        resident_id=res_id,
                        bill_id=bill.id if bill else None,
                        old_state=bill.status if bill else "UNKNOWN",
                        new_state=stage,
                        reason=f"Risk level: {risk}",
                        actor_id=executed_by.id if executed_by else None,
                        automation_id="process_defaulter_recovery"
                    )
                    db.session.add(transition)

                    # Cooldown check (24 hours)
                    cooldown = NotificationService.check_reminder_cooldown(
                        user.id, d["pending_months"][0], "OVERDUE_REMINDER", cooldown_hours=24
                    ) if d["pending_months"] else True

                    if not cooldown:
                        if risk == "LOW":
                            NotificationService.send_billing_notification(
                                user, d["pending_months"][0], "OVERDUE_REMINDER",
                                f"Friendly Reminder: Your maintenance bill for {d['pending_months'][0]} of ₹{d['total_outstanding']:,.0f} is overdue. Please settle to avoid late fees.",
                                cooldown_hours=24
                            )
                            updated += 1
                        elif risk in ["MEDIUM", "HIGH"]:
                            NotificationService.send_billing_notification(
                                user, d["pending_months"][0], "ESCALATION_NOTICE",
                                f"URGENT: Your account has overdue dues of ₹{d['total_outstanding']:,.0f} ({d['days_overdue']} days overdue). Please settle immediately or contact administration.",
                                cooldown_hours=24
                            )
                            updated += 1

                    if risk == "CRITICAL":
                        # Ensure follow-up task exists
                        has_open = DefaulterFollowUp.query.filter_by(
                            society_id=res.society_id, resident_id=res.id, status="OPEN"
                        ).first()
                        if not has_open:
                            PaymentService.create_defaulter_followup(
                                society_id=res.society_id,
                                resident_id=res.id,
                                flat_id=res.flat_id,
                                reason=f"Automated Escalation: {risk} Risk ({d['days_overdue']} days overdue, ₹{d['total_outstanding']:,.0f})",
                                due_date=utcnow().date() + timedelta(days=2),
                                priority="Critical",
                                notes=f"Automated recovery engine flagged resident with {d['pending_months_count']} unpaid month(s).",
                            )
                            created += 1

                    if bill:
                        bill.status = stage
                        db.session.add(bill)

                db.session.commit()

                return {
                    "scanned": scanned,
                    "created": created,
                    "updated": updated,
                    "skipped": skipped,
                }

            return _recovery

        if action_type in AutomationService.JOB_REGISTRY:
            return AutomationService.JOB_REGISTRY[action_type]

        return None

    @staticmethod
    def get_automation_history(society_id=None, limit=20):
        """Returns recent automation executions."""
        q = AutomationExecution.query
        if society_id:
            q = q.filter((AutomationExecution.society_id == society_id) | (AutomationExecution.society_id.is_(None)))
        return q.order_by(AutomationExecution.start_time.desc()).limit(limit).all()

    @staticmethod
    def get_automation_status_summary(society_id=None):
        """Returns high-level status of core society automations."""
        executions = AutomationService.get_automation_history(society_id=society_id, limit=50)
        jobs = [
            "RECONCILE_PAYMENTS",
            "GENERATE_MONTHLY_BILLS",
            "APPLY_LATE_FEES",
            "RUN_DAILY_HEALTH_CHECK",
            "SEND_DUE_REMINDERS",
            "EXPIRE_VISITOR_PASSES",
        ]
        status_map = {}
        for j in jobs:
            latest = next((e for e in executions if e.automation_name.upper() == j), None)
            if latest:
                status_map[j] = {
                    "last_status": latest.status,
                    "last_run": latest.start_time.isoformat() if latest.start_time else None,
                    "duration_ms": latest.duration_ms,
                    "records_created": latest.records_created,
                    "records_updated": latest.records_updated,
                }
            else:
                status_map[j] = {
                    "last_status": "IDLE",
                    "last_run": None,
                    "duration_ms": 0,
                    "records_created": 0,
                    "records_updated": 0,
                }
        return status_map
