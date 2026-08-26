"""
AI & Automation API Routes
==========================
Exposes unified REST endpoints for AI recommendations, resident next actions, admin work queue,
contextual help, form assistance, communication intelligence, incident analysis, data quality audits,
application health, telemetry, and audit diffing.
"""

from __future__ import annotations

import logging

from flask import Blueprint, abort, jsonify, request, session

from app.models import (
    db,
    User,
    Role,
    Resident,
)
from app.services.ai.recommendation_service import AIRecommendationService
from app.services.ai.resident_ai import ResidentNextActionService, SmartResidentStatusService
from app.services.ai.admin_ai import (
    AdminWorkQueueService,
    AdminFocusModeService,
    SafeBulkActionGuard,
    RecordChangePreviewService,
)
from app.services.ai.contextual_help_service import ContextualHelpService
from app.services.ai.form_assistant_service import FormAssistantService
from app.services.ai.communication_ai import CommunicationAIService
from app.services.ai.incident_ai import IncidentAIService
from app.services.ai.data_quality_ai import DataQualityAIService, DuplicateResidentDetector
from app.services.ai.csv_import_ai import CSVImportAIService
from app.services.ai.health_ai import HealthAIService
from app.services.ai.feature_usage_service import FeatureUsageService
from app.services.ai.what_changed_service import WhatChangedService
from app.services.ai.notification_ai import SmartNotificationService

logger = logging.getLogger(__name__)

ai_bp = Blueprint("ai", __name__, url_prefix="/api/v1/ai")


def _get_authenticated_user() -> User:
    user_id = session.get("user_id")
    if not user_id:
        abort(401)
    user = db.session.get(User, int(user_id))
    if not user or not user.is_active or user.account_status != "ACTIVE":
        abort(401)
    return user


def _require_admin(user: User) -> None:
    if user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)


# ── 1. Unified Recommendations API ───────────────────────────────────────────

@ai_bp.route("/recommendations", methods=["GET"])
def get_recommendations():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    context = request.args.get("context")
    result = AIRecommendationService.get_recommendations(user=user, society_id=society_id, context=context)
    return jsonify(result), 200


# ── 2. Resident Experience APIs ──────────────────────────────────────────────

@ai_bp.route("/resident/status", methods=["GET"])
def get_resident_status():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(user_id=user.id, society_id=society_id).first()
    if not resident:
        return jsonify({"error": "Resident profile not found"}), 404

    status_data = SmartResidentStatusService.get_status(resident.id, society_id)
    return jsonify(status_data), 200


@ai_bp.route("/resident/next-actions", methods=["GET"])
def get_resident_next_actions():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(user_id=user.id, society_id=society_id).first()
    if not resident:
        return jsonify({"error": "Resident profile not found"}), 404

    actions = ResidentNextActionService.get_next_actions(resident.id, society_id)
    return jsonify({"actions": actions}), 200


# ── 3. Admin Work Queue & Focus Mode APIs ────────────────────────────────────

@ai_bp.route("/admin/work-queue", methods=["GET"])
def get_admin_work_queue():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    tasks = AdminWorkQueueService.get_work_queue(society_id)
    return jsonify({"tasks": tasks, "total_tasks": len(tasks)}), 200


@ai_bp.route("/admin/focus-mode", methods=["GET"])
def get_admin_focus_mode():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    focus_data = AdminFocusModeService.get_focus_data(society_id)
    return jsonify(focus_data), 200


# ── 4. Smart Contextual Help APIs ────────────────────────────────────────────

@ai_bp.route("/contextual-help", methods=["GET"])
def get_contextual_help():
    _get_authenticated_user()
    page_key = request.args.get("page", "admin_dashboard")
    help_info = ContextualHelpService.get_help_for_page(page_key)
    return jsonify(help_info), 200


@ai_bp.route("/contextual-help/ask", methods=["POST"])
def ask_contextual_help():
    _get_authenticated_user()
    data = request.get_json() or {}
    page_key = data.get("page", "admin_dashboard")
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "Question is required."}), 400

    answer = ContextualHelpService.answer_contextual_question(page_key, question)
    return jsonify({"page": page_key, "question": question, "answer": answer}), 200


