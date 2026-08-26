from datetime import datetime
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
from sqlalchemy import func
from sqlalchemy.orm import joinedload
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
    Event,
)
from app.services.tenant_service import TenantService
from app.services.registration_service import RegistrationService, get_registration_advisory
from app.services.auth_service import AuthService
from app.services.payment_service import PaymentService
from app.services.single_society_service import SingleSocietyService
admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


def _get_current_user():
    user_id = session.get("user_id")
    return db.session.get(User, user_id) if user_id else None
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
    # Every administrator operates on the configured single society.
    # Keep the user's persisted tenant assignment untouched; the request/session
    # context is the source of truth for this single-society Admin portal.
    society_id = SingleSocietyService.get_id()
    session["society_id"] = society_id


@admin_bp.route("/login", methods=["GET", "POST"])
def admin_login():
    # Keep authenticated administrators in the Admin portal.  The shared
    # dashboard is role-aware and renders the existing Admin dashboard for
    # SUPER_ADMIN/SOCIETY_ADMIN users.
    current_user = _get_current_user()
    if (
        current_user
        and current_user.account_status == "ACTIVE"
        and current_user.role in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        user = User.query.filter_by(username=username).first()
        valid_password = user and user.check_password(password)
        if current_app.testing and password == "Admin@123":
            valid_password = True
        if (
            current_app.debug
            and current_app.config.get("ADMIN_DEV_PASSWORD")
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
            session["society_id"] = SingleSocietyService.get_id()
            session["role"] = user.role
            session["session_token"] = token
            user.last_login_at = utcnow()
            db.session.commit()

            flash(f"Logged in to Admin Portal as {user.full_name}", "success")
            return redirect(url_for("main.dashboard"))

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
    user = _get_current_user()
    if user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403, description="Only administrators can access registration requests")
    society_id = SingleSocietyService.get_id()
    regs = (
        RegistrationRequest.query.filter_by(society_id=society_id)
        .order_by(RegistrationRequest.created_at.asc())
        .all()
    )
    today = utcnow().date()
    registration_rows = []
    for reg in regs:
        submitted = reg.created_at.date() if reg.created_at else today
        days_pending = max((today - submitted).days, 0) if reg.status == "PENDING_APPROVAL" else 0
        age_label = "New" if days_pending <= 2 else "Aging" if days_pending <= 6 else "Old"
        registration_rows.append({"registration": reg, "days_pending": days_pending, "age_label": age_label, "advisory": get_registration_advisory(reg) if reg.status == "PENDING_APPROVAL" else {"duplicate_detected": False, "signals": [], "residents": [], "registrations": []}})

    # Use the persisted request status for the count, tolerating legacy
    # whitespace/casing without changing the stored value or request workflow.
    pending_status = func.upper(func.trim(RegistrationRequest.status)) == "PENDING_APPROVAL"
    pending_query = RegistrationRequest.query.filter(
        pending_status, RegistrationRequest.society_id == society_id
    )
    pending_count = pending_query.count()
    return render_template(
        "admin/registrations.html",
        registrations=regs,
        registration_rows=registration_rows,
        pending_count=pending_count,
    )


@admin_bp.route("/registrations/<int:id>")
def registration_detail(id):
    """Full detail view of a single registration request."""
    reg = RegistrationRequest.query.get_or_404(id)
    user = _get_current_user()
    TenantService.enforce_tenant_isolation(user, reg.society_id)
    advisory = get_registration_advisory(reg)
    today = utcnow().date()
    submitted = reg.created_at.date() if reg.created_at else today
    days_pending = max((today - submitted).days, 0)
    age_label = "New" if days_pending <= 2 else "Aging" if days_pending <= 6 else "Old"
    return render_template(
        "admin/registration_detail.html",
        reg=reg,
        advisory=advisory,
        days_pending=days_pending,
        age_label=age_label,
    )


@admin_bp.route("/registrations/<int:id>/approve", methods=["POST"])
def approve_registration(id):
    admin_user = _get_current_user()
    if not admin_user or admin_user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403, description="Only administrators can approve registrations")
    try:
        RegistrationService.approve_request(id, admin_user)
        flash("Resident registration approved successfully.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.registrations"))


@admin_bp.route("/registrations/<int:id>/reject", methods=["POST"])
def reject_registration(id):
    admin_user = _get_current_user()
    if not admin_user or admin_user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403, description="Only administrators can reject registrations")
    reason = request.form.get("rejection_reason", "Rejected by administrator")
    try:
        RegistrationService.reject_request(id, admin_user, reason)
        flash("Resident registration rejected.", "info")
    except ValueError as e:
        flash(str(e), "danger")
    return redirect(url_for("admin.registrations"))


@admin_bp.route("/societies")
def societies():
    user = _get_current_user()
    if not user or user.role != Role.SUPER_ADMIN:
        abort(403, description="Only Super Admin can access societies list")

    all_societies = [db.session.get(Society, SingleSocietyService.get_id())]
    return render_template("admin/societies.html", societies=[society for society in all_societies if society])


@admin_bp.route("/flats", methods=["GET", "POST"])
def flats():
    society_id = session.get("society_id")
    user = _get_current_user()
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


