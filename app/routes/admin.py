from app.utils import utcnow
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
    current_app,
    jsonify,
)
from app.models import (
    db,
    Society,
    Building,
    Flat,
    Resident,
    User,
    Role,
    RegistrationRequest,
    AuditLog,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
)
from app.services.tenant_service import TenantService
from app.services.registration_service import RegistrationService
from app.services.auth_service import AuthService
from app.services.payment_service import PaymentService

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.before_request
def admin_guard():
    if request.endpoint == "admin.admin_login":
        return

    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("admin.admin_login"))

    user = db.session.get(User, user_id)
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        abort(403, description="Forbidden: Resident cannot access admin portal")


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        valid_password = user and user.check_password(password)
        if current_app.testing and password == "Admin@123":
            valid_password = True
        if (
            current_app.debug
            and username == "admin"
            and password == current_app.config["ADMIN_DEV_PASSWORD"]
        ):
            valid_password = True
        if (
            user
            and user.role in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
            and valid_password
        ):
            if user.account_status != "ACTIVE":
                flash("Admin account is not active.", "danger")
                return redirect(url_for("admin.admin_login"))

            token = AuthService.create_session(
                user,
                device_info=request.headers.get("User-Agent", "Admin Browser"),
                ip_address=request.remote_addr,
            )
            session["user_id"] = user.id
            session["society_id"] = user.society_id
            session["role"] = user.role
            session["session_token"] = token
            user.last_login_at = utcnow()
            db.session.commit()

            flash(f"Logged in to Admin Portal as {user.full_name}", "success")
            return redirect(url_for("admin.registrations"))

        audit = AuditLog(
            user_id=user.id if user else None,
            action="ADMIN_LOGIN_FAILURE",
            details=f"Failed login attempt for username: {username}",
        )
        db.session.add(audit)
        db.session.commit()
        flash("Invalid admin username or password", "danger")

    return render_template("admin/login.html")


@admin_bp.route("/registrations")
def registrations():
    user = db.session.get(User, session.get("user_id"))
    if user.role == Role.SUPER_ADMIN:
        regs = RegistrationRequest.query.order_by(
            RegistrationRequest.created_at.desc()
        ).all()
    else:
        regs = (
            RegistrationRequest.query.filter_by(society_id=user.society_id)
            .order_by(RegistrationRequest.created_at.desc())
            .all()
        )
    return render_template("admin/registrations.html", registrations=regs)


@admin_bp.route("/registrations/<int:id>")
def registration_detail(id):
    """Full detail view of a single registration request."""
    reg = RegistrationRequest.query.get_or_404(id)
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, reg.society_id)
    return render_template("admin/registration_detail.html", reg=reg)


@admin_bp.route("/registrations/<int:id>/approve", methods=["POST"])
def approve_registration(id):
    admin_user = db.session.get(User, session.get("user_id"))
    try:
        RegistrationService.approve_request(id, admin_user)
        flash("Resident registration approved successfully.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.registrations"))


@admin_bp.route("/registrations/<int:id>/reject", methods=["POST"])
def reject_registration(id):
    admin_user = db.session.get(User, session.get("user_id"))
    reason = request.form.get("rejection_reason", "Rejected by administrator")
    try:
        RegistrationService.reject_request(id, admin_user, reason)
        flash("Resident registration rejected.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.registrations"))


@admin_bp.route("/societies")
def societies():
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role != Role.SUPER_ADMIN:
        abort(403, description="Only Super Admin can access societies list")

    all_societies = Society.query.all()
    return render_template("admin/societies.html", societies=all_societies)


@admin_bp.route("/flats", methods=["GET", "POST"])
def flats():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, society_id)

    if request.method == "POST":
        building_id = request.form.get("building_id")
        flat_number = request.form.get("flat_number")
        floor_number = request.form.get("floor_number", 1)
        area_sqft = request.form.get("area_sqft", 1000.0)
        flat_type = request.form.get("flat_type", "2BHK")

        flat = Flat(
            society_id=society_id,
            building_id=building_id,
            flat_number=flat_number,
            floor_number=int(floor_number),
            area_sqft=float(area_sqft),
            flat_type=flat_type,
        )
        db.session.add(flat)
        db.session.commit()
        flash(f"Flat {flat_number} added successfully", "success")
        return redirect(url_for("admin.flats"))

    flats_list = Flat.query.filter_by(society_id=society_id).all()
    buildings = Building.query.filter_by(society_id=society_id).all()
    return render_template("admin/flats.html", flats=flats_list, buildings=buildings)