# ── 5. Smart Form Assistant APIs ─────────────────────────────────────────────

@ai_bp.route("/form/explain-field", methods=["GET"])
def explain_form_field():
    _get_authenticated_user()
    field_name = request.args.get("field", "")
    if not field_name:
        return jsonify({"error": "field parameter required"}), 400
    explanation = FormAssistantService.explain_field(field_name)
    return jsonify({"field": field_name, "explanation": explanation}), 200


@ai_bp.route("/form/assist", methods=["POST"])
def inspect_form_assist():
    _get_authenticated_user()
    data = request.get_json() or {}
    form_context = data.get("form_context", "general")
    form_data = data.get("form_data", {})

    report = FormAssistantService.inspect_form_data(form_context, form_data)
    return jsonify(report), 200


# ── 6. Safe Bulk Action & Record Change Preview APIs ─────────────────────────

@ai_bp.route("/bulk-action/guard", methods=["POST"])
def inspect_bulk_action():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    data = request.get_json() or {}
    action_type = data.get("action_type", "")
    target_ids = data.get("target_ids", [])

    guard_info = SafeBulkActionGuard.inspect_bulk_action(action_type, target_ids, society_id)
    return jsonify(guard_info), 200


@ai_bp.route("/record-change/preview", methods=["POST"])
def preview_record_change():
    user = _get_authenticated_user()
    _require_admin(user)
    data = request.get_json() or {}
    entity_name = data.get("entity_name", "Record")
    before_data = data.get("before", {})
    after_data = data.get("after", {})

    diff = RecordChangePreviewService.generate_diff(entity_name, before_data, after_data)
    return jsonify({"entity_name": entity_name, "changes_count": len(diff), "diff": diff}), 200


# ── 7. Communication Intelligence APIs ───────────────────────────────────────

@ai_bp.route("/communication/check-tone", methods=["POST"])
def check_tone():
    _get_authenticated_user()
    data = request.get_json() or {}
    text_content = data.get("text", "")
    res = CommunicationAIService.check_tone(text_content)
    return jsonify(res), 200


@ai_bp.route("/communication/check-readability", methods=["POST"])
def check_readability():
    _get_authenticated_user()
    data = request.get_json() or {}
    text_content = data.get("text", "")
    res = CommunicationAIService.check_readability(text_content)
    return jsonify(res), 200


@ai_bp.route("/communication/check-missing-info", methods=["POST"])
def check_missing_info():
    _get_authenticated_user()
    data = request.get_json() or {}
    text_content = data.get("text", "")
    notice_type = data.get("notice_type", "General")
    res = CommunicationAIService.detect_missing_information(text_content, notice_type)
    return jsonify(res), 200


@ai_bp.route("/communication/check-duplicate-announcement", methods=["POST"])
def check_duplicate_announcement():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    data = request.get_json() or {}
    title = data.get("title", "")
    content = data.get("content", "")
    res = CommunicationAIService.detect_duplicate_announcement(society_id, title, content)
    return jsonify(res), 200


@ai_bp.route("/communication/simplify-notice", methods=["POST"])
def simplify_notice():
    _get_authenticated_user()
    data = request.get_json() or {}
    title = data.get("title", "")
    content = data.get("content", "")
    res = CommunicationAIService.simplify_notice(title, content)
    return jsonify(res), 200


@ai_bp.route("/communication/check-translation", methods=["POST"])
def check_translation():
    _get_authenticated_user()
    data = request.get_json() or {}
    orig = data.get("original", "")
    trans = data.get("translated", "")
    lang = data.get("language", "Hindi")
    res = CommunicationAIService.check_translation_consistency(orig, trans, lang)
    return jsonify(res), 200


# ── 8. Incident Intelligence APIs ────────────────────────────────────────────

