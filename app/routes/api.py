from flask import Blueprint, abort, jsonify, request, session
from app.models import db, Resident, MaintenanceBill, User, Role, Building, Flat
from app.services.ai_service import AIService
from app.services.search_service import SearchService
from app.services.society_health_service import SocietyHealthService
from app.services.single_society_service import SingleSocietyService

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")


@api_bp.before_request
def enforce_api_tenant_session_scope():
    """Reject stale or mismatched tenant scope on authenticated API calls."""
    user_id = session.get("user_id")
    if not user_id:
        return
    user = db.session.get(User, user_id)
    if not user:
        abort(401)
    if user.role in (Role.SOCIETY_ADMIN, Role.RESIDENT):
        if not user.society_id or session.get("society_id") != user.society_id:
            abort(403, description="Forbidden: Invalid society scope")

# ── Public endpoints used by registration form (no auth required) ──────────

# Also register at /api/buildings so the register.html form can call it


def _buildings_response():
    society_id_raw = request.args.get("society_id", "").strip()
    if society_id_raw:
        try:
            society_id = int(society_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid society_id", "buildings": []}), 400
        if society_id != SingleSocietyService.get_id():
            return jsonify({"error": "Invalid society_id", "buildings": []}), 403
    else:
        society_id = SingleSocietyService.get_id()
    try:
        from app.services.tenant_service import TenantService
        TenantService.ensure_default_blocks_and_flats(society_id)
    except Exception:
        pass
    buildings = (
        Building.query.filter_by(society_id=society_id)
        .order_by(Building.name.asc())
        .all()
    )
    block_names = ["Block A", "Block B", "Block C", "Block D", "Block E", "Block F"]
    std_buildings = [b for b in buildings if b.name in block_names]
    if std_buildings:
        std_buildings.sort(key=lambda b: block_names.index(b.name) if b.name in block_names else 99)
        buildings = std_buildings + [b for b in buildings if b.name not in block_names]
    return jsonify({"buildings": [{"id": b.id, "name": b.name} for b in buildings]})


def _flats_response():
    society_id_raw = request.args.get("society_id", "").strip()
    block_id_raw = request.args.get("block_id", "").strip()
    building_id_raw = request.args.get("building_id", "").strip()
    if not block_id_raw and not building_id_raw:
        return jsonify({"flats": []}), 200
    if society_id_raw:
        try:
            society_id = int(society_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid society ID", "flats": []}), 400
        if society_id != SingleSocietyService.get_id():
            return jsonify({"error": "Invalid society_id", "flats": []}), 403
    else:
        society_id = SingleSocietyService.get_id()
    try:
        block_id = int(block_id_raw) if block_id_raw else None
        building_id = int(building_id_raw) if building_id_raw else None
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid block or building ID", "flats": []}), 400
    if block_id:
        flats = (
            Flat.query.filter_by(society_id=society_id, block_id=block_id)
            .order_by(Flat.floor_number.asc(), Flat.flat_number.asc())
            .all()
        )
    elif building_id:
        flats = (
            Flat.query.filter_by(society_id=society_id, building_id=building_id)
            .order_by(Flat.floor_number.asc(), Flat.flat_number.asc())
            .all()
        )
    else:
        return jsonify({"flats": []}), 200
    return jsonify(
        {"flats": [{"id": f.id, "flat_number": f.flat_number, "floor_number": f.floor_number} for f in flats]}
    )


@api_bp.route("/residents", methods=["GET"])
def get_residents():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    if not society_id:
        return jsonify({"error": "society_id required"}), 400

    residents = Resident.query.filter_by(society_id=int(society_id)).all()
    return jsonify(
        [
            {
                "id": r.id,
                "full_name": r.full_name,
                "mobile": r.mobile,
                "email": r.email,
                "resident_type": r.resident_type,
                "occupancy_status": r.occupancy_status,
            }
            for r in residents
        ]
    )


@api_bp.route("/bills", methods=["GET"])
def get_bills():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    society_id = session.get("society_id")
    if not society_id:
        return jsonify({"error": "society_id required"}), 400

    query = MaintenanceBill.query.filter_by(society_id=int(society_id))
    if user.role == Role.RESIDENT:
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=int(society_id)
        ).first()
        if not resident:
            abort(403)
        query = query.filter_by(resident_id=resident.id)
    bills = query.all()
    return jsonify(
        [
            {
                "id": b.id,
                "bill_number": b.bill_number,
                "billing_month": b.billing_month,
                "total_amount": b.total_amount,
                "amount_paid": b.amount_paid,
                "remaining_amount": b.remaining_amount,
                "status": b.status,
            }
            for b in bills
        ]
    )


@api_bp.route("/ai/query", methods=["POST"])
def ai_query():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    prompt = (
        request.json.get("prompt", "")
        if request.is_json
        else request.form.get("prompt", "")
    )
    if not prompt:
        return jsonify({"error": "Prompt required"}), 400

    answer = AIService.answer_query(user, prompt)
    return jsonify({"prompt": prompt, "response": answer})


@api_bp.route("/search", methods=["GET"])
def global_search():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    society_id = session.get("society_id") or user.society_id
    if not society_id:
        return jsonify({"query": "", "categories": []})
    query_str = request.args.get("q", "")
    category = request.args.get("category", None)
    limit = request.args.get("limit", 6, type=int)
    res = SearchService.global_search(
        user, int(society_id), query_str, category=category, limit=limit
    )
    return jsonify(res)


# ── Automation Engine APIs ───────────────────────────────────────────────────


@api_bp.route("/automation/status", methods=["GET"])
def automation_status():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService
    status_summary = AutomationService.get_automation_status_summary(society_id=society_id)
    return jsonify({"status": "OK", "automations": status_summary})


@api_bp.route("/automation/execute", methods=["POST"])
def execute_automation():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    action_type = data.get("action_type") or request.form.get("action_type")
    if not action_type:
        return jsonify({"error": "action_type is required"}), 400
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService
    res = AutomationService.execute_job(
        action_type=action_type,
        society_id=society_id,
        executed_by=user,
        trigger_source="ADMIN_UI",
        params=data.get("params", {}),
    )
    return jsonify(res)


@api_bp.route("/automation/history", methods=["GET"])
def automation_history():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    limit = request.args.get("limit", 20, type=int)
    from app.services.automation_service import AutomationService
    history = AutomationService.get_automation_history(society_id=society_id, limit=limit)
    return jsonify([
        {
            "id": h.id,
            "execution_id": h.execution_id,
            "automation_name": h.automation_name,
            "status": h.status,
            "start_time": h.start_time.isoformat() if h.start_time else None,
            "end_time": h.end_time.isoformat() if h.end_time else None,
            "duration_ms": h.duration_ms,
            "records_scanned": h.records_scanned,
            "records_created": h.records_created,
            "records_updated": h.records_updated,
        }
        for h in history
    ])


# ── Payment Reconciliation APIs ──────────────────────────────────────────────


@api_bp.route("/reconciliation/summary", methods=["GET"])
def reconciliation_summary():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    from app.services.reconciliation_service import PaymentReconciliationService
    summary = PaymentReconciliationService.get_net_collection_summary(society_id=society_id)
    return jsonify(summary)


@api_bp.route("/reconciliation/issues", methods=["GET"])
def reconciliation_issues():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    from app.services.reconciliation_service import PaymentReconciliationService
    issues = PaymentReconciliationService.get_open_issues(society_id=society_id)
    return jsonify([
        {
            "id": i.id,
            "issue_type": i.issue_type,
            "severity": i.severity,
            "description": i.description,
            "detected_at": i.detected_at.isoformat() if i.detected_at else None,
            "payment_id": i.payment_id,
            "bill_id": i.bill_id,
            "resident_id": i.resident_id,
        }
        for i in issues
    ])


@api_bp.route("/reconciliation/resolve", methods=["POST"])
def resolve_reconciliation_issue():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    issue_id = data.get("issue_id") or request.form.get("issue_id")
    notes = data.get("notes") or request.form.get("notes", "Resolved via API")
    if not issue_id:
        return jsonify({"error": "issue_id is required"}), 400
    from app.services.reconciliation_service import PaymentReconciliationService
    res = PaymentReconciliationService.resolve_issue(int(issue_id), user, notes)
    return jsonify(res)


# ── Society Health & Daily Brief APIs ─────────────────────────────────────────


@api_bp.route("/health/score", methods=["GET"])
def get_health_score():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    society_id = session.get("society_id") or user.society_id
    from app.services.society_health_service import SocietyHealthService
    score_data = SocietyHealthService.calculate_society_health(society_id=society_id)
    return jsonify(score_data)


@api_bp.route("/health/daily-brief", methods=["GET"])
def get_daily_brief():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id
    from app.services.society_health_service import SocietyHealthService
    brief = SocietyHealthService.get_admin_daily_brief(society_id=society_id)
    return jsonify(brief)


# ── Contextual Resident AI APIs ──────────────────────────────────────────────


@api_bp.route("/resident/insights", methods=["GET"])
def resident_insights():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(user_id=user.id, society_id=society_id).first() if user.role == Role.RESIDENT else None
    if not resident:
        return jsonify({"error": "No resident profile linked to user"}), 404
    insights = AIService.get_resident_payment_insights(resident.id, society_id)
    return jsonify(insights)


@api_bp.route("/resident/daily-summary", methods=["GET"])
def resident_daily_summary():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(user_id=user.id, society_id=society_id).first() if user.role == Role.RESIDENT else None
    if not resident:
        return jsonify({"error": "No resident profile linked to user"}), 404
    summary = AIService.get_resident_daily_summary(resident.id, society_id)
    return jsonify(summary)


@api_bp.route("/complaints/classify", methods=["POST"])
def classify_complaint():
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    data = request.get_json() or {}
    title = data.get("title", "")
    description = data.get("description", "")
    classification = AIService.classify_complaint(title, description)
    return jsonify(classification)


# ── AI Communication Generators APIs ─────────────────────────────────────────

@api_bp.route("/ai/generate-notice", methods=["POST"])
def generate_notice():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    topic = data.get("topic", "")
    audience = data.get("audience", "All Residents")
    tone = data.get("tone", "Formal")
    important_points = data.get("important_points", [])

    notice = AIService.generate_notice(topic, audience, tone, important_points)
    return jsonify({"notice": notice, "requires_approval": True})


@api_bp.route("/ai/generate-whatsapp", methods=["POST"])
def generate_whatsapp():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    message_type = data.get("message_type", "maintenance_reminder")
    context_data = data.get("context_data", {})

    message = AIService.generate_whatsapp_message(message_type, context_data)
    return jsonify({"message": message, "requires_approval": True})


@api_bp.route("/ai/generate-sms", methods=["POST"])
def generate_sms():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    message_type = data.get("message_type", "maintenance_reminder")
    context_data = data.get("context_data", {})

    message = AIService.generate_sms(message_type, context_data)
    return jsonify({"message": message, "requires_approval": True})


@api_bp.route("/ai/generate-complaint-reply", methods=["POST"])
def generate_complaint_reply():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    complaint_title = data.get("complaint_title", "")
    complaint_description = data.get("complaint_description", "")
    category = data.get("category", "General Maintenance")

    reply = AIService.generate_complaint_reply(complaint_title, complaint_description, category)
    return jsonify({"reply": reply, "requires_approval": True})


# ── Financial AI APIs ───────────────────────────────────────────────────────

@api_bp.route("/ai/payment-anomalies", methods=["GET"])
def detect_payment_anomalies():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    anomalies = AIService.detect_payment_anomalies(society_id)
    return jsonify({"anomalies": anomalies, "advisory_only": True})


@api_bp.route("/ai/expense-anomalies", methods=["GET"])
def detect_expense_anomalies():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    anomalies = AIService.detect_expense_anomalies(society_id)
    return jsonify({"anomalies": anomalies, "advisory_only": True})


@api_bp.route("/ai/financial-summary", methods=["GET"])
def get_financial_summary():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    summary = AIService.generate_financial_summary(society_id)
    return jsonify({"summary": summary, "based_on_actual_data": True})


# ── Document AI APIs ───────────────────────────────────────────────────────

@api_bp.route("/ai/document-categorize", methods=["POST"])
def categorize_document():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    title = data.get("title", "")
    description = data.get("description", "")

    category = AIService.suggest_document_categorization(title, description)
    return jsonify({"suggested_category": category, "admin_can_override": True})


@api_bp.route("/ai/document-summary", methods=["POST"])
def summarize_document():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    document_title = data.get("document_title", "")
    document_content = data.get("document_content", "")

    summary = AIService.generate_document_summary(document_title, document_content)
    return jsonify({"summary": summary, "based_on_document_only": True})


@api_bp.route("/ai/document-query", methods=["POST"])
def query_document():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    data = request.get_json() or {}
    question = data.get("question", "")
    document_content = data.get("document_content", "")

    answer = AIService.ask_document(question, document_content)
    return jsonify({"answer": answer, "grounded_in_document_only": True})


# ── Summary APIs ────────────────────────────────────────────────────────────

@api_bp.route("/ai/weekly-summary", methods=["GET"])
def get_weekly_summary():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    summary = AIService.get_weekly_summary(society_id)
    return jsonify({"summary": summary, "based_on_actual_data": True})


@api_bp.route("/ai/monthly-summary", methods=["GET"])
def get_monthly_summary():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    summary = AIService.get_monthly_summary(society_id)
    return jsonify({"summary": summary, "based_on_actual_data": True})


# ── STAGE 4 Extended: Collection Prediction & Cash-Flow Forecast ────────────

@api_bp.route("/ai/collection-prediction", methods=["GET"])
def get_collection_prediction():
    """Get estimated collection forecast using historical data."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    prediction = AIService.generate_collection_prediction(society_id)
    return jsonify({"prediction": prediction, "estimate_only": True})


@api_bp.route("/ai/cash-flow-forecast", methods=["GET"])
def get_cash_flow_forecast():
    """Get projected cash flow forecast."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    forecast = AIService.generate_cash_flow_forecast(society_id)
    return jsonify({"forecast": forecast, "estimate_only": True})


# ── STAGE 5 Extended: Automation and AI Assistant ────────────────────────────

@api_bp.route("/ai/overdue-tasks", methods=["GET"])
def get_overdue_tasks():
    """Get list of overdue tasks requiring attention."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    days_overdue = request.args.get("days_overdue", 0, type=int)
    tasks = AIService.get_overdue_tasks(society_id, days_overdue=days_overdue)
    return jsonify({"tasks": tasks, "advisory_only": True})


@api_bp.route("/ai/expiring-items", methods=["GET"])
def get_expiring_items():
    """Get list of items expiring within threshold."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    days_threshold = request.args.get("days_threshold", 30, type=int)
    items = AIService.get_expiring_items(society_id, days_threshold=days_threshold)
    return jsonify({"items": items, "advisory_only": True})


@api_bp.route("/ai/low-stock", methods=["GET"])
def get_low_stock():
    """Get list of low stock inventory items."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    items = AIService.get_low_stock_items(society_id)
    return jsonify({"items": items, "advisory_only": True})


@api_bp.route("/ai/document-search", methods=["GET"])
def ai_document_search():
    """AI-enhanced document search."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    query = request.args.get("q", "")
    categories = request.args.getlist("category")

    results = SearchService.ai_document_search(user, int(society_id), query, categories=categories)
    return jsonify(results)


@api_bp.route("/ai/task-escalation-alert", methods=["GET"])
def get_task_escalation_alert():
    """Get task escalation alerts for overdue tasks."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    alert = AIService.generate_task_escalation_alert(society_id)
    return jsonify(alert)


@api_bp.route("/ai/expiry-reminder-summary", methods=["GET"])
def get_expiry_reminder_summary():
    """Get expiry reminder summary for admin review."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    days_threshold = request.args.get("days_threshold", 30, type=int)
    summary = AIService.generate_expiry_reminder_summary(society_id, days_threshold=days_threshold)
    return jsonify(summary)


@api_bp.route("/ai/low-stock-alert", methods=["GET"])
def get_low_stock_alert():
    """Get low stock alert summary."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    alert = AIService.generate_low_stock_alert(society_id)
    return jsonify(alert)


# ── STAGE 7: Resident AI Assistant ───────────────────────────────────────────

@api_bp.route("/resident/ai/query", methods=["POST"])
def resident_ai_query():
    """
    AI Assistant for residents with strict data isolation.
    Only returns data authorized for the current resident.
    Never trusts user_id, society_id, or flat_id from request body.
    Derives all values from authenticated session.
    """
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)

    prompt = request.json.get("prompt", "") if request.is_json else request.form.get("prompt", "")
    if not prompt:
        return jsonify({"error": "Prompt required"}), 400

    response = AIService.get_resident_assistant_response(user, prompt)
    return jsonify(response)


@api_bp.route("/resident/ai/feedback", methods=["POST"])
def resident_ai_feedback():
    """Fire-and-forget feedback recording for Resident AI Assistant."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role != Role.RESIDENT or user.account_status != "ACTIVE":
        abort(403)
    return jsonify({"success": True, "recorded": True})


# ── STAGE 2 Extended: Society Health AI Daily Brief ──────────────────────────

@api_bp.route("/health/ai-daily-brief", methods=["GET"])
def get_ai_daily_brief():
    """Get AI-enhanced daily brief with insights and recommendations."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)
    society_id = session.get("society_id") or user.society_id

    brief = SocietyHealthService.get_ai_daily_brief_insights(society_id=society_id)
    return jsonify(brief)

# ── PHASE 1: Resident AI Bill Explanation ────────────────────────────────────

@api_bp.route("/resident/ai/explain-bill/<int:bill_id>", methods=["GET"])
def resident_explain_bill(bill_id):
    """
    Explain a single bill in plain language.
    Resident must own the bill — identity derived from session only.
    Never modifies any record.
    """
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    if user.role != Role.RESIDENT:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    # Derive resident from session — never trust request body
    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()
    if not resident:
        return jsonify({"error": "Resident profile not found"}), 404

    bill = MaintenanceBill.query.filter_by(
        id=bill_id,
        society_id=society_id,
        resident_id=resident.id,
    ).first()
    if not bill:
        # Bill not found OR belongs to another resident — same 404, no info leak
        return jsonify({"error": "Bill not found"}), 404

    result = AIService.explain_bill(bill, resident)
    return jsonify(result)


# ── PHASE 1: Resident AI Payment Status Explanation ───────────────────────────

@api_bp.route("/resident/ai/explain-payment/<int:payment_id>", methods=["GET"])
def resident_explain_payment(payment_id):
    """
    Explain a single payment's status in plain language.
    Resident must own the payment — identity from session only.
    Never modifies any record.
    """
    from app.models import Payment

    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    if user.role != Role.RESIDENT:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()
    if not resident:
        return jsonify({"error": "Resident profile not found"}), 404

    payment = Payment.query.filter_by(
        id=payment_id,
        society_id=society_id,
        resident_id=resident.id,
    ).first()
    if not payment:
        return jsonify({"error": "Payment not found"}), 404

    result = AIService.explain_payment_status(payment, resident)
    return jsonify(result)


# ── PHASE 1: Resident Personal Dashboard Summary ─────────────────────────────

@api_bp.route("/resident/ai/dashboard-summary", methods=["GET"])
def resident_dashboard_summary():
    """
    Return a concise personal account summary for the resident dashboard.
    Identity from session only — never from request params.
    """
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    if user.role != Role.RESIDENT:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    resident = Resident.query.filter_by(
        user_id=user.id, society_id=society_id
    ).first()
    if not resident:
        return jsonify({"error": "Resident profile not found"}), 404

    result = AIService.get_resident_account_summary(resident, society_id)
    return jsonify(result)


# ── PHASE 1: Smart Notification Grouping ─────────────────────────────────────

@api_bp.route("/resident/notifications/grouped", methods=["GET"])
def resident_notifications_grouped():
    """
    Return the resident's notifications organised into category buckets.
    Presentation layer only — does NOT delete or modify notification records.
    """
    from app.models import NotificationLog

    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(401)
    if user.role != Role.RESIDENT:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    limit = request.args.get("limit", 50, type=int)
    limit = min(limit, 200)  # cap to avoid large payloads

    notifications = (
        NotificationLog.query.filter_by(
            society_id=society_id,
            user_id=user.id,
        )
        .order_by(NotificationLog.sent_at.desc())
        .limit(limit)
        .all()
    )

    result = AIService.group_resident_notifications(notifications)
    return jsonify(result)