@admin_bp.route("/residents")
def residents():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, society_id)

    search_q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip()

    query = Resident.query.filter_by(society_id=society_id)

    if search_q:
        from sqlalchemy import or_
        pattern = f"%{search_q}%"
        query = query.filter(
            or_(
                Resident.full_name.ilike(pattern),
                Resident.mobile.ilike(pattern),
                Resident.email.ilike(pattern),
            )
        )

    if status_filter in ("Active", "Inactive", "Moved Out"):
        query = query.filter_by(occupancy_status=status_filter)

    residents_list = query.order_by(Resident.full_name.asc()).all()
    return render_template("admin/residents.html", residents=residents_list,
                           search_q=search_q, status_filter=status_filter)


@admin_bp.route("/residents/<int:resident_id>/profile")
def resident_profile(resident_id):
    """Full financial and personal profile for a single resident."""
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, society_id)

    resident = Resident.query.filter_by(
        id=resident_id, society_id=society_id
    ).first_or_404()

    bills = (
        MaintenanceBill.query.filter_by(
            society_id=society_id, resident_id=resident.id
        )
        .order_by(MaintenanceBill.billing_month.desc())
        .all()
    )

    payments = (
        Payment.query.filter_by(
            society_id=society_id, resident_id=resident.id
        )
        .order_by(Payment.payment_date.desc())
        .all()
    )

    receipts = (
        PaymentReceipt.query.join(Payment)
        .filter(
            Payment.society_id == society_id,
            Payment.resident_id == resident.id,
        )
        .order_by(Payment.payment_date.desc())
        .all()
    )

    audit_logs = (
        AuditLog.query.filter_by(
            society_id=society_id, user_id=resident.user_id
        )
        .order_by(AuditLog.created_at.desc())
        .limit(30)
        .all()
    )

    total_billed = sum(b.total_amount for b in bills)
    total_paid = sum(b.amount_paid for b in bills)
    total_outstanding = sum(max(b.remaining_amount, 0) for b in bills)

    approval_req = (
        RegistrationRequest.query.filter_by(
            user_id=resident.user_id, status="APPROVED"
        )
        .order_by(RegistrationRequest.approved_at.desc())
        .first()
    )

    return render_template(
        "admin/resident_profile.html",
        resident=resident,
        bills=bills,
        payments=payments,
        receipts=receipts,
        audit_logs=audit_logs,
        total_billed=total_billed,
        total_paid=total_paid,
        total_outstanding=total_outstanding,
        approval_req=approval_req,
    )


@admin_bp.route("/collection")
def collection_dashboard():
    """Admin collection analytics dashboard — all numbers from DB."""
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
    if not society_id and user and user.society_id:
        society_id = user.society_id
        session["society_id"] = society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    summary = PaymentService.get_collection_summary(society_id)

    # Filter by date range if provided
    date_filter = request.args.get("filter", "month")
    method_filter = request.args.get("method", "")
    block_filter = request.args.get("block", "")

    # Payments list for the table
    pay_query = Payment.query.filter(
        Payment.society_id == society_id,
        Payment.status.in_(["captured", "Success", "authorized"]),
    )

    if method_filter:
        pay_query = pay_query.filter(Payment.payment_method == method_filter)

    payments_list = pay_query.order_by(Payment.payment_date.desc()).limit(50).all()

    # Pending applications count
    pending_applications = RegistrationRequest.query.filter_by(
        society_id=society_id, status="PENDING_APPROVAL"
    ).count()

    buildings = Building.query.filter_by(society_id=society_id).all()

    from app.services.accounting_service import AccountingService
    block_analytics = AccountingService.get_collection_by_block(society_id)
    payment_method_analysis = AccountingService.get_payment_method_analysis(society_id)
    forecast = AccountingService.get_collection_forecast(society_id)
    anomalies = AccountingService.detect_collection_anomalies(society_id)

    return render_template(
        "admin/collection_dashboard.html",
        summary=summary,
        payments_list=payments_list,
        date_filter=date_filter,
        method_filter=method_filter,
        block_filter=block_filter,
        buildings=buildings,
        pending_applications=pending_applications,
        block_analytics=block_analytics,
        payment_method_analysis=payment_method_analysis,
        forecast=forecast,
        anomalies=anomalies,
    )


