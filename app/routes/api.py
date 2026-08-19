from flask import Blueprint, abort, jsonify, request, session
from app.models import db, Resident, MaintenanceBill, User, Role, Society, Building, Flat
from app.services.ai_service import AIService
from app.services.search_service import SearchService

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# ── Public endpoints used by registration form (no auth required) ──────────

# Also register at /api/buildings so the register.html form can call it


def _buildings_response():
    society_id_raw = request.args.get("society_id", "").strip()
    if not society_id_raw:
        return jsonify({"buildings": []}), 200
    try:
        society_id = int(society_id_raw)
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid society_id", "buildings": []}), 400
    if society_id <= 0 or not db.session.get(Society, society_id):
        return jsonify({"error": "Invalid society_id", "buildings": []}), 400
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
    if not society_id_raw or (not block_id_raw and not building_id_raw):
        return jsonify({"flats": []}), 200
    try:
        society_id = int(society_id_raw)
        block_id = int(block_id_raw) if block_id_raw else None
        building_id = int(building_id_raw) if building_id_raw else None
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid society, block, or building ID", "flats": []}), 400
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

