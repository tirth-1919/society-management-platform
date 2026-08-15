import secrets
from datetime import date
from app.models import db, ExpenseVoucher, AccountLedger


class AccountingService:
    @staticmethod
    def create_expense_voucher(
        society_id,
        category,
        amount,
        payee_name,
        description,
        expense_date=None,
        invoice_number=None,
        user_id=None,
    ):
        """Creates an expense voucher and posts a DEBIT entry to the general ledger."""
        if not expense_date:
            expense_date = date.today()

        voucher_num = f"VCHR-{society_id}-{secrets.token_hex(4).upper()}"
        voucher = ExpenseVoucher(
            voucher_number=voucher_num,
            society_id=society_id,
            category=category,
            amount=amount,
            payee_name=payee_name,
            description=description,
            invoice_number=invoice_number,
            expense_date=expense_date,
            status="Approved",
            approved_by_id=user_id,
        )
        db.session.add(voucher)
        db.session.flush()

        # General Ledger DEBIT (Expense) entry
        ledger_entry = AccountLedger(
            society_id=society_id,
            entry_date=expense_date,
            account_head=f"{category} Expense",
            entry_type="DEBIT",
            amount=amount,
            reference_type="EXPENSE_VOUCHER",
            reference_id=voucher.id,
            narration=f"Expense Voucher {voucher_num}: {description} (Paid to {payee_name})",
        )
        db.session.add(ledger_entry)
        db.session.commit()
        return voucher

    @staticmethod
    def get_financial_summary(society_id):
        """Calculates income vs expense metrics for a society."""
        entries = AccountLedger.query.filter_by(society_id=society_id).all()
        total_income = sum(e.amount for e in entries if e.entry_type == "CREDIT")
        total_expense = sum(e.amount for e in entries if e.entry_type == "DEBIT")
        net_surplus = total_income - total_expense

        return {
            "total_income": total_income,
            "total_expense": total_expense,
            "net_surplus": net_surplus,
            "ledger_count": len(entries),
        }
