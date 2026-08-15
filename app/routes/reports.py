from flask import Blueprint, render_template, Response, session
from app.models import MaintenanceBill
from app.services.accounting_service import AccountingService
from app.services.import_export_service import ImportExportService

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")


@reports_bp.route("/financial")
def financial_reports():
    society_id = session.get("society_id")
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


@reports_bp.route("/export/residents")
def export_residents():
    society_id = session.get("society_id")
    csv_data = ImportExportService.export_residents_csv(society_id)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=residents_export.csv"},
    )