@ai_bp.route("/incidents/analyze", methods=["POST"])
def analyze_incident():
    _get_authenticated_user()
    data = request.get_json() or {}
    title = data.get("title", "")
    description = data.get("description", "")
    res = IncidentAIService.classify_incident(title, description)
    return jsonify(res), 200


@ai_bp.route("/incidents/detect-duplicates", methods=["POST"])
def detect_duplicate_incidents():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    data = request.get_json() or {}
    title = data.get("title", "")
    description = data.get("description", "")
    flat_id = data.get("flat_id")
    res = IncidentAIService.detect_duplicate_incidents(society_id, title, description, flat_id)
    return jsonify(res), 200


@ai_bp.route("/incidents/timeline/<int:complaint_id>", methods=["GET"])
def get_incident_timeline(complaint_id):
    _get_authenticated_user()
    timeline = IncidentAIService.generate_incident_timeline(complaint_id)
    return jsonify({"complaint_id": complaint_id, "timeline": timeline}), 200


@ai_bp.route("/incidents/check-closure", methods=["POST"])
def check_closure():
    _get_authenticated_user()
    data = request.get_json() or {}
    complaint_id = data.get("complaint_id", 0)
    notes = data.get("resolution_notes", "")
    res = IncidentAIService.check_closure_quality(complaint_id, notes)
    return jsonify(res), 200


# ── 9. Data Quality APIs ─────────────────────────────────────────────────────

@ai_bp.route("/data-quality/scan", methods=["GET"])
def scan_data_quality():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    res = DataQualityAIService.run_full_audit(society_id)
    return jsonify(res), 200


@ai_bp.route("/data-quality/duplicate-residents", methods=["GET"])
def get_duplicate_residents():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    duplicates = DuplicateResidentDetector.find_potential_duplicates(society_id)
    return jsonify({"duplicates": duplicates, "count": len(duplicates)}), 200


# ── 10. CSV Import Assistant APIs ────────────────────────────────────────────

@ai_bp.route("/csv/suggest-mappings", methods=["POST"])
def suggest_csv_mappings():
    user = _get_authenticated_user()
    _require_admin(user)
    data = request.get_json() or {}
    headers = data.get("headers", [])
    mappings = CSVImportAIService.suggest_column_mappings(headers)
    return jsonify({"mappings": mappings}), 200


@ai_bp.route("/csv/preview-import", methods=["POST"])
def preview_csv_import():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    data = request.get_json() or {}
    csv_text = data.get("csv_text", "")
    mapping = data.get("column_mapping", {})
    preview = CSVImportAIService.preview_and_validate_import(society_id, csv_text, mapping)
    return jsonify(preview), 200


# ── 11. Health & Scheduled Job APIs ──────────────────────────────────────────

@ai_bp.route("/health/dashboard", methods=["GET"])
def get_health_dashboard():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    health = HealthAIService.get_system_health_status(society_id)
    return jsonify(health), 200


@ai_bp.route("/health/scheduled-jobs", methods=["GET"])
def get_scheduled_jobs():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    jobs = HealthAIService.get_scheduled_jobs_status(society_id)
    return jsonify({"jobs": jobs}), 200


@ai_bp.route("/health/error-patterns", methods=["GET"])
def get_error_patterns():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    patterns = HealthAIService.get_error_patterns(society_id)
    return jsonify(patterns), 200


@ai_bp.route("/health/webhook-timeline", methods=["GET"])
def get_webhook_timeline():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    timeline = HealthAIService.get_webhook_intelligence(society_id)
    return jsonify({"timeline": timeline}), 200


# ── 12. Feature Usage Telemetry & What Changed APIs ───────────────────────────

@ai_bp.route("/analytics/record-usage", methods=["POST"])
def record_feature_usage():
    data = request.get_json() or {}
    fname = data.get("feature_name", "General")
    act = data.get("action", "open")
    FeatureUsageService.record_usage(fname, act)
    return jsonify({"status": "recorded"}), 200


