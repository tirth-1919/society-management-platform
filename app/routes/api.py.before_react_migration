from flask import Blueprint, abort, jsonify, request, session
from app.models import db, Resident, MaintenanceBill, User, Building, Flat
from app.services.ai_service import AIService
from app.services.search_service import SearchService

api_bp = Blueprint("api", __name__, url_prefix="/api/v1")

# ── Public endpoints used by registration form (no auth required) ──────────

# Also register at /api/buildings so the register.html form can call it


def _buildings_response():
    society_id = request.args.get("society_id")
    if not society_id:
        return jsonify({"buildings": []}), 200
    buildings = (
        Building.query.filter_by(society_id=int(society_id))
        .order_by(Building.name)
        .all()
    )
    return jsonify({"buildings": [{"id": b.id, "name": b.name} for b in buildings]})


def _flats_response():
    building_id = request.args.get("building_id")
    if not building_id:
        return jsonify({"flats": []}), 200
    flats = (
        Flat.query.filter_by(building_id=int(building_id))
        .order_by(Flat.flat_number)
        .all()
    )
    return jsonify(
        {"flats": [{"id": f.id, "flat_number": f.flat_number} for f in flats]}
    )


@api_bp.route("/residents", methods=["GET"])
def get_residents():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role == "Resident":
        abort(403)
    society_id = session.get("society_id")
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
    if user.role == "Resident":
        resident = Resident.query.filter_by(
            user_id=user.id, society_id=society_id, is_primary=True
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
    if user.role == "Resident":
        abort(403)
    society_id = session.get("society_id")
    query_str = request.args.get("q", "")
    res = SearchService.global_search(int(society_id), query_str)
    return jsonify(res)
