from flask import Blueprint, render_template, Response, request, session, abort
from app.models import db, MaintenanceBill, User, Role, Building, Block, Payment
from app.services.accounting_service import AccountingService
from app.services.billing_service import BillingService
from app.services.import_export_service import ImportExportService
from app.services.tenant_service import TenantService

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.before_request
def admin_only_guard():
    user_id = session.get("user_id")
    if not user_id:
        abort(403, description="Authentication required")
    user = db.session.get(User, user_id)
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        abort(403, description="Admin access required")
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)


@reports_bp.route("/financial")
def financial_reports():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    fin_summary = AccountingService.get_financial_summary(society_id)
    bills = MaintenanceBill.query.filter_by(society_id=society_id).all()

    total_collected = sum(b.amount_paid for b in bills)
    total_pending = sum(b.remaining_amount for b in bills)

    return render_template(
        "reports/financial.html",
        summary=fin_summary,
        total_collected=total_collected,
        total_pending=total_pending,
    )


@reports_bp.route("/defaulters")
def defaulters_report():
    """Admin Defaulter Dashboard with filters."""
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    building_id = request.args.get("building_id", type=int)
    block_id = request.args.get("block_id", type=int)
    min_amount = request.args.get("min_amount", type=float)
    min_months = request.args.get("min_months", type=int)

    defaulters = BillingService.get_defaulters_list(
        society_id=society_id,
        building_id=building_id,
        block_id=block_id,
        min_amount=min_amount,
        min_months=min_months,
    )

    buildings = Building.query.filter_by(society_id=society_id).all()
    blocks = Block.query.filter_by(society_id=society_id).all()

    total_defaulters_amount = sum(d["total_outstanding"] for d in defaulters)
    total_defaulters_count = len(defaulters)

    # Aging analysis breakdown
    aging_30_count = sum(1 for d in defaulters if d["days_overdue"] <= 30)
    aging_30_amount = sum(d["total_outstanding"] for d in defaulters if d["days_overdue"] <= 30)
    aging_60_count = sum(1 for d in defaulters if 30 < d["days_overdue"] <= 60)
    aging_60_amount = sum(d["total_outstanding"] for d in defaulters if 30 < d["days_overdue"] <= 60)
    aging_90_count = sum(1 for d in defaulters if d["days_overdue"] > 60)
    aging_90_amount = sum(d["total_outstanding"] for d in defaulters if d["days_overdue"] > 60)

    aging_summary = BillingService.get_aging_buckets_summary(society_id)

    return render_template(
        "reports/defaulters.html",
        defaulters=defaulters,
        buildings=buildings,
        blocks=blocks,
        selected_building_id=building_id,
        selected_block_id=block_id,
        selected_min_amount=min_amount,
        selected_min_months=min_months,
        total_defaulters_amount=total_defaulters_amount,
        total_defaulters_count=total_defaulters_count,
        aging_30_count=aging_30_count,
        aging_30_amount=aging_30_amount,
        aging_60_count=aging_60_count,
        aging_60_amount=aging_60_amount,
        aging_90_count=aging_90_count,
        aging_90_amount=aging_90_amount,
        aging_summary=aging_summary,
    )


@reports_bp.route("/collections")
def collections_report():
    """Maintenance collection summary report."""
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    payments = (
        Payment.query.filter_by(society_id=society_id)
        .filter(Payment.status.in_(["captured", "Success"]))
        .order_by(Payment.payment_date.desc())
        .all()
    )

    total_collected = sum(p.amount_paid for p in payments)

    return render_template(
        "reports/collections.html",
        payments=payments,
        total_collected=total_collected,
    )


@reports_bp.route("/income-vs-expense")
def income_vs_expense_report():
    """Income vs Expense comparison by month."""
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    year = request.args.get("year", default=None, type=int)
    monthly_data = AccountingService.get_income_vs_expense_by_month(society_id, year=year)
    category_expenses = AccountingService.get_expense_breakdown_by_category(society_id)
    summary = AccountingService.get_financial_summary(society_id)

    return render_template(
        "reports/income_vs_expense.html",
        monthly_data=monthly_data,
        category_expenses=category_expenses,
        summary=summary,
        selected_year=year or 2026,
    )


@reports_bp.route("/export/defaulters")
def export_defaulters():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    building_id = request.args.get("building_id", type=int)
    block_id = request.args.get("block_id", type=int)
    min_amount = request.args.get("min_amount", type=float)
    min_months = request.args.get("min_months", type=int)

    csv_data = ImportExportService.export_defaulters_csv(
        society_id=society_id,
        building_id=building_id,
        block_id=block_id,
        min_amount=min_amount,
        min_months=min_months,
    )
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=defaulters_report.csv"},
    )


@reports_bp.route("/export/expenses")
def export_expenses():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    csv_data = ImportExportService.export_expenses_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=expenses_report.csv"},
    )


@reports_bp.route("/export/residents")
def export_residents():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    csv_data = ImportExportService.export_residents_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=residents_export.csv"},
    )


@reports_bp.route("/export/payments")
def export_payments():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    csv_data = ImportExportService.export_payments_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=payments_export.csv"},
    )


@reports_bp.route("/export/bills")
def export_bills():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    csv_data = ImportExportService.export_bills_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=bills_export.csv"},
    )


@reports_bp.route("/export/complaints")
def export_complaints():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    csv_data = ImportExportService.export_complaints_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=complaints_export.csv"},
    )