@ai_bp.route("/analytics/feature-usage", methods=["GET"])
def get_feature_usage():
    user = _get_authenticated_user()
    _require_admin(user)
    analytics = FeatureUsageService.get_analytics_summary()
    return jsonify(analytics), 200


@ai_bp.route("/what-changed", methods=["GET"])
def get_what_changed():
    user = _get_authenticated_user()
    entity_type = request.args.get("entity_type", "")
    entity_id = request.args.get("entity_id", type=int)
    society_id = session.get("society_id") or user.society_id
    changes = WhatChangedService.get_changes_summary(entity_type, entity_id, society_id)
    return jsonify(changes), 200


@ai_bp.route("/notifications/smart-list", methods=["GET"])
def get_smart_notifications():
    user = _get_authenticated_user()
    society_id = session.get("society_id") or user.society_id
    notifs = SmartNotificationService.group_and_rank_notifications(user.id, society_id)
    return jsonify(notifs), 200


@ai_bp.route("/notifications/mark-read/<int:notification_id>", methods=["POST"])
def mark_notification_read(notification_id):
    user = _get_authenticated_user()
    success = SmartNotificationService.mark_as_read(notification_id, user.id)
    return jsonify({"success": success}), 200


# ── 13. AI Operations Center REST APIs ──────────────────────────────────────

@ai_bp.route("/operations/dashboard", methods=["GET"])
def get_operations_dashboard_api():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    from app.services.ai import AIOperationsService
    data = AIOperationsService.get_operations_dashboard(society_id)
    return jsonify(data), 200


@ai_bp.route("/operations/run-analysis", methods=["POST"])
def run_operations_analysis_api():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    from app.services.ai import AIOperationsService
    res = AIOperationsService.run_full_society_analysis(society_id, actor_id=user.id)
    return jsonify(res), 200


@ai_bp.route("/findings", methods=["GET"])
def get_findings_api():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    from app.models.ai_operations import AIFinding

    severity = request.args.get("severity")
    system = request.args.get("system")
    status = request.args.get("status")

    query = AIFinding.query.filter_by(society_id=society_id)
    if severity:
        query = query.filter_by(severity=severity.upper())
    if system:
        query = query.filter_by(ai_system=system.upper())
    if status:
        query = query.filter_by(status=status.upper())

    findings = query.order_by(AIFinding.created_at.desc()).all()
    return jsonify({"findings": [f.to_dict() for f in findings], "count": len(findings)}), 200


@ai_bp.route("/findings/<int:id>/status", methods=["POST"])
def update_finding_status_api(id):
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    data = request.get_json() or {}
    new_status = data.get("status", "REVIEWING").upper()
    notes = data.get("notes")

    from app.services.ai import AIOperationsService
    finding = AIOperationsService.update_finding_status(
        finding_id=id,
        society_id=society_id,
        actor_id=user.id,
        new_status=new_status,
        action_taken=notes,
    )
    return jsonify(finding.to_dict()), 200


@ai_bp.route("/maintenance/risk", methods=["GET"])
def get_maintenance_risk_api():
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    from app.services.ai import PredictiveMaintenanceAIService
    analyses = PredictiveMaintenanceAIService.run_society_maintenance_analysis(society_id)
    return jsonify({"analyses": analyses, "count": len(analyses)}), 200


@ai_bp.route("/digital-twin/node/<node_type>/<int:node_id>", methods=["GET"])
def get_digital_twin_node_api(node_type, node_id):
    user = _get_authenticated_user()
    _require_admin(user)
    society_id = session.get("society_id") or user.society_id
    from app.services.ai import DigitalTwinAIService
    detail = DigitalTwinAIService.get_entity_detail_view(node_type, node_id, society_id)
    return jsonify(detail), 200


@ai_bp.route("/models", methods=["GET"])
def get_ai_models_api():
    user = _get_authenticated_user()
    _require_admin(user)
    from app.services.ai import AIModelManagementService
    models_list = AIModelManagementService.get_all_models()
    return jsonify({"models": [m.to_dict() for m in models_list]}), 200
