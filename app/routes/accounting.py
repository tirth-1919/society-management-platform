from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import ExpenseVoucher, AccountLedger
from app.services.accounting_service import AccountingService

accounting_bp = Blueprint("accounting", __name__, url_prefix="/accounting")


@accounting_bp.route("/vouchers", methods=["GET", "POST"])
def vouchers():
    society_id = session.get("society_id")
    user_id = session.get("user_id")

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
    society_id = session.get("society_id")
    entries = (
        AccountLedger.query.filter_by(society_id=society_id)
        .order_by(AccountLedger.entry_date.desc())
        .all()
    )
    fin_summary = AccountingService.get_financial_summary(society_id)
    return render_template(
        "accounting/ledger.html", entries=entries, summary=fin_summary
    )
