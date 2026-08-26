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

    SUPPORTED_EVENTS = [
        "resident_registered",
        "registration_pending",
        "registration_approved",
        "registration_rejected",
        "bill_created",
        "bill_due",
        "bill_overdue",
        "payment_created",
        "payment_verified",
        "payment_failed",
        "payment_reconciled",
        "expense_created",
        "expense_approved",
        "complaint_created",
        "complaint_overdue",
        "document_uploaded",
        "document_expiring",
        "asset_expiring",
        "inventory_low",
        "task_created",
        "task_overdue",
    ]

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
                society_id=society_id,
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
                society_id=society_id,
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

        # ── STAGE 5: Task Escalation ─────────────────────────────────────────────

        if action_type == "CHECK_OVERDUE_TASKS" or action_type == "check_overdue_tasks":
            from app.services.ai_service import AIService
            from app.models import DefaulterFollowUp

            def _check_overdue_tasks(society_id, params, executed_by):
                # Find overdue tasks
                overdue_tasks = AIService.get_overdue_tasks(society_id, days_overdue=0)
                scanned = len(DefaulterFollowUp.query.filter_by(society_id=society_id).all())

                # Create alert entries
                created = 0
                for task in overdue_tasks:
                    if task["priority"] in ["CRITICAL", "HIGH"]:
                        created += 1

                return {
                    "scanned": scanned,
                    "updated": len(overdue_tasks),
                    "critical_alerts": sum(1 for t in overdue_tasks if t["priority"] == "CRITICAL"),
                    "high_alerts": sum(1 for t in overdue_tasks if t["priority"] == "HIGH"),
                    "warnings": [f"Task #{t['task_id']}: {t['days_overdue']} days overdue" for t in overdue_tasks[:5]]
                }

            return _check_overdue_tasks

        # ── STAGE 5: Expiry Reminders ────────────────────────────────────────────

        if action_type == "CHECK_EXPIRY_REMINDERS" or action_type == "check_expiry_reminders":
            from app.services.ai_service import AIService
            from app.models import Document, Asset, Vendor
            from app.services.notification_service import NotificationService

            def _check_expiries(society_id, params, executed_by):
                days_threshold = int(params.get("days_threshold", 30))

                # Get expiring items
                expiring = AIService.get_expiring_items(society_id, days_threshold)
                scanned = len(Document.query.filter_by(society_id=society_id).all()) + \
                          len(Asset.query.filter_by(society_id=society_id).all()) + \
                          len(Vendor.query.filter_by(society_id=society_id).all())

                # Send notifications for critical items
                created = 0
                critical_items = [i for i in expiring if i["severity"] == "critical"]

                for item in critical_items:
                    try:
                        # Send notification
                        message = f"EXPIRING: {item['type'].replace('_', ' ').title()} - {item.get('title', item.get('name', 'Unknown'))} expires on {item['expiry_date'][:10]}. Action required!"
                        NotificationService.send_notification(
                            recipient="admin",
                            message=message,
                            channel="In-App",
                            society_id=society_id,
                            user_id=executed_by.id,
                            category="Alert"
                        )
                        created += 1
                    except Exception:
                        pass  # Continue even if notification fails

                return {
                    "scanned": scanned,
                    "created": created,
                    "critical_items": len(critical_items),
                    "warning_items": len([i for i in expiring if i["severity"] == "warning"]),
                    "info_items": len([i for i in expiring if i["severity"] == "info"]),
                    "warnings": [f"{i['type']}: {i.get('title', i.get('name', 'Unknown'))} - {i['days_until_expiry']} days" for i in expiring[:5]]
                }

            return _check_expiries

        # ── STAGE 5: Low Stock Automation ────────────────────────────────────────

        if action_type == "CHECK_LOW_STOCK" or action_type == "check_low_stock":
            from app.services.ai_service import AIService
            from app.models import InventoryItem
            from app.services.notification_service import NotificationService

            def _check_low_stock(society_id, params, executed_by):
                # Get low stock items
                low_stock_items = AIService.get_low_stock_items(society_id)
                scanned = len(InventoryItem.query.filter_by(society_id=society_id).all())

                # Send notifications for critical items
                created = 0
                critical_items = [i for i in low_stock_items if i["severity"] == "critical"]

                for item in critical_items:
                    try:
                        message = f"LOW STOCK CRITICAL: {item['item_name']} has 0 {item['unit']} remaining! Suggested: {item['suggested_reorder_quantity']} units."
                        NotificationService.send_notification(
                            recipient="admin",
                            message=message,
                            channel="In-App",
                            society_id=society_id,
                            user_id=executed_by.id,
                            category="Alert"
                        )
                        created += 1
                    except Exception:
                        pass  # Continue even if notification fails

                return {
                    "scanned": scanned,
                    "created": created,
                    "critical_items": len(critical_items),
                    "warning_items": len([i for i in low_stock_items if i["severity"] == "warning"]),
                    "info_items": len([i for i in low_stock_items if i["severity"] == "info"]),
                    "warnings": [f"{i['item_name']}: {i['current_stock']} {i['unit']}" for i in low_stock_items[:5]]
                }

            return _check_low_stock

        if action_type in ["SCAN_PENDING_REGISTRATIONS", "scan_pending_registrations", "ESCALATE_PENDING_REGISTRATIONS"]:
            from app.services.resident_automation_service import ResidentAutomationService
            return lambda society_id, params, executed_by: ResidentAutomationService.scan_and_escalate_pending_registrations(society_id=society_id)

        if action_type in ["SCAN_INACTIVE_RESIDENTS", "scan_inactive_residents"]:
            from app.services.resident_automation_service import ResidentAutomationService
            return lambda society_id, params, executed_by: ResidentAutomationService.detect_and_remind_inactive_residents(society_id=society_id)

        if action_type in ["DISPATCH_BILLING_REMINDERS", "dispatch_billing_reminders"]:
            from app.services.billing_automation_service import BillingAutomationService
            return lambda society_id, params, executed_by: BillingAutomationService.dispatch_billing_reminders_and_escalations(society_id=society_id)

        if action_type in ["AUDIT_BILLING_ANOMALIES", "audit_billing_anomalies"]:
            from app.services.billing_automation_service import BillingAutomationService
            def _audit_billing(society_id, params, executed_by):
                missing = BillingAutomationService.detect_missing_bills(society_id)
                dupes = BillingAutomationService.detect_duplicate_bills(society_id)
                incorrect = BillingAutomationService.detect_incorrect_billing_months(society_id)
                abnormal = BillingAutomationService.detect_abnormal_bill_amounts(society_id)
                return {
                    "scanned": 100,
                    "missing_bills": len(missing),
                    "duplicate_bills": len(dupes),
                    "incorrect_months": len(incorrect),
                    "abnormal_amounts": len(abnormal),
                }
            return _audit_billing

        if action_type in ["RUN_RECONCILIATION_PIPELINE", "run_reconciliation_pipeline"]:
            from app.services.payment_automation_service import PaymentAutomationService
            return lambda society_id, params, executed_by: PaymentAutomationService.run_reconciliation_pipeline(society_id=society_id)

        if action_type in ["SCAN_UNUSUAL_PAYMENTS", "scan_unusual_payments"]:
            from app.services.payment_automation_service import PaymentAutomationService
            def _scan_unusual_pmts(society_id, params, executed_by):
                cash_alerts = PaymentAutomationService.alert_unusual_cash_payments(society_id)
                refund_alerts = PaymentAutomationService.detect_unusual_refunds(society_id)
                suspicious = PaymentAutomationService.detect_suspicious_payments(society_id)
                return {
                    "scanned": 50,
                    "cash_alerts": len(cash_alerts),
                    "refund_alerts": len(refund_alerts),
                    "suspicious_payments": len(suspicious),
                }
            return _scan_unusual_pmts

        if action_type in ["RUN_ACCOUNTING_AUDITS", "run_accounting_audits"]:
            from app.services.accounting_automation_service import AccountingAutomationService
            return lambda society_id, params, executed_by: AccountingAutomationService.run_financial_alerts_and_audits(society_id=society_id)

        if action_type in ["GENERATE_FINANCIAL_SNAPSHOT", "generate_financial_snapshot"]:
            from app.services.accounting_automation_service import AccountingAutomationService
            return lambda society_id, params, executed_by: AccountingAutomationService.get_financial_snapshot(society_id=society_id)

        if action_type in ["RUN_SELF_HEALING_PIPELINE", "run_self_healing_pipeline"]:
            from app.services.system_health_hardening_service import SystemHealthHardeningService
            return lambda society_id, params, executed_by: SystemHealthHardeningService.run_self_healing_maintenance_pipeline(society_id=society_id, admin_user=executed_by)

    @staticmethod
    def evaluate_conditions(conditions, payload):
        """
        Safely evaluates condition dictionary against payload context dictionary.
        Supports equality, numerical comparisons, list containment.
        No arbitrary code evaluation.
        """
        if not conditions or not isinstance(conditions, dict):
            return True
        if not payload or not isinstance(payload, dict):
            return False

        for field, rule in conditions.items():
            val = payload.get(field)
            if isinstance(rule, dict):
                for op, target in rule.items():
                    try:
                        if op in ["==", "eq"]:
                            if str(val) != str(target):
                                return False
                        elif op in ["!=", "ne"]:
                            if str(val) == str(target):
                                return False
                        elif op in [">", "gt"]:
                            if val is None or float(val) <= float(target):
                                return False
                        elif op in [">=", "gte"]:
                            if val is None or float(val) < float(target):
                                return False
                        elif op in ["<", "lt"]:
                            if val is None or float(val) >= float(target):
                                return False
                        elif op in ["<=", "lte"]:
                            if val is None or float(val) > float(target):
                                return False
                        elif op in ["in", "contains"]:
                            if target not in val and val not in target:
                                return False
                    except (ValueError, TypeError):
                        return False
            else:
                if val != rule:
                    return False
        return True

    @staticmethod
    def trigger_event(event_name, society_id=None, payload=None, executed_by=None):
        """
        Evaluates and fires all active automation rules registered for `event_name`.
        Scoped to society_id.
        """
        payload = payload or {}
        q = AutomationRule.query.filter(
            AutomationRule.is_active.is_(True),
            (AutomationRule.event_name == event_name) | (AutomationRule.trigger_type == "EVENT_TRIGGERED"),
        )
        if society_id:
            q = q.filter((AutomationRule.society_id == society_id) | (AutomationRule.society_id.is_(None)))
        rules = q.order_by(AutomationRule.priority.desc()).all()

        results = []
        for rule in rules:
            conds = rule.get_conditions()
            if AutomationService.evaluate_conditions(conds, payload):
                params = rule.get_action_params()
                merged_params = {**params, **payload}
                res = AutomationService.execute_job(
                    action_type=rule.action_type,
                    society_id=society_id or rule.society_id,
                    executed_by=executed_by,
                    trigger_source=f"EVENT:{event_name}",
                    rule_id=rule.id,
                    params=merged_params,
                )
                results.append({"rule_id": rule.id, "rule_name": rule.name, "result": res})
        return results

    @staticmethod
    def retry_execution(execution_id_or_id, executed_by=None):
        """
        Re-runs a failed automation execution by ID or execution_id string.
        Increments retry_count and marks failures resolved if successful.
        """
        if isinstance(execution_id_or_id, int):
            execution = db.session.get(AutomationExecution, execution_id_or_id)
        else:
            execution = AutomationExecution.query.filter_by(execution_id=execution_id_or_id).first()

        if not execution:
            return {"success": False, "error": "Execution record not found"}

        execution.retry_count = (execution.retry_count or 0) + 1
        execution.status = "RETRYING"
        db.session.commit()

        res = AutomationService.execute_job(
            action_type=execution.automation_name,
            society_id=execution.society_id,
            executed_by=executed_by,
            trigger_source=f"RETRY:{execution.execution_id}",
            rule_id=execution.rule_id,
        )

        if res.get("success"):
            failures = AutomationFailure.query.filter_by(execution_id=execution.id).all()
            for f in failures:
                f.is_resolved = True
                f.resolved_at = utcnow()
                f.resolved_by_id = executed_by.id if executed_by else None
            db.session.commit()

        return res

    @staticmethod
    def resolve_failure(failure_id, resolved_by=None):
        """Marks an AutomationFailure record as resolved."""
        failure = db.session.get(AutomationFailure, failure_id)
        if failure:
            failure.is_resolved = True
            failure.resolved_at = utcnow()
            failure.resolved_by_id = resolved_by.id if resolved_by else None
            db.session.commit()
        return failure

    @staticmethod
    def get_rules(society_id=None):
        """Returns all AutomationRule rows scoped to society."""
        q = AutomationRule.query
        if society_id:
            q = q.filter((AutomationRule.society_id == society_id) | (AutomationRule.society_id.is_(None)))
        return q.order_by(AutomationRule.priority.desc(), AutomationRule.name.asc()).all()

    @staticmethod
    def toggle_rule(rule_id):
        """Toggles the is_active status of an AutomationRule."""
        rule = db.session.get(AutomationRule, rule_id)
        if rule:
            rule.is_active = not rule.is_active
            db.session.commit()
        return rule

    @staticmethod
    def delete_rule(rule_id):
        """Deletes an AutomationRule by ID."""
        rule = db.session.get(AutomationRule, rule_id)
        if rule:
            db.session.delete(rule)
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_alerts(society_id=None, resolved=None, limit=50):
        """Returns AutomationAlert records."""
        from app.models import AutomationAlert
        q = AutomationAlert.query
        if society_id:
            q = q.filter((AutomationAlert.society_id == society_id) | (AutomationAlert.society_id.is_(None)))
        if resolved is not None:
            q = q.filter(AutomationAlert.is_resolved.is_(resolved))
        return q.order_by(AutomationAlert.created_at.desc()).limit(limit).all()

    @staticmethod
    def resolve_alert(alert_id, resolved_by=None):
        """Marks an AutomationAlert as resolved."""
        from app.models import AutomationAlert
        alert = db.session.get(AutomationAlert, alert_id)
        if alert:
            alert.is_resolved = True
            alert.resolved_at = utcnow()
            alert.resolved_by_id = resolved_by.id if resolved_by else None
            db.session.commit()
        return alert

    @staticmethod
    def get_scheduled_jobs(society_id=None):
        """Returns list of configured scheduled jobs with status."""
        registered_scheduled = [
            {
                "action_type": "RUN_DAILY_HEALTH_CHECK",
                "name": "Daily Society Health Check",
                "schedule": "Daily at 00:00",
                "description": "Full system health, data consistency audit, and society health scoring.",
                "category": "System",
            },
            {
                "action_type": "RECONCILE_PAYMENTS",
                "name": "Payment Reconciliation Engine",
                "schedule": "Daily at 01:00",
                "description": "Audits ledger entries vs gateway logs vs bills to catch discrepancies.",
                "category": "Billing",
            },
            {
                "action_type": "GENERATE_MONTHLY_BILLS",
                "name": "Monthly Billing Batch",
                "schedule": "1st of every month",
                "description": "Generates maintenance bills for active occupied units automatically.",
                "category": "Billing",
            },
            {
                "action_type": "SEND_DUE_REMINDERS",
                "name": "Maintenance Reminders Dispatch",
                "schedule": "Daily at 09:00",
                "description": "Dispatches upcoming due and overdue payment reminders with cooldown checks.",
                "category": "Notifications",
            },
            {
                "action_type": "APPLY_LATE_FEES",
                "name": "Late Fee Assessment",
                "schedule": "Daily at 02:00",
                "description": "Calculates and updates overdue late fees according to society policy.",
                "category": "Billing",
            },
            {
                "action_type": "EXPIRE_VISITOR_PASSES",
                "name": "Visitor Pass Expiry Cleanup",
                "schedule": "Every hour",
                "description": "Deactivates visitor passes that have passed their validity window.",
                "category": "Operations",
            },
            {
                "action_type": "CHECK_OVERDUE_TASKS",
                "name": "Overdue Defaulter Task Escalation",
                "schedule": "Daily at 08:00",
                "description": "Scans overdue tasks and raises critical alerts for administrators.",
                "category": "Operations",
            },
            {
                "action_type": "CHECK_EXPIRY_REMINDERS",
                "name": "Document & Asset Expiry Check",
                "schedule": "Daily at 07:00",
                "description": "Scans documents, asset warranties, and vendor contracts nearing expiry.",
                "category": "Operations",
            },
            {
                "action_type": "CHECK_LOW_STOCK",
                "name": "Low Inventory Stock Alert",
                "schedule": "Daily at 10:00",
                "description": "Scans inventory stock quantities against configured minimum thresholds.",
                "category": "Inventory",
            },
            {
                "action_type": "SCAN_PENDING_REGISTRATIONS",
                "name": "Pending Registration Escalation Scanner",
                "schedule": "Daily at 08:30",
                "description": "Scans pending memberships for 3-day and 7-day critical escalation.",
                "category": "Resident",
            },
            {
                "action_type": "SCAN_INACTIVE_RESIDENTS",
                "name": "Inactive Resident Profile Audit",
                "schedule": "Weekly on Monday",
                "description": "Scans resident profiles for missing emergency contacts and sends reminders.",
                "category": "Resident",
            },
            {
                "action_type": "DISPATCH_BILLING_REMINDERS",
                "name": "Billing Reminder & Escalation Dispatcher",
                "schedule": "Daily at 09:30",
                "description": "Dispatches upcoming, overdue, and final notices with cooldown protection.",
                "category": "Billing",
            },
            {
                "action_type": "AUDIT_BILLING_ANOMALIES",
                "name": "Billing Anomaly & Integrity Audit",
                "schedule": "Daily at 03:00",
                "description": "Detects missing, duplicate, incorrect, and abnormal bill amounts.",
                "category": "Billing",
            },
            {
                "action_type": "RUN_RECONCILIATION_PIPELINE",
                "name": "Automated Reconciliation & Issue Escalation",
                "schedule": "Daily at 01:30",
                "description": "Audits payment ledger and escalates unresolved reconciliation issues > 3 days.",
                "category": "Payment",
            },
            {
                "action_type": "SCAN_UNUSUAL_PAYMENTS",
                "name": "Unusual Payment & Cash Audit",
                "schedule": "Daily at 18:00",
                "description": "Flags cash payments > ₹20k, unverified cash > 48h, and unusual refunds.",
                "category": "Payment",
            },
            {
                "action_type": "RUN_ACCOUNTING_AUDITS",
                "name": "Financial Alerts & Expense Audits",
                "schedule": "Daily at 04:00",
                "description": "Audits budget overruns, unusual expenses > 3x average, and missing invoices.",
                "category": "Accounting",
            },
            {
                "action_type": "GENERATE_FINANCIAL_SNAPSHOT",
                "name": "Executive Financial Health Snapshot",
                "schedule": "Daily at 23:55",
                "description": "Calculates daily surplus, category totals, and current cash/bank position.",
                "category": "Accounting",
            },
            {
                "action_type": "RUN_SELF_HEALING_PIPELINE",
                "name": "Automated Self-Healing & Data Repair",
                "schedule": "Daily at 05:00",
                "description": "Repairs flat occupancy, reconciles bill balances, and regenerates missing receipts.",
                "category": "System",
            },
        ]

        status_map = AutomationService.get_automation_status_summary(society_id=society_id)
        jobs = []
        for item in registered_scheduled:
            st = status_map.get(item["action_type"], {})
            jobs.append({
                **item,
                "last_status": st.get("last_status", "IDLE"),
                "last_run": st.get("last_run"),
                "duration_ms": st.get("duration_ms", 0),
            })
        return jobs

    @staticmethod
    def get_failed_automations(society_id=None, limit=50):
        """Returns failed executions and unresolved failure records."""
        q = AutomationExecution.query.filter(AutomationExecution.status.in_(["FAILED", "WARNING"]))
        if society_id:
            q = q.filter((AutomationExecution.society_id == society_id) | (AutomationExecution.society_id.is_(None)))
        return q.order_by(AutomationExecution.start_time.desc()).limit(limit).all()

    # ── Simple CRUD helpers ───────────────────────────────────────────────────

    @staticmethod
    def create_rule(
        society_id,
        name,
        action_type,
        trigger_type="MANUAL",
        event_name=None,
        priority=1,
        description=None,
        schedule_cron=None,
        conditions=None,
        action_params=None,
        cooldown_seconds=60,
        retry_limit=3,
        is_active=True,
    ):
        """
        Creates a new AutomationRule record for the given society.
        Returns the created rule.
        """
        import json as _json
        rule = AutomationRule(
            society_id=society_id,
            name=name,
            description=description,
            trigger_type=trigger_type,
            event_name=event_name,
            priority=priority,
            schedule_cron=schedule_cron,
            conditions_json=_json.dumps(conditions) if conditions else None,
            action_type=action_type,
            action_params_json=_json.dumps(action_params) if action_params else None,
            cooldown_seconds=cooldown_seconds,
            retry_limit=retry_limit,
            is_active=is_active,
        )
        db.session.add(rule)
        db.session.commit()
        return rule

    @staticmethod
    def enable_rule(rule_id):
        """Enables an AutomationRule by ID. Returns the updated rule or None."""
        rule = db.session.get(AutomationRule, rule_id)
        if rule:
            rule.is_active = True
            db.session.commit()
        return rule

    @staticmethod
    def disable_rule(rule_id):
        """Disables an AutomationRule by ID. Returns the updated rule or None."""
        rule = db.session.get(AutomationRule, rule_id)
        if rule:
            rule.is_active = False
            db.session.commit()
        return rule

    @staticmethod
    def record_execution(
        automation_name,
        society_id=None,
        status="COMPLETED",
        trigger_source="SYSTEM",
        rule_id=None,
        executed_by_id=None,
        records_scanned=0,
        records_created=0,
        records_updated=0,
        records_skipped=0,
        duration_ms=0,
        warnings=None,
        errors=None,
    ):
        """
        Records an automation execution directly (for external callers that
        run their own logic and only need to persist the outcome).
        Returns the created AutomationExecution.
        """
        execution_id = f"exec_{__import__('uuid').uuid4().hex[:12]}"
        now = utcnow()
        execution = AutomationExecution(
            rule_id=rule_id,
            society_id=society_id,
            automation_name=automation_name,
            execution_id=execution_id,
            status=status,
            start_time=now,
            end_time=now,
            duration_ms=duration_ms,
            trigger_source=trigger_source,
            executed_by_id=executed_by_id,
            records_scanned=records_scanned,
            records_created=records_created,
            records_updated=records_updated,
            records_skipped=records_skipped,
            warnings_json=json.dumps(warnings) if warnings else None,
            errors_json=json.dumps(errors) if errors else None,
        )
        db.session.add(execution)
        db.session.commit()
        return execution

    @staticmethod
    def record_failure(execution_id_int, rule_id=None, society_id=None, error_message="", stack_trace=None):
        """
        Records an AutomationFailure against an existing execution row.
        execution_id_int is the integer PK of AutomationExecution.
        Returns the created AutomationFailure.
        """
        failure = AutomationFailure(
            execution_id=execution_id_int,
            rule_id=rule_id,
            society_id=society_id,
            error_message=error_message,
            stack_trace=stack_trace,
            retry_count=0,
            is_resolved=False,
        )
        db.session.add(failure)
        db.session.commit()
        return failure

    @staticmethod
    def create_alert(society_id, message, severity="INFO", source=None, executed_by_id=None, title=None, rule_id=None, execution_id=None):
        """
        Persists an alert by creating an AutomationAlert record AND recording a MANUAL
        AutomationExecution with status WARNING or FAILED.
        severity: INFO | WARNING | CRITICAL
        Returns the created AutomationAlert.
        """
        from app.models import AutomationAlert

        alert_title = title or f"Alert: {severity.title()}"
        alert = AutomationAlert(
            society_id=society_id,
            rule_id=rule_id,
            execution_id=execution_id,
            alert_type=source or "SYSTEM",
            severity=severity,
            title=alert_title,
            message=message,
            is_resolved=False,
        )
        db.session.add(alert)

        status_map = {"INFO": "COMPLETED", "WARNING": "WARNING", "CRITICAL": "FAILED"}
        exec_record = AutomationService.record_execution(
            automation_name=f"ALERT_{severity}",
            society_id=society_id,
            status=status_map.get(severity, "WARNING"),
            trigger_source="SYSTEM",
            executed_by_id=executed_by_id,
            errors=[message] if severity == "CRITICAL" else None,
            warnings=[message] if severity == "WARNING" else None,
        )
        alert.execution_id = exec_record.id
        db.session.commit()
        return alert

    @staticmethod
    def get_dashboard_stats(society_id=None):
        """
        Returns counts used by the Automation Center dashboard cards:
          active_automations  – enabled AutomationRule rows
          todays_executions   – executions started today
          successful          – COMPLETED executions today
          failed              – FAILED executions today
          pending_actions     – executions currently RUNNING or PENDING
          critical_alerts     – unresolved AutomationFailure rows
        """
        today_start = utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

        rule_q = AutomationRule.query
        if society_id:
            rule_q = rule_q.filter(
                (AutomationRule.society_id == society_id) | (AutomationRule.society_id.is_(None))
            )
        active_automations = rule_q.filter(AutomationRule.is_active.is_(True)).count()

        exec_q = AutomationExecution.query
        if society_id:
            exec_q = exec_q.filter(
                (AutomationExecution.society_id == society_id) | (AutomationExecution.society_id.is_(None))
            )

        todays_executions = exec_q.filter(AutomationExecution.start_time >= today_start).count()
        successful = exec_q.filter(
            AutomationExecution.start_time >= today_start,
            AutomationExecution.status == "COMPLETED",
        ).count()
        failed = exec_q.filter(
            AutomationExecution.start_time >= today_start,
            AutomationExecution.status.in_(["FAILED", "WARNING"]),
        ).count()
        pending_actions = exec_q.filter(
            AutomationExecution.status.in_(["RUNNING", "PENDING"]),
        ).count()

        failure_q = AutomationFailure.query.filter(AutomationFailure.is_resolved.is_(False))
        if society_id:
            failure_q = failure_q.filter(
                (AutomationFailure.society_id == society_id) | (AutomationFailure.society_id.is_(None))
            )
        crit_failure_count = failure_q.count()

        from app.models import AutomationAlert
        alert_q = AutomationAlert.query.filter(
            AutomationAlert.is_resolved.is_(False),
            AutomationAlert.severity.in_(["CRITICAL", "FAILED"]),
        )
        if society_id:
            alert_q = alert_q.filter(
                (AutomationAlert.society_id == society_id) | (AutomationAlert.society_id.is_(None))
            )
        crit_alert_count = alert_q.count()
        critical_alerts = max(crit_failure_count, crit_alert_count)

        return {
            "active_automations": active_automations,
            "todays_executions": todays_executions,
            "successful": successful,
            "failed": failed,
            "pending_actions": pending_actions,
            "critical_alerts": critical_alerts,
        }

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
            "CHECK_OVERDUE_TASKS",
            "CHECK_EXPIRY_REMINDERS",
            "CHECK_LOW_STOCK",
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