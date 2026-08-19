<<<<<<< HEAD
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from app.models import ExpenseVoucher, AccountLedger, User, Role, Resident, db
from app.services.accounting_service import AccountingService
from app.services.billing_service import BillingService
from app.services.tenant_service import TenantService
=======
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import ExpenseVoucher, AccountLedger
from app.services.accounting_service import AccountingService
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


<<<<<<< HEAD
@accounting_bp.before_request
def admin_only_guard():
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("admin.admin_login"))
    user = db.session.get(User, user_id)
    if (
        not user
        or user.account_status != "ACTIVE"
        or user.role not in [Role.SUPER_ADMIN, Role.SOCIETY_ADMIN]
    ):
        abort(403, description="Admin access required")
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)



@accounting_bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)
    user_id = user.id
=======
@accounting_bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    society_id = session.get("society_id")
    user_id = session.get("user_id")
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    if request.method == "POST":
        category = request.form.get("category")
        amount = float(request.form.get("amount"))
        payee = request.form.get("payee_name")
        description = request.form.get("description")
        invoice_num = request.form.get("invoice_number")

        v = AccountingService.create_expense_voucher(
            society_id=society_id,
            category=category,
            amount=amount,
            payee_name=payee,
            description=description,
            invoice_number=invoice_num,
            user_id=user_id,
        )
        flash(
            f"Expense Voucher {v.voucher_number} approved & posted to Ledger!",
            "success",
        )
        return redirect(url_for("accounting.vouchers"))

    vouchers_list = (
        ExpenseVoucher.query.filter_by(society_id=society_id)
        .order_by(ExpenseVoucher.expense_date.desc())
        .all()
    )
    fin_summary = AccountingService.get_financial_summary(society_id)
    return render_template(
        "accounting/vouchers.html", vouchers=vouchers_list, summary=fin_summary
    )


@accounting_bp.route("/ledger")
def ledger():
<<<<<<< HEAD
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    entries = (
        AccountLedger.query.filter_by(society_id=society_id)
        .order_by(AccountLedger.entry_date.desc(), AccountLedger.id.desc())
=======
    society_id = session.get("society_id")
    entries = (
        AccountLedger.query.filter_by(society_id=society_id)
        .order_by(AccountLedger.entry_date.desc())
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        .all()
    )
    fin_summary = AccountingService.get_financial_summary(society_id)
    return render_template(
        "accounting/ledger.html", entries=entries, summary=fin_summary
    )
<<<<<<< HEAD


@accounting_bp.route("/resident-ledger/<int:resident_id>")
def admin_resident_ledger(resident_id):
    """Admin view of a resident's ledger with strict tenant isolation check."""
    user = db.session.get(User, session.get("user_id"))
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    resident = Resident.query.filter_by(id=resident_id, society_id=society_id).first_or_404()
    ledger_data = BillingService.get_resident_ledger(
        resident_id=resident.id,
        society_id=society_id,
    )
    return render_template("accounting/resident_ledger.html", ledger_data=ledger_data, resident=resident)

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