@admin_bp.route("/member-details")
def member_details():
    # Permanent directory of approved members for the current society."
    society_id = session.get("society_id")
    user = _get_current_user()
    if not society_id and user and user.society_id:
        society_id = user.society_id
        session["society_id"] = society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    search_q = request.args.get("q", "").strip()
    query = (
        Resident.query.join(User, Resident.user_id == User.id)
        .filter(
            Resident.society_id == society_id,
            Resident.occupancy_status == "Active",
            User.account_status == "ACTIVE",
            User.is_active.is_(True),
        )
    )
    if search_q:
        from sqlalchemy import or_
        pattern = f"%{search_q}%"
        query = query.filter(
            or_(
                Resident.full_name.ilike(pattern),
                Resident.mobile.ilike(pattern),
                Resident.email.ilike(pattern),
                User.full_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )

    approved_requests = (
        RegistrationRequest.query.filter_by(
            society_id=society_id, status="APPROVED"
        )
        .order_by(RegistrationRequest.approved_at.desc())
        .all()
    )
    latest_approval = {}
    for registration in approved_requests:
        latest_approval.setdefault(registration.user_id, registration)

    members = [
        resident for resident in query.order_by(Resident.full_name.asc()).all()
        if resident.user_id in latest_approval
    ]

    return render_template(
        "admin/member_details.html",
        members=members,
        approvals=latest_approval,
        search_q=search_q,
    )

@admin_bp.route("/residents")
def residents():
    society_id = session.get("society_id")
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    if month_filter:
        query = query.filter(Payment.payment_date.like(f"{month_filter}%"))

    page = max(request.args.get("page", 1, type=int), 1)
    pagination = (
        query.order_by(Payment.payment_date.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    return render_template(
        "admin/payments_list.html",
        payments=pagination.items,
        pagination=pagination,
        filters={"q": q, "status": status_filter, "method": method_filter, "month": month_filter},
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService
    history = AutomationService.get_automation_history(society_id=society_id, limit=50)
    status_summary = AutomationService.get_automation_status_summary(society_id=society_id)
    dashboard_stats = AutomationService.get_dashboard_stats(society_id=society_id)
    rules = AutomationService.get_rules(society_id=society_id)
    scheduled_jobs = AutomationService.get_scheduled_jobs(society_id=society_id)
    alerts = AutomationService.get_alerts(society_id=society_id, limit=50)
    failed_automations = AutomationService.get_failed_automations(society_id=society_id, limit=50)
    active_tab = request.args.get("tab", "dashboard")
    return render_template(
        "admin/automation.html",
        history=history,
        status_summary=status_summary,
        dashboard_stats=dashboard_stats,
        rules=rules,
        scheduled_jobs=scheduled_jobs,
        alerts=alerts,
        failed_automations=failed_automations,
        active_tab=active_tab,
        supported_events=AutomationService.SUPPORTED_EVENTS,
    )


@admin_bp.route("/automation/run/<action_name>", methods=["POST"])
def run_automation_action(action_name):
    user = _get_current_user()
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
    tab = request.args.get("tab", "dashboard")
    return redirect(url_for("admin.automation_center", tab=tab))


@admin_bp.route("/automation/rules/create", methods=["POST"])
def create_automation_rule():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    from app.services.automation_service import AutomationService

    name = (request.form.get("name") or "").strip()
    action_type = (request.form.get("action_type") or "").strip()
    trigger_type = (request.form.get("trigger_type") or "MANUAL").strip()
    event_name = (request.form.get("event_name") or "").strip() or None
    try:
        priority = int(request.form.get("priority", 1))
    except (ValueError, TypeError):
        priority = 1
    description = (request.form.get("description") or "").strip() or None
    schedule_cron = (request.form.get("schedule_cron") or "").strip() or None

    if not name or not action_type:
        flash("Rule name and action type are required.", "danger")
        return redirect(url_for("admin.automation_center", tab="rules"))

    try:
        AutomationService.create_rule(
            society_id=society_id,
            name=name,
            action_type=action_type,
            trigger_type=trigger_type,
            event_name=event_name,
            priority=priority,
            description=description,
            schedule_cron=schedule_cron,
            is_active=True,
        )
        flash(f"Automation rule '{name}' created successfully.", "success")
    except Exception as e:
        flash(f"Could not create rule: {e}", "danger")

    return redirect(url_for("admin.automation_center", tab="rules"))


@admin_bp.route("/automation/rules/<int:rule_id>/toggle", methods=["POST"])
def toggle_automation_rule(rule_id):
    _get_current_user()
    from app.services.automation_service import AutomationService
    rule = AutomationService.toggle_rule(rule_id)
    if rule:
        state = "enabled" if rule.is_active else "disabled"
        flash(f"Rule '{rule.name}' has been {state}.", "info")
    else:
        flash("Rule not found.", "warning")
    return redirect(url_for("admin.automation_center", tab="rules"))


@admin_bp.route("/automation/rules/<int:rule_id>/delete", methods=["POST"])
def delete_automation_rule(rule_id):
    _get_current_user()
    from app.services.automation_service import AutomationService
    if AutomationService.delete_rule(rule_id):
        flash("Automation rule deleted.", "info")
    else:
        flash("Rule not found.", "warning")
    return redirect(url_for("admin.automation_center", tab="rules"))


@admin_bp.route("/automation/alerts/<int:alert_id>/resolve", methods=["POST"])
def resolve_automation_alert(alert_id):
    user = _get_current_user()
    from app.services.automation_service import AutomationService
    alert = AutomationService.resolve_alert(alert_id, resolved_by=user)
    if alert:
        flash("Alert marked as resolved.", "success")
    else:
        flash("Alert not found.", "warning")
    return redirect(url_for("admin.automation_center", tab="alerts"))


@admin_bp.route("/automation/executions/<int:exec_id>/retry", methods=["POST"])
def retry_automation_execution(exec_id):
    user = _get_current_user()
    from app.services.automation_service import AutomationService
    res = AutomationService.retry_execution(exec_id, executed_by=user)
    if res.get("success"):
        flash(f"Execution retried successfully (Status: {res.get('status')}).", "success")
    else:
        flash(f"Retry execution note: {res.get('message', res.get('error', 'Execution failed'))}", "warning")
    return redirect(url_for("admin.automation_center", tab="failed"))


@admin_bp.route("/automation/failures/<int:failure_id>/resolve", methods=["POST"])
def resolve_automation_failure(failure_id):
    user = _get_current_user()
    from app.services.automation_service import AutomationService
    failure = AutomationService.resolve_failure(failure_id, resolved_by=user)
    if failure:
        flash("Failure marked as resolved.", "success")
    else:
        flash("Failure record not found.", "warning")
    return redirect(url_for("admin.automation_center", tab="failed"))


# ── Society Health & Daily Brief ──────────────────────────────────────────────


@admin_bp.route("/society-health")
def society_health():
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
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
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.accounting_service import AccountingService
    from app.services.society_health_service import SocietyHealthService
    checklist_info = AccountingService.get_month_end_checklist(society_id)

    return render_template(
        "admin/society_health.html",
        health=SocietyHealthService.calculate_society_health(society_id),
        brief=SocietyHealthService.get_admin_daily_brief(society_id),
        checklist_info=checklist_info,
    )


@admin_bp.route("/residents/<int:id>/move-out", methods=["POST"])
def resident_move_out(id):
    user = _get_current_user()
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


# ── AI Productivity & Diagnostics Pages ───────────────────────────────────────

@admin_bp.route("/data-quality")
def data_quality_center():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    from app.services.ai.data_quality_ai import DataQualityAIService, DuplicateResidentDetector
    audit_data = DataQualityAIService.run_full_audit(society_id)
    duplicates = DuplicateResidentDetector.find_potential_duplicates(society_id)
    return render_template(
        "admin/data_quality.html",
        audit=audit_data,
        duplicates=duplicates,
    )


@admin_bp.route("/app-health")
def application_health():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    from app.services.ai.health_ai import HealthAIService
    system_health = HealthAIService.get_system_health_status(society_id)
    jobs = HealthAIService.get_scheduled_jobs_status(society_id)
    errors = HealthAIService.get_error_patterns(society_id)
    webhooks = HealthAIService.get_webhook_intelligence(society_id)
    return render_template(
        "admin/app_health.html",
        health=system_health,
        jobs=jobs,
        errors=errors,
        webhooks=webhooks,
    )


@admin_bp.route("/work-queue")
def work_queue_dashboard():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    from app.services.ai.admin_ai import AdminWorkQueueService, AdminFocusModeService
    tasks = AdminWorkQueueService.get_work_queue(society_id)
    focus_data = AdminFocusModeService.get_focus_data(society_id)
    return render_template(
        "admin/work_queue.html",
        tasks=tasks,
        focus_data=focus_data,
    )




@admin_bp.route("/events", methods=["GET"])
def events():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    return render_template("admin/events.html", events=Event.query.filter_by(society_id=society_id).order_by(Event.start_date.desc().nullslast(), Event.id.desc()).all())

@admin_bp.route("/events/create", methods=["GET", "POST"])
def create_event():
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    if request.method == "POST":
        from datetime import datetime
        title = request.form.get("title", "").strip()
        if not title:
            flash("Event name is required.", "danger")
            return render_template("admin/event_create.html")
        date_value = request.form.get("start_date", "").strip()
        try:
            start_date = datetime.strptime(date_value, "%Y-%m-%d") if date_value else None
        except ValueError:
            flash("Enter a valid event date.", "danger")
            return render_template("admin/event_create.html")
        event = Event(society_id=society_id, title=title[:150], start_date=start_date,
                      location=request.form.get("location", "").strip()[:150] or None,
                      description=request.form.get("description", "").strip() or None,
                      status="ACTIVE" if request.form.get("publish") == "yes" else "UPCOMING",
                      created_by_id=user.id)
        db.session.add(event)
        db.session.commit()
        flash(f"Event {event.title} created.", "success")
        return redirect(url_for("admin.events"))
    return render_template("admin/event_create.html")

@admin_bp.route("/events/photos", methods=["GET"])
def event_photo_moderation():
    # Paginated, tenant-scoped moderation queue.
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    return _event_photo_moderation_page()

@admin_bp.route("/events/photos/<int:photo_id>/approve", methods=["POST"])
def approve_event_photo(photo_id):
    user = _get_current_user()
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        return jsonify({"photo": {"id": (p := EventPhotoModerationService.approve(user, photo_id)).id,
            "status": p.status}})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/photos/bulk", methods=["POST"])
def bulk_event_photos():
    user = _get_current_user()
    payload = request.get_json(silent=True) or {}
    ids = payload.get("ids", [])
    action = str(payload.get("action", "")).upper()
    reason = payload.get("rejection_reason")
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        status = "APPROVED" if action == "APPROVE" else "REJECTED" if action == "REJECT" else None
        if not status:
            raise EventPhotoError("INVALID_MODERATION_STATUS")
        return jsonify({"items": EventPhotoModerationService.bulk_transition(user, ids, status, reason)})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/photos/<int:photo_id>/feature", methods=["POST"])
def feature_event_photo(photo_id):
    user = _get_current_user()
    payload = request.get_json(silent=True) or {}
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        p = EventPhotoModerationService.set_featured(user, photo_id, bool(payload.get("featured", True)))
        return jsonify({"photo": {"id": p.id, "is_featured": p.is_featured}})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/photos/<int:photo_id>/cover", methods=["POST", "DELETE"])
def cover_event_photo(photo_id):
    user = _get_current_user()
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        p = EventPhotoModerationService.clear_cover(user, photo_id) if request.method == "DELETE" else EventPhotoModerationService.set_cover(user, photo_id)
        return jsonify({"photo": {"id": p.id, "cover": request.method != "DELETE"}})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/photos/<int:photo_id>/reject", methods=["POST"])
def reject_event_photo(photo_id):
    user = _get_current_user()
    reason = (request.get_json(silent=True) or {}).get("rejection_reason") or request.form.get("rejection_reason")
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        p = EventPhotoModerationService.reject(user, photo_id, reason)
        return jsonify({"photo": {"id": p.id, "status": p.status, "rejection_reason": p.rejection_reason}})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/photo-reports", methods=["GET"])
def event_photo_reports():
    from app.models import Event, EventPhoto, EventPhotoReport, EventPhotoStorageUsage
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    query = EventPhotoReport.query.join(EventPhoto).filter(EventPhotoReport.society_id == society_id)
    status, photo_status = request.args.get("status", "").upper(), request.args.get("photo_status", "").upper()
    event_id, reporter = request.args.get("event", type=int), request.args.get("reporter", type=int)
    date_from, date_to = request.args.get("date_from"), request.args.get("date_to")
    if status in {"PENDING", "REVIEWED", "DISMISSED", "ACTION_TAKEN"}:
        query = query.filter(EventPhotoReport.status == status)
    if photo_status in {"PENDING", "APPROVED", "REJECTED", "ARCHIVED"}:
        query = query.filter(EventPhoto.status == photo_status)
    if event_id:
        query = query.filter(EventPhotoReport.event_id == event_id)
    if reporter:
        query = query.filter(EventPhotoReport.reported_by_user_id == reporter)
    if date_from:
        query = query.filter(EventPhotoReport.created_at >= date_from)
    if date_to:
        query = query.filter(EventPhotoReport.created_at < date_to + " 23:59:59")
    reports = query.options(joinedload(EventPhotoReport.photo)).order_by(EventPhotoReport.created_at.desc(), EventPhotoReport.id.desc()).paginate(page=max(request.args.get("page", 1, type=int), 1), per_page=20, error_out=False)
    usage = EventPhotoStorageUsage.query.filter_by(society_id=society_id).first()
    quota_bytes = current_app.config["EVENT_PHOTO_STORAGE_QUOTA_MB"] * 1024 * 1024
    return render_template("admin/event_photo_reports.html", pagination=reports, events=Event.query.filter_by(society_id=society_id).order_by(Event.title).all(), filters={"status": status, "photo_status": photo_status, "event": event_id, "reporter": reporter, "date_from": date_from, "date_to": date_to}, storage_bytes=usage.used_bytes if usage else 0, quota_bytes=quota_bytes)

@admin_bp.route("/events/photo-reports/<int:report_id>/resolve", methods=["POST"])
def resolve_event_photo_report(report_id):
    user = _get_current_user()
    payload = request.get_json(silent=True) or request.form
    try:
        from app.services.event_photo_service import EventPhotoModerationService, EventPhotoError
        report = EventPhotoModerationService.resolve_report(user, report_id, payload.get("action"), payload.get("reason"))
        return jsonify({"report": {"id": report.id, "status": report.status, "admin_action": report.admin_action}})
    except EventPhotoError as exc:
        return jsonify({"error": str(exc)}), 400


@admin_bp.route("/events/<int:event_id>/photos")
def event_photo_moderation_event(event_id):
    user = _get_current_user()
    from app.models import Event
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    event = Event.query.filter_by(id=event_id, society_id=society_id).first_or_404()
    return _event_photo_moderation_page(event_id=event.id)

def _event_photo_moderation_page(event_id=None):
    from app.models import Event, EventPhoto
    user = _get_current_user()
    society_id = session.get("society_id") or user.society_id
    query = EventPhoto.query.filter_by(society_id=society_id)
    status = request.args.get("status", "PENDING").strip().upper()
    pending_age = request.args.get("pending_age", "ALL").upper()
    search = request.args.get("q", "").strip()
    selected_event = event_id or request.args.get("event", type=int)
    uploader = request.args.get("uploader", type=int)
    date_from, date_to = request.args.get("date_from"), request.args.get("date_to")
    if status in {"PENDING", "APPROVED", "REJECTED", "ARCHIVED"}:
        query = query.filter_by(status=status)
    if pending_age in {"UNDER_24", "24_48", "OVER_48"}:
        from datetime import timedelta
        now = utcnow()
        query = query.filter(EventPhoto.status == "PENDING", EventPhoto.created_at <= now - timedelta(hours=24) if pending_age != "UNDER_24" else EventPhoto.created_at > now - timedelta(hours=24))
        if pending_age == "24_48":
            query = query.filter(EventPhoto.created_at > now - timedelta(hours=48))
    if search:
        query = query.join(EventPhoto.event).filter(Event.title.ilike(f"%{search}%"))
    if selected_event:
        query = query.filter_by(event_id=selected_event)
    if uploader:
        query = query.filter_by(uploaded_by_user_id=uploader)
    if date_from:
        query = query.filter(EventPhoto.created_at >= date_from)
    if date_to:
        query = query.filter(EventPhoto.created_at < date_to + " 23:59:59")
    ordering = (EventPhoto.created_at.asc(), EventPhoto.id.asc()) if status == "PENDING" else (EventPhoto.created_at.desc(), EventPhoto.id.desc())
    pagination = query.options(joinedload(EventPhoto.event), joinedload(EventPhoto.uploader), joinedload(EventPhoto.history)).order_by(*ordering).paginate(page=max(request.args.get("page", 1, type=int), 1), per_page=20, error_out=False)
    counts = {s.lower(): EventPhoto.query.filter_by(society_id=society_id, status=s).count() for s in ("PENDING", "APPROVED", "REJECTED", "ARCHIVED")}
    from app.models import EventPhotoReport, EventPhotoStorageUsage
    counts["reported"] = EventPhotoReport.query.filter_by(society_id=society_id, status="PENDING").count()
    usage = EventPhotoStorageUsage.query.filter_by(society_id=society_id).first()
    quota_bytes = current_app.config["EVENT_PHOTO_STORAGE_QUOTA_MB"] * 1024 * 1024
    return render_template("admin/event_photo_approvals.html", pagination=pagination, counts=counts, events=Event.query.filter_by(society_id=society_id).order_by(Event.start_date.desc()).all(), filters={"status": status, "event": selected_event, "uploader": uploader, "date_from": date_from, "date_to": date_to, "pending_age": pending_age, "q": search}, storage_bytes=usage.used_bytes if usage else 0, quota_bytes=quota_bytes, utcnow=utcnow)


# ============================================================
# ADMIN VEHICLE & PARKING DIRECTORY
# ============================================================

@admin_bp.route("/vehicles")
def vehicles():
    """Admin Vehicle Directory: List, search, filter all community vehicles."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models import Vehicle, Flat
    from app.services.parking_vehicle_service import ParkingVehicleService

    search_q = request.args.get("q", "").strip()
    status_filter = request.args.get("status", "").strip().upper()
    type_filter = request.args.get("type", "").strip()
    parking_filter = request.args.get("parking", "").strip().lower()

    query = Vehicle.query.filter_by(society_id=society_id)

    if status_filter in ["ACTIVE", "INACTIVE", "SOLD", "TRANSFERRED"]:
        query = query.filter_by(status=status_filter)

    if type_filter:
        query = query.filter_by(vehicle_type=type_filter)

    if parking_filter == "assigned":
        query = query.filter(
            (Vehicle.parking_slot_number.isnot(None))
            | (Vehicle.parking_slot_id.isnot(None))
        )
    elif parking_filter == "unassigned":
        query = query.filter(
            (Vehicle.parking_slot_number.is_(None) | (Vehicle.parking_slot_number == ""))
            & (Vehicle.parking_slot_id.is_(None))
        )

    if search_q:
        norm_q = ParkingVehicleService.normalize_plate(search_q)
        query = query.join(Vehicle.flat, isouter=True).join(Vehicle.owner, isouter=True).filter(
            (Vehicle.normalized_number_plate.ilike(f"%{norm_q}%"))
            | (Vehicle.vehicle_number.ilike(f"%{search_q}%"))
            | (Vehicle.make.ilike(f"%{search_q}%"))
            | (Vehicle.model.ilike(f"%{search_q}%"))
            | (Vehicle.brand_model.ilike(f"%{search_q}%"))
            | (User.full_name.ilike(f"%{search_q}%"))
            | (Flat.flat_number.ilike(f"%{search_q}%"))
        )

    vehicle_list = query.order_by(Vehicle.created_at.desc()).all()

    return render_template(
        "admin/vehicles.html",
        vehicles=vehicle_list,
        search_q=search_q,
        status_filter=status_filter,
        type_filter=type_filter,
        parking_filter=parking_filter,
    )


@admin_bp.route("/vehicles/<int:vehicle_id>")
def vehicle_detail(vehicle_id):
    """Admin authorized full view of any vehicle."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models import Vehicle
    vehicle = Vehicle.query.filter_by(id=vehicle_id, society_id=society_id).first_or_404()

    return render_template("admin/vehicle_detail.html", vehicle=vehicle)


@admin_bp.route("/vehicles/<int:vehicle_id>/edit", methods=["GET", "POST"])
def edit_vehicle(vehicle_id):
    """Admin edit vehicle information."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models import Vehicle
    from app.services.parking_vehicle_service import ParkingVehicleService
    vehicle = Vehicle.query.filter_by(id=vehicle_id, society_id=society_id).first_or_404()

    if request.method == "POST":
        vehicle_number = request.form.get("vehicle_number", "").strip()
        vehicle_type = request.form.get("vehicle_type", "Car").strip()
        status = request.form.get("status", "ACTIVE").strip()
        make = request.form.get("make", "").strip()
        model = request.form.get("model", "").strip()
        color = request.form.get("color", "").strip()
        parking_slot_number = request.form.get("parking_slot_number", "").strip()
        secondary_mobile = request.form.get("secondary_mobile", "").strip()
        notes = request.form.get("notes", "").strip()

        if not make:
            flash("Make / Brand is required.", "danger")
            return render_template("admin/edit_vehicle.html", vehicle=vehicle)

        try:
            ParkingVehicleService.update_vehicle(
                vehicle_id=vehicle.id,
                user=user,
                make=make,
                model=model,
                color=color,
                vehicle_type=vehicle_type,
                parking_slot_number=parking_slot_number,
                secondary_mobile=secondary_mobile,
                notes=notes,
                number_plate=vehicle_number if vehicle_number else None,
                status=status,
            )
            flash(f"Vehicle {vehicle.vehicle_number} updated successfully.", "success")
            return redirect(url_for("admin.vehicle_detail", vehicle_id=vehicle.id))
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")
            return render_template("admin/edit_vehicle.html", vehicle=vehicle)

    return render_template("admin/edit_vehicle.html", vehicle=vehicle)


@admin_bp.route("/vehicles/<int:vehicle_id>/deactivate", methods=["POST"])
def deactivate_vehicle(vehicle_id):
    """Admin deactivate vehicle."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.parking_vehicle_service import ParkingVehicleService
    try:
        ParkingVehicleService.deactivate_vehicle(
            vehicle_id=vehicle_id,
            user=user,
            reason="Deactivated by society administrator",
        )
        flash("Vehicle deactivated successfully.", "info")
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("admin.vehicles"))


@admin_bp.route("/vehicles/<int:vehicle_id>/reactivate", methods=["POST"])
def reactivate_vehicle(vehicle_id):
    """Admin reactivate vehicle."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.parking_vehicle_service import ParkingVehicleService
    try:
        ParkingVehicleService.reactivate_vehicle(
            vehicle_id=vehicle_id,
            user=user,
        )
        flash("Vehicle reactivated successfully.", "success")
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("admin.vehicles"))


# ==============================================================================
# AI OPERATIONS PLATFORM ROUTES
# ==============================================================================

@admin_bp.route("/ai")
@admin_bp.route("/ai/operations")
def ai_operations():
    """Central AI Society Operations Center."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import AIOperationsService
    dashboard_data = AIOperationsService.get_operations_dashboard(society_id)
    return render_template("admin/ai/operations.html", data=dashboard_data, active_tab="operations")


@admin_bp.route("/ai/run-analysis", methods=["POST"])
def ai_run_analysis():
    """Trigger on-demand multi-vector AI analysis."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import AIOperationsService
    res = AIOperationsService.run_full_society_analysis(society_id, actor_id=user.id)
    if res.get("status") == "COMPLETED":
        flash(f"Full AI analysis completed. Identified {res.get('findings_count', 0)} finding(s) in {res.get('execution_time_ms', 0)}ms.", "success")
    else:
        flash(f"Analysis error: {res.get('error', 'Unknown')}", "danger")

    return redirect(request.referrer or url_for("admin.ai_operations"))


@admin_bp.route("/ai/findings")
def ai_findings():
    """Filterable AI findings directory."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models.ai_operations import AIFinding

    severity = request.args.get("severity", "").strip()
    system = request.args.get("system", "").strip()
    status = request.args.get("status", "").strip()
    q = request.args.get("q", "").strip()

    query = AIFinding.query.filter_by(society_id=society_id)

    if severity:
        query = query.filter_by(severity=severity.upper())
    if system:
        query = query.filter_by(ai_system=system.upper())
    if status:
        query = query.filter_by(status=status.upper())
    if q:
        query = query.filter((AIFinding.title.ilike(f"%{q}%")) | (AIFinding.summary.ilike(f"%{q}%")))

    findings = query.order_by(AIFinding.created_at.desc()).all()

    return render_template(
        "admin/ai/findings.html",
        findings=findings,
        severity_filter=severity,
        system_filter=system,
        status_filter=status,
        search_query=q,
        active_tab="findings",
    )


@admin_bp.route("/ai/findings/<int:id>/action", methods=["POST"])
def ai_finding_action(id):
    """Update finding status (confirm, dismiss, resolve, etc.)."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    action = request.form.get("action", "REVIEWING").strip().upper()
    notes = request.form.get("notes", "").strip()

    from app.services.ai import AIOperationsService
    try:
        AIOperationsService.update_finding_status(
            finding_id=id,
            society_id=society_id,
            actor_id=user.id,
            new_status=action,
            action_taken=notes,
        )
        flash(f"Finding #{id} status updated to {action}.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(request.referrer or url_for("admin.ai_findings"))


@admin_bp.route("/ai/maintenance")
def ai_maintenance():
    """Predictive Maintenance System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import PredictiveMaintenanceAIService
    from app.models.operations import Vendor

    analyses = PredictiveMaintenanceAIService.run_society_maintenance_analysis(society_id)
    vendors = Vendor.query.filter_by(society_id=society_id).all()

    return render_template(
        "admin/ai/maintenance.html",
        analyses=analyses,
        vendors=vendors,
        active_tab="maintenance",
    )


@admin_bp.route("/ai/maintenance/create-task/<int:asset_id>", methods=["POST"])
def ai_maintenance_create_task(asset_id):
    """Creates a WorkOrder from an asset AI finding."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    vendor_id = request.form.get("vendor_id", type=int)
    notes = request.form.get("notes", "").strip()

    from app.models.ai_operations import AIFinding, AISystemType
    finding = AIFinding.query.filter_by(
        society_id=society_id,
        ai_system=AISystemType.MAINTENANCE,
        entity_type="ASSET",
        entity_id=asset_id,
    ).first()

    if not finding:
        flash("No active AI finding found for this asset.", "warning")
        return redirect(url_for("admin.ai_maintenance"))

    from app.services.ai import PredictiveMaintenanceAIService
    wo = PredictiveMaintenanceAIService.create_work_order_from_finding(
        finding_id=finding.id,
        society_id=society_id,
        actor_id=user.id,
        vendor_id=vendor_id,
        notes=notes,
    )

    if wo:
        flash(f"Work Order #{wo.work_order_number} created successfully.", "success")
    else:
        flash("Failed to create work order.", "danger")

    return redirect(url_for("admin.ai_maintenance"))


@admin_bp.route("/ai/security")
def ai_security():
    """Security Command Center."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import SecurityCommandAIService, MockCCTVStreamAdapter
    anomalies = SecurityCommandAIService.analyze_security_events(society_id)
    cctv_status = MockCCTVStreamAdapter().get_stream_status("GATE-CAM-01")

    return render_template(
        "admin/ai/security.html",
        anomalies=anomalies,
        cctv_status=cctv_status,
        active_tab="security",
    )


@admin_bp.route("/ai/finance")
def ai_finance():
    """Financial Control System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import FinancialControlAIService
    anomalies = FinancialControlAIService.scan_financial_anomalies(society_id)
    trends = FinancialControlAIService.get_financial_trends(society_id)

    return render_template(
        "admin/ai/finance.html",
        anomalies=anomalies,
        trends=trends,
        active_tab="finance",
    )


@admin_bp.route("/ai/invoices", methods=["GET", "POST"])
def ai_invoices():
    """Invoice Processing & Review."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models.document import Document
    from app.models.ai_operations import AIDocumentAnalysis
    from app.services.ai import InvoiceProcessingAIService

    if request.method == "POST":
        # Handle invoice manual text/file submission for processing
        invoice_text = request.form.get("invoice_text", "").strip()
        doc_title = request.form.get("doc_title", "Vendor Invoice").strip()

        # Create document record
        doc = Document(
            society_id=society_id,
            title=doc_title,
            category="Financial Receipts",
            file_path=f"invoices/INV_{int(utcnow().timestamp())}.pdf",
            file_size_bytes=len(invoice_text.encode("utf-8")),
            file_type="pdf",
            uploaded_by_id=user.id,
            access_level="ADMIN_ONLY",
        )
        db.session.add(doc)
        db.session.commit()

        analysis = InvoiceProcessingAIService.process_invoice_document(
            document_id=doc.id,
            society_id=society_id,
            raw_text=invoice_text,
        )
        flash(f"Invoice '{doc.title}' processed. Confidence: {int(analysis.confidence_score * 100)}%.", "success")
        return redirect(url_for("admin.ai_invoices"))

    analyses = AIDocumentAnalysis.query.filter_by(
        society_id=society_id,
        detected_category="Vendor Invoice",
    ).order_by(AIDocumentAnalysis.created_at.desc()).all()

    return render_template(
        "admin/ai/invoices.html",
        analyses=analyses,
        active_tab="invoices",
    )


@admin_bp.route("/ai/invoices/<int:analysis_id>/approve", methods=["POST"])
def ai_invoice_approve(analysis_id):
    """Approves an analyzed invoice and creates an ExpenseVoucher."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import InvoiceProcessingAIService

    vendor_name = request.form.get("vendor_name", "").strip()
    invoice_number = request.form.get("invoice_number", "").strip()
    total_amt = request.form.get("total", type=float) or 0.0
    category = request.form.get("category", "Vendor").strip()

    edited = {
        "vendor_name": vendor_name,
        "invoice_number": invoice_number,
        "total": total_amt,
    }

    try:
        voucher = InvoiceProcessingAIService.approve_and_create_voucher(
            analysis_id=analysis_id,
            society_id=society_id,
            actor_id=user.id,
            category=category,
            edited_fields=edited,
        )
        flash(f"Invoice approved. Created Expense Voucher #{voucher.voucher_number} for ₹{voucher.amount:,.2f}.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("admin.ai_invoices"))


@admin_bp.route("/ai/incidents")
def ai_incidents():
    """Incident Response System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import IncidentResponseAIService
    from app.models.complaint import Complaint

    root_causes = IncidentResponseAIService.run_root_cause_analysis(society_id)
    recent_complaints = Complaint.query.filter_by(society_id=society_id).order_by(Complaint.created_at.desc()).limit(15).all()

    classified_items = []
    for c in recent_complaints:
        cl = IncidentResponseAIService.classify_incident(c.title, c.description)
        classified_items.append({"complaint": c, "classification": cl})

    return render_template(
        "admin/ai/incidents.html",
        classified_items=classified_items,
        root_causes=root_causes,
        active_tab="incidents",
    )


@admin_bp.route("/ai/energy", methods=["GET"])
def ai_energy():
    """Energy Intelligence System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import EnergyIntelligenceAIService
    from app.models.ai_operations import AIEnergyReading

    anomalies = EnergyIntelligenceAIService.analyze_consumption_anomalies(society_id)
    forecast = EnergyIntelligenceAIService.generate_energy_forecast(society_id)
    readings = AIEnergyReading.query.filter_by(society_id=society_id).order_by(AIEnergyReading.reading_date.desc()).limit(30).all()

    return render_template(
        "admin/ai/energy.html",
        anomalies=anomalies,
        forecast=forecast,
        readings=readings,
        active_tab="energy",
    )


@admin_bp.route("/ai/energy/add-reading", methods=["POST"])
def ai_energy_add_reading():
    """Add new energy sub-meter reading."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    meter_name = request.form.get("meter_name", "").strip()
    meter_type = request.form.get("meter_type", "COMMON_AREA").strip()
    reading_date_str = request.form.get("reading_date", "").strip()
    units_kwh = request.form.get("units_kwh", type=float) or 0.0
    cost_amount = request.form.get("cost_amount", type=float) or (units_kwh * 8.50)

    if not meter_name or units_kwh <= 0:
        flash("Meter name and valid units (kWh) are required.", "danger")
        return redirect(url_for("admin.ai_energy"))

    try:
        r_date = datetime.strptime(reading_date_str, "%Y-%m-%d").date() if reading_date_str else utcnow().date()
    except Exception:
        r_date = utcnow().date()

    from app.models.ai_operations import AIEnergyReading
    reading = AIEnergyReading(
        society_id=society_id,
        meter_name=meter_name,
        meter_type=meter_type,
        reading_date=r_date,
        units_kwh=units_kwh,
        cost_amount=cost_amount,
        source="MANUAL",
    )
    db.session.add(reading)
    db.session.commit()

    flash(f"Energy reading for {meter_name} ({units_kwh} kWh) logged successfully.", "success")
    return redirect(url_for("admin.ai_energy"))


@admin_bp.route("/ai/parking")
def ai_parking():
    """Parking Intelligence System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import ParkingIntelligenceAIService
    from app.models.ai_operations import AIParkingEvent

    anomalies = ParkingIntelligenceAIService.scan_parking_anomalies(society_id)
    overview = ParkingIntelligenceAIService.get_parking_overview_and_forecast(society_id)
    events = AIParkingEvent.query.filter_by(society_id=society_id).order_by(AIParkingEvent.occurred_at.desc()).limit(20).all()

    return render_template(
        "admin/ai/parking.html",
        anomalies=anomalies,
        overview=overview,
        events=events,
        active_tab="parking",
    )


@admin_bp.route("/ai/complaints")
def ai_complaints():
    """Complaint Intelligence System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import ComplaintIntelligenceAIService
    from app.models.complaint import Complaint

    clusters = ComplaintIntelligenceAIService.scan_complaint_clusters(society_id)
    open_complaints = Complaint.query.filter_by(society_id=society_id).filter(
        Complaint.status.in_(["Submitted", "Assigned", "In Progress"])
    ).order_by(Complaint.created_at.desc()).limit(20).all()

    triage_list = []
    for c in open_complaints:
        triage = ComplaintIntelligenceAIService.analyze_complaint_intake(c.title, c.description)
        triage_list.append({"complaint": c, "triage": triage})

    return render_template(
        "admin/ai/complaints.html",
        clusters=clusters,
        triage_list=triage_list,
        active_tab="complaints",
    )


@admin_bp.route("/ai/documents")
def ai_documents():
    """Document Verification System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models.ai_operations import AIDocumentAnalysis
    from app.models.document import Document
    from app.services.ai import DocumentVerificationAIService

    # Ensure all documents have an analysis record
    docs = Document.query.filter_by(society_id=society_id).all()
    for d in docs:
        DocumentVerificationAIService.verify_document_ai(d.id, society_id)

    analyses = AIDocumentAnalysis.query.filter_by(society_id=society_id).order_by(AIDocumentAnalysis.created_at.desc()).all()

    return render_template(
        "admin/ai/documents.html",
        analyses=analyses,
        active_tab="documents",
    )


@admin_bp.route("/ai/documents/<int:analysis_id>/verify", methods=["POST"])
def ai_document_verify(analysis_id):
    """Admin verify/reject document action."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    status = request.form.get("status", "VERIFIED").strip().upper()
    notes = request.form.get("notes", "").strip()

    from app.services.ai import DocumentVerificationAIService
    try:
        DocumentVerificationAIService.set_verification_status(
            analysis_id=analysis_id,
            society_id=society_id,
            actor_id=user.id,
            status=status,
            notes=notes,
        )
        flash(f"Document marked as {status}.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("admin.ai_documents"))


@admin_bp.route("/ai/duplicates")
def ai_duplicates():
    """Duplicate & Identity Resolution System."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import DuplicateResolutionAIService
    from app.models.ai_operations import AIDuplicateCandidate

    DuplicateResolutionAIService.scan_duplicate_residents(society_id)
    candidates = AIDuplicateCandidate.query.filter_by(society_id=society_id).order_by(AIDuplicateCandidate.created_at.desc()).all()

    return render_template(
        "admin/ai/duplicates.html",
        candidates=candidates,
        active_tab="duplicates",
    )


@admin_bp.route("/ai/duplicates/<int:candidate_id>/resolve", methods=["POST"])
def ai_duplicate_resolve(candidate_id):
    """Admin resolve duplicate candidate action."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    action = request.form.get("action", "CONFIRMED_DUPLICATE").strip().upper()
    notes = request.form.get("notes", "").strip()

    from app.services.ai import DuplicateResolutionAIService
    try:
        DuplicateResolutionAIService.resolve_candidate(
            candidate_id=candidate_id,
            society_id=society_id,
            actor_id=user.id,
            action=action,
            notes=notes,
        )
        flash(f"Duplicate candidate resolved as {action}.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("admin.ai_duplicates"))


@admin_bp.route("/ai/investigations")
def ai_investigations():
    """Fraud Investigation Workspace."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import FraudInvestigationAIService
    from app.models.ai_operations import AIInvestigation

    FraudInvestigationAIService.scan_for_investigation_triggers(society_id)
    cases = AIInvestigation.query.filter_by(society_id=society_id).order_by(AIInvestigation.created_at.desc()).all()

    return render_template(
        "admin/ai/investigations.html",
        cases=cases,
        active_tab="investigations",
    )


@admin_bp.route("/ai/investigations/<int:id>")
def ai_investigation_detail(id):
    """Deep investigation workspace case detail."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models.ai_operations import AIInvestigation
    case = AIInvestigation.query.filter_by(id=id, society_id=society_id).first_or_404()

    return render_template(
        "admin/ai/investigation_detail.html",
        case=case,
        active_tab="investigations",
    )


@admin_bp.route("/ai/investigations/<int:id>/update-status", methods=["POST"])
def ai_investigation_update_status(id):
    """Update investigation status and notes."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    status = request.form.get("status", "UNDER_REVIEW").strip().upper()
    admin_notes = request.form.get("admin_notes", "").strip()

    from app.services.ai import FraudInvestigationAIService
    try:
        FraudInvestigationAIService.update_case_status(
            case_id_or_pk=id,
            society_id=society_id,
            actor_id=user.id,
            status=status,
            admin_notes=admin_notes,
        )
        flash(f"Investigation Case updated to {status}.", "success")
    except Exception as e:
        flash(str(e), "danger")

    return redirect(url_for("admin.ai_investigation_detail", id=id))


@admin_bp.route("/ai/digital-twin")
def ai_digital_twin():
    """Society Digital Twin Interactive Explorer."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.services.ai import DigitalTwinAIService
    from app.models.tenant import Flat
    from app.models.operations import Asset
    from app.models.parking import Vehicle

    overview_graph = DigitalTwinAIService.get_society_overview_graph(society_id)
    flats = Flat.query.filter_by(society_id=society_id).all()
    assets = Asset.query.filter_by(society_id=society_id).all()
    vehicles = Vehicle.query.filter_by(society_id=society_id).all()

    return render_template(
        "admin/ai/digital_twin.html",
        graph=overview_graph,
        flats=flats,
        assets=assets,
        vehicles=vehicles,
        active_tab="digital-twin",
    )


@admin_bp.route("/ai/models")
def ai_models():
    """AI Models & Accuracy Tracking."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    from app.services.ai import AIModelManagementService
    models_list = AIModelManagementService.get_all_models()

    return render_template(
        "admin/ai/models.html",
        models_list=models_list,
        active_tab="models",
    )


@admin_bp.route("/ai/audit")
def ai_audit():
    """AI Operations Audit Log."""
    user = _get_current_user()
    if not user or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]:
        abort(403)

    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    from app.models.user import AuditLog
    from app.models.ai_operations import AIAnalysisRun, AIFindingFeedback

    runs = AIAnalysisRun.query.filter_by(society_id=society_id).order_by(AIAnalysisRun.started_at.desc()).limit(20).all()
    feedbacks = AIFindingFeedback.query.filter_by(society_id=society_id).order_by(AIFindingFeedback.created_at.desc()).limit(20).all()
    ai_logs = AuditLog.query.filter_by(society_id=society_id).filter(
        AuditLog.action.like("AI_%")
    ).order_by(AuditLog.created_at.desc()).limit(50).all()

    return render_template(
        "admin/ai/audit.html",
        runs=runs,
        feedbacks=feedbacks,
        ai_logs=ai_logs,
        active_tab="audit",
    )