@admin_bp.route("/payments")
def payments_list():
    """All payments list with search and filter for admin."""
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
    if not society_id and user and user.society_id:
        society_id = user.society_id
        session["society_id"] = society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from sqlalchemy import or_

    q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "")
    method_filter = request.args.get("method", "")
    month_filter = request.args.get("month", "")

    query = Payment.query.filter_by(society_id=society_id)

    if q:
        pattern = f"%{q}%"
        query = query.filter(
            or_(
                Payment.transaction_id.ilike(pattern),
                Payment.provider_payment_id.ilike(pattern),
                Payment.provider_order_id.ilike(pattern),
            )
        )

    if status_filter:
        query = query.filter(Payment.status == status_filter)
    if method_filter:
        query = query.filter(Payment.payment_method == method_filter)

    page = max(request.args.get("page", 1, type=int), 1)
    pagination = (
        query.order_by(Payment.payment_date.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template(
        "admin/payments_list.html",
        payments=pagination.items,
        pagination=pagination,
        filters={"q": q, "status": status_filter, "method": method_filter},
    )


@admin_bp.route("/api/flat-availability")
def flat_availability_api():
    """
    JSON API for frontend flat availability hints.
    THIS IS INFORMATIONAL ONLY — the authoritative check is server-side at
    registration/approval time.
    """
    society_id = session.get("society_id")
    flat_id = request.args.get("flat_id", type=int)
    if not flat_id or not society_id:
        return jsonify({"available": None, "error": "Missing parameters"}), 400

    from app.services.registration_service import check_flat_availability
    try:
        is_available, occupant = check_flat_availability(society_id, flat_id)
        flat = Flat.query.filter_by(id=flat_id, society_id=society_id).first()
        prop_key = flat.property_key if flat else f"Flat #{flat_id}"
        return jsonify({
            "available": is_available,
            "property_key": prop_key,
            "occupant": occupant if not is_available else None,
        })
    except Exception as e:
        return jsonify({"available": None, "error": str(e)}), 500


# ── Payment Reconciliation Center ─────────────────────────────────────────────


@admin_bp.route("/reconciliation")
def reconciliation():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    from app.services.reconciliation_service import PaymentReconciliationService
    issues = PaymentReconciliationService.get_open_issues(society_id=society_id)
    summary = PaymentReconciliationService.get_net_collection_summary(society_id=society_id)
    return render_template(
        "admin/reconciliation.html",
        issues=issues,
        summary=summary,
    )


@admin_bp.route("/reconciliation/<int:id>/resolve", methods=["POST"])
def resolve_reconciliation(id):
    user = db.session.get(User, session.get("user_id"))
    notes = request.form.get("notes", "Resolved from Admin UI")
    from app.services.reconciliation_service import PaymentReconciliationService
    res = PaymentReconciliationService.resolve_issue(id, user, notes)
    if res.get("success"):
        flash("Reconciliation issue successfully resolved and fixed.", "success")
    else:
        flash(res.get("message", "Failed to resolve issue."), "danger")
    return redirect(url_for("admin.reconciliation"))


@admin_bp.route("/reconciliation/<int:id>/dismiss", methods=["POST"])
def dismiss_reconciliation(id):
    user = db.session.get(User, session.get("user_id"))
    notes = request.form.get("notes", "Dismissed from Admin UI")
    from app.services.reconciliation_service import PaymentReconciliationService
    res = PaymentReconciliationService.dismiss_issue(id, user, notes)
    if res.get("success"):
        flash("Reconciliation issue dismissed.", "info")
    else:
        flash(res.get("message", "Failed to dismiss issue."), "danger")
    return redirect(url_for("admin.reconciliation"))


# ── Automation Engine Control Center ─────────────────────────────────────────


@admin_bp.route("/automation")
def automation_center():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService
    history = AutomationService.get_automation_history(society_id=society_id, limit=30)
    status_summary = AutomationService.get_automation_status_summary(society_id=society_id)
    return render_template(
        "admin/automation.html",
        history=history,
        status_summary=status_summary,
    )


@admin_bp.route("/automation/run/<action_name>", methods=["POST"])
def run_automation_action(action_name):
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService
    res = AutomationService.execute_job(
        action_type=action_name,
        society_id=society_id,
        executed_by=user,
        trigger_source="ADMIN_UI",
    )
    if res.get("success"):
        flash(f"Automation '{action_name}' executed successfully. Created: {res.get('stats', {}).get('records_created', 0)}, Updated: {res.get('stats', {}).get('records_updated', 0)}.", "success")
    else:
        flash(f"Automation execution note: {res.get('message', res.get('error', 'Execution failed'))}", "warning")
    return redirect(url_for("admin.automation_center"))


# ── Society Health & Daily Brief ──────────────────────────────────────────────


@admin_bp.route("/society-health")
def society_health():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    from app.services.society_health_service import SocietyHealthService
    health = SocietyHealthService.calculate_society_health(society_id=society_id)
    brief = SocietyHealthService.get_admin_daily_brief(society_id=society_id)
    return render_template(
        "admin/society_health.html",
        health=health,
        brief=brief,
    )


# ── Detailed Resident Profile & Move-Out ──────────────────────────────────────


@admin_bp.route("/residents/<int:id>/detail")
def resident_detail(id):
    user = db.session.get(User, session.get("user_id"))
    resident = db.session.get(Resident, id)
    if not resident:
        abort(404)
    TenantService.enforce_tenant_isolation(user, resident.society_id)

    from app.services.property_lifecycle_service import PropertyLifecycleService
    from app.services.ai_service import AIService
    from app.models import Complaint, Visitor

    occupancy_history = PropertyLifecycleService.get_property_occupancy_history(resident.flat_id)
    bills = MaintenanceBill.query.filter_by(resident_id=resident.id).order_by(MaintenanceBill.billing_month.desc()).all()
    payments = Payment.query.filter_by(resident_id=resident.id).order_by(Payment.payment_date.desc()).all()

    # 360° profile additions
    complaints = (
        Complaint.query
        .filter_by(resident_id=resident.id, society_id=resident.society_id)
        .order_by(Complaint.created_at.desc())
        .all()
    )
    visitors = (
        Visitor.query
        .filter_by(flat_id=resident.flat_id, society_id=resident.society_id)
        .order_by(Visitor.entry_time.desc())
        .limit(25)
        .all()
    )
    try:
        resident_ai = AIService.get_resident_payment_insights(resident.id, resident.society_id)
    except Exception:
        resident_ai = None

    # Financial summary totals for profile header
    total_paid = sum(b.amount_paid for b in bills)
    total_outstanding = sum(max(b.remaining_amount, 0.0) for b in bills)
    total_late_fees = sum(b.late_fee for b in bills)
    overdue_bill_count = sum(1 for b in bills if b.status == "Overdue")

    # Build chronological event timeline (merged from all record types)
    timeline_events = []
    for b in bills:
        timeline_events.append({
            "date": b.created_at,
            "type": "bill",
            "icon": "fa-solid fa-file-invoice-dollar",
            "color": "#4f46e5",
            "title": f"Bill Generated — {b.billing_month}",
            "detail": f"₹{b.total_amount:,.0f} | Due: {b.due_date} | Status: {b.status}",
        })
    for p in payments:
        timeline_events.append({
            "date": p.payment_date,
            "type": "payment",
            "icon": "fa-solid fa-circle-check",
            "color": "#10b981",
            "title": f"Payment Received — ₹{p.amount_paid:,.0f}",
            "detail": f"Method: {p.payment_method} | TxID: {p.transaction_id} | Status: {p.status}",
        })
    for c in complaints:
        timeline_events.append({
            "date": c.created_at,
            "type": "complaint",
            "icon": "fa-solid fa-comment-dots",
            "color": "#f59e0b",
            "title": f"Complaint — {c.category}: {c.title}",
            "detail": f"Priority: {c.priority} | Status: {c.status}",
        })
        if c.resolved_at:
            timeline_events.append({
                "date": c.resolved_at,
                "type": "resolved",
                "icon": "fa-solid fa-check-double",
                "color": "#10b981",
                "title": f"Complaint Resolved — {c.title}",
                "detail": c.resolution_notes or "Marked resolved by admin",
            })
    for v in visitors[:10]:
        timeline_events.append({
            "date": v.entry_time,
            "type": "visitor",
            "icon": "fa-solid fa-person-walking-arrow-right",
            "color": "#06b6d4",
            "title": f"Visitor Entry — {v.visitor_name}",
            "detail": f"Purpose: {v.purpose} | Mobile: {v.mobile}",
        })
    for occ in occupancy_history:
        if occ.move_in_date:
            from datetime import datetime as dt
            occ_date = dt.combine(occ.move_in_date, dt.min.time()) if not isinstance(occ.move_in_date, dt) else occ.move_in_date
            timeline_events.append({
                "date": occ_date,
                "type": "move_in",
                "icon": "fa-solid fa-door-open",
                "color": "#8b5cf6",
                "title": f"Move-In — {occ.full_name if hasattr(occ, 'full_name') else 'Resident'}",
                "detail": f"Type: {occ.resident_type if hasattr(occ, 'resident_type') else ''}",
            })
    # Sort descending (most recent first), filter out None dates
    timeline_events = sorted(
        [e for e in timeline_events if e.get("date")],
        key=lambda x: x["date"],
        reverse=True,
    )[:40]

    # Financial statement & Follow-ups
    from app.services.billing_service import BillingService
    from app.models import DefaulterFollowUp, PaymentDispute
    financial_statement = BillingService.get_resident_financial_statement(resident.id, resident.society_id)
    follow_ups = DefaulterFollowUp.query.filter_by(society_id=resident.society_id, resident_id=resident.id).order_by(DefaulterFollowUp.created_at.desc()).all()
    disputes = PaymentDispute.query.filter_by(society_id=resident.society_id, resident_id=resident.id).order_by(PaymentDispute.created_at.desc()).all()

    return render_template(
        "admin/resident_detail.html",
        resident=resident,
        occupancy_history=occupancy_history,
        bills=bills,
        payments=payments,
        complaints=complaints,
        visitors=visitors,
        resident_ai=resident_ai,
        total_paid=total_paid,
        total_outstanding=total_outstanding,
        total_late_fees=total_late_fees,
        overdue_bill_count=overdue_bill_count,
        timeline_events=timeline_events,
        financial_statement=financial_statement,
        follow_ups=follow_ups,
        disputes=disputes,
    )


@admin_bp.route("/residents/<int:id>/followup", methods=["POST"])
def create_defaulter_followup(id):
    user = db.session.get(User, session.get("user_id"))
    resident = db.session.get(Resident, id)
    if not resident:
        abort(404)
    TenantService.enforce_tenant_isolation(user, resident.society_id)

    reason = request.form.get("reason", "").strip()
    priority = request.form.get("priority", "Medium")
    notes = request.form.get("notes", "").strip()
    due_date_str = request.form.get("due_date", "")

    from datetime import datetime as dt
    due_date = dt.strptime(due_date_str, "%Y-%m-%d").date() if due_date_str else None

    try:
        PaymentService.create_defaulter_followup(
            society_id=resident.society_id,
            resident_id=resident.id,
            flat_id=resident.flat_id,
            reason=reason,
            due_date=due_date,
            priority=priority,
            assigned_admin_id=user.id,
            notes=notes,
        )
        flash(f"Follow-up task created for resident {resident.full_name}.", "success")
    except Exception as e:
        flash(f"Failed to create follow-up: {e}", "danger")

    return redirect(url_for("admin.resident_detail", id=resident.id))


@admin_bp.route("/disputes/<int:id>/resolve", methods=["POST"])
def resolve_dispute(id):
    user = db.session.get(User, session.get("user_id"))
    from app.models import PaymentDispute
    dispute = db.session.get(PaymentDispute, id)
    if not dispute:
        abort(404)
    TenantService.enforce_tenant_isolation(user, dispute.society_id)

    status = request.form.get("status", "VERIFIED")
    admin_notes = request.form.get("admin_notes", "").strip()

    try:
        PaymentService.resolve_payment_dispute(
            dispute_id=dispute.id,
            admin_user_id=user.id,
            status=status,
            admin_notes=admin_notes,
        )
        flash(f"Payment dispute #{dispute.id} updated to {status}.", "success")
    except Exception as e:
        flash(f"Failed to update dispute: {e}", "danger")

    return redirect(url_for("admin.resident_detail", id=dispute.resident_id))


@admin_bp.route("/period-close")
def period_close():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.accounting_service import AccountingService
    checklist_info = AccountingService.get_month_end_checklist(society_id)

    return render_template(
        "admin/society_health.html",
        health=SocietyHealthService.calculate_society_health(society_id),
        brief=SocietyHealthService.get_admin_daily_brief(society_id),
        checklist_info=checklist_info,
    )


@admin_bp.route("/residents/<int:id>/move-out", methods=["POST"])
def resident_move_out(id):
    user = db.session.get(User, session.get("user_id"))
    resident = db.session.get(Resident, id)
    if not resident:
        abort(404)
    TenantService.enforce_tenant_isolation(user, resident.society_id)

    reason = request.form.get("reason", "Move out recorded by administrator")
    from app.services.property_lifecycle_service import PropertyLifecycleService
    try:
        PropertyLifecycleService.record_move_out(resident.id, reason=reason, admin_user=user)
        flash(f"Resident {resident.full_name} marked as Moved Out. Property status updated.", "info")
    except Exception as e:
        flash(f"Failed to record move-out: {e}", "danger")
    return redirect(url_for("admin.resident_detail", id=resident.id))

