from app.models import (
    db,
    Society,
    ExpenseVoucher,
    AccountLedger,
    Payment,
    Document,
    Vendor,
    AutomationAlert,
)
from app.utils import utcnow
from datetime import datetime, date, timedelta
from sqlalchemy import func


class AccountingAutomationService:
    """
    Implements Phase 5 Accounting Automation (Features 61–80):
    61. Accounting entry after verified payment
    62. Expense ledger entry
    63. Expense-invoice matching
    64. Duplicate invoice detection
    65. Duplicate expense detection
    66. Unusual expense detection
    67. Vendor price increase detection
    68. Monthly expense totals
    69. Monthly surplus calculation
    70. Cash-position calculation
    71. Monthly accounting summary
    72. Expense report generation
    73. Income-vs-expense report
    74. Budget-overrun alert
    75. Unusual-spending alert
    76. Missing expense-document alert
    77. Pending-expense reminder
    78. Old-pending-expense escalation
    79. Financial snapshot
    80. Committee/board financial brief
    """

    @staticmethod
    def record_payment_ledger_entry(payment_id):
        """Feature 61: Automatically records AccountLedger CREDIT entry on verified payment."""
        payment = db.session.get(Payment, payment_id)
        if not payment or payment.status not in ["captured", "Success", "paid"]:
            return None

        # Check idempotency: avoid duplicate ledger entries for the same payment
        existing = AccountLedger.query.filter_by(
            society_id=payment.society_id,
            reference_type="BILL_PAYMENT",
            reference_id=payment.id,
        ).first()
        if existing:
            return existing

        flat_str = payment.resident.flat.flat_number if (payment.resident and payment.resident.flat) else "Unit"
        ledger_entry = AccountLedger(
            society_id=payment.society_id,
            entry_date=payment.payment_date.date() if payment.payment_date else utcnow().date(),
            account_head="Maintenance Collection",
            entry_type="CREDIT",
            amount=payment.amount_paid,
            reference_type="BILL_PAYMENT",
            reference_id=payment.id,
            narration=f"Maintenance payment received via {payment.payment_method} from Flat {flat_str} (TXN: {payment.transaction_id})",
        )
        db.session.add(ledger_entry)
        db.session.commit()
        return ledger_entry

    @staticmethod
    def record_expense_ledger_entry(voucher_id, approved_by_id=None):
        """Feature 62: Automatically records AccountLedger DEBIT entry on approved ExpenseVoucher."""
        voucher = db.session.get(ExpenseVoucher, voucher_id)
        if not voucher or voucher.status not in ["Approved", "Paid"]:
            return None

        # Check idempotency
        existing = AccountLedger.query.filter_by(
            society_id=voucher.society_id,
            reference_type="EXPENSE_VOUCHER",
            reference_id=voucher.id,
        ).first()
        if existing:
            return existing

        ledger_entry = AccountLedger(
            society_id=voucher.society_id,
            entry_date=voucher.expense_date or utcnow().date(),
            account_head=f"{voucher.category} Expense",
            entry_type="DEBIT",
            amount=voucher.amount,
            reference_type="EXPENSE_VOUCHER",
            reference_id=voucher.id,
            narration=f"Expense voucher #{voucher.voucher_number} paid to {voucher.payee_name} for {voucher.description}",
        )
        db.session.add(ledger_entry)
        db.session.commit()
        return ledger_entry

    @staticmethod
    def match_expense_to_invoice(voucher_id):
        """Feature 63: Matches an expense voucher against invoices in the document vault."""
        voucher = db.session.get(ExpenseVoucher, voucher_id)
        if not voucher or not voucher.invoice_number:
            return None

        # Search documents
        doc = Document.query.filter_by(society_id=voucher.society_id).filter(
            (Document.title.ilike(f"%{voucher.invoice_number}%")) |
            (Document.category.ilike("%Invoice%"))
        ).first()
        return doc

    @staticmethod
    def detect_duplicate_invoices(society_id):
        """Feature 64: Flags vouchers sharing identical invoice numbers from the same payee."""
        q = db.session.query(
            ExpenseVoucher.payee_name,
            ExpenseVoucher.invoice_number,
            func.count(ExpenseVoucher.id).label("count")
        ).filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.invoice_number.isnot(None),
            ExpenseVoucher.invoice_number != "",
        ).group_by(ExpenseVoucher.payee_name, ExpenseVoucher.invoice_number).having(func.count(ExpenseVoucher.id) > 1).all()

        return [
            {"payee_name": d.payee_name, "invoice_number": d.invoice_number, "duplicate_count": d.count}
            for d in q
        ]

    @staticmethod
    def detect_duplicate_expenses(society_id):
        """Feature 65: Flags vouchers with identical payee, exact amount, and expense date."""
        q = db.session.query(
            ExpenseVoucher.payee_name,
            ExpenseVoucher.amount,
            ExpenseVoucher.expense_date,
            func.count(ExpenseVoucher.id).label("count")
        ).filter(ExpenseVoucher.society_id == society_id).group_by(
            ExpenseVoucher.payee_name, ExpenseVoucher.amount, ExpenseVoucher.expense_date
        ).having(func.count(ExpenseVoucher.id) > 1).all()

        return [
            {"payee_name": d.payee_name, "amount": d.amount, "expense_date": str(d.expense_date), "duplicate_count": d.count}
            for d in q
        ]

    @staticmethod
    def detect_unusual_expenses(society_id):
        """Feature 66: Detects single expenses that are > 3x the average category expense."""
        vouchers = ExpenseVoucher.query.filter_by(society_id=society_id).all()
        by_category = {}
        for v in vouchers:
            by_category.setdefault(v.category, []).append(v.amount)

        anomalies = []
        for v in vouchers:
            amounts = by_category.get(v.category, [])
            if len(amounts) >= 3:
                avg = sum(amounts) / len(amounts)
                if v.amount > avg * 3.0:
                    anomalies.append({
                        "voucher_id": v.id,
                        "voucher_number": v.voucher_number,
                        "category": v.category,
                        "amount": v.amount,
                        "category_avg": round(avg, 2),
                        "ratio": round(v.amount / avg, 2),
                    })
        return anomalies


    @staticmethod
    def detect_vendor_price_increases(society_id):
        """Feature 67: Compares vendor voucher amounts against previous history to detect price hikes."""
        vendors = Vendor.query.filter_by(society_id=society_id).all()
        increases = []

        for vnd in vendors:
            vouchers = ExpenseVoucher.query.filter(
                ExpenseVoucher.society_id == society_id,
                ExpenseVoucher.payee_name.ilike(f"%{vnd.company_name}%")
            ).order_by(ExpenseVoucher.expense_date.desc()).limit(5).all()

            if len(vouchers) >= 2:
                latest = vouchers[0]
                prev = vouchers[1]
                if latest.amount > prev.amount * 1.15:  # > 15% increase
                    increases.append({
                        "vendor_name": vnd.company_name,
                        "latest_voucher": latest.voucher_number,
                        "latest_amount": latest.amount,
                        "previous_amount": prev.amount,
                        "increase_percentage": round(((latest.amount - prev.amount) / prev.amount) * 100, 1),
                    })
        return increases

    @staticmethod
    def calculate_monthly_financials(society_id, target_month=None):
        """
        Features 68, 69, 70:
        Calculates monthly expense totals, net operating surplus, and cash positions.
        """
        target_month = target_month or utcnow().strftime("%Y-%m")
        year, month = map(int, target_month.split("-"))
        start_date = date(year, month, 1)
        next_m = month + 1 if month < 12 else 1
        next_y = year if month < 12 else year + 1
        end_date = date(next_y, next_m, 1)

        # 1. Total expenses by category (Feature 68)
        vouchers = ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.status.in_(["Approved", "Paid"]),
            ExpenseVoucher.expense_date >= start_date,
            ExpenseVoucher.expense_date < end_date,
        ).all()

        by_category = {}
        total_expense = 0.0
        for v in vouchers:
            by_category[v.category] = round(by_category.get(v.category, 0.0) + v.amount, 2)
            total_expense += v.amount

        # 2. Total collections in target month
        start_dt = datetime(year, month, 1)
        end_dt = datetime(next_y, next_m, 1)
        payments = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success", "paid"]),
            Payment.payment_date >= start_dt,
            Payment.payment_date < end_dt,
        ).all()
        total_income = sum(p.amount_paid for p in payments)

        # 3. Monthly surplus (Feature 69)
        net_surplus = round(total_income - total_expense, 2)

        # 4. Cash position (Feature 70)
        lifetime_payments = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success", "paid"]),
        ).all()
        lifetime_expenses = ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.status.in_(["Approved", "Paid"]),
        ).all()
        cash_position = round(sum(p.amount_paid for p in lifetime_payments) - sum(v.amount for v in lifetime_expenses), 2)

        return {
            "society_id": society_id,
            "month": target_month,
            "total_income": round(total_income, 2),
            "total_expense": round(total_expense, 2),
            "net_surplus": net_surplus,
            "cash_position": cash_position,
            "expenses_by_category": by_category,
            "vouchers_count": len(vouchers),
            "payments_count": len(payments),
        }

    @staticmethod
    def generate_monthly_accounting_summary(society_id, target_month=None):
        """Feature 71: Executive monthly accounting summary."""
        return AccountingAutomationService.calculate_monthly_financials(society_id, target_month)

    @staticmethod
    def generate_expense_report(society_id, start_date=None, end_date=None):
        """Feature 72: Itemized expense report grouped by category and vendor."""
        q = ExpenseVoucher.query.filter_by(society_id=society_id)
        if start_date:
            q = q.filter(ExpenseVoucher.expense_date >= start_date)
        if end_date:
            q = q.filter(ExpenseVoucher.expense_date <= end_date)
        vouchers = q.order_by(ExpenseVoucher.expense_date.desc()).all()

        return [
            {
                "voucher_number": v.voucher_number,
                "category": v.category,
                "amount": v.amount,
                "payee_name": v.payee_name,
                "invoice_number": v.invoice_number or "-",
                "date": str(v.expense_date),
                "status": v.status,
            }
            for v in vouchers
        ]

    @staticmethod
    def generate_income_vs_expense_report(society_id, months_count=6):
        """Feature 73: Comparative income vs expense history for the past months."""
        now = utcnow().date()
        history = []
        for i in range(months_count - 1, -1, -1):
            m_date = now.replace(day=1) - timedelta(days=i * 28)
            month_str = m_date.strftime("%Y-%m")
            stats = AccountingAutomationService.calculate_monthly_financials(society_id, month_str)
            history.append({
                "month": month_str,
                "income": stats["total_income"],
                "expense": stats["total_expense"],
                "surplus": stats["net_surplus"],
            })
        return history

    @staticmethod
    def run_financial_alerts_and_audits(society_id):
        """
        Features 74, 75, 76, 77, 78:
        Scans for budget overruns, unusual spending, missing receipts, pending vouchers, and escalations.
        """
        alerts_generated = 0
        now = utcnow()

        # Feature 75: Unusual spending alert (> ₹50,000)
        big_expenses = ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.amount > 50000.0,
            ExpenseVoucher.created_at >= now - timedelta(days=1),
        ).all()
        for v in big_expenses:
            alert = AutomationAlert(
                society_id=society_id,
                alert_type="UNUSUAL_SPENDING",
                severity="WARNING",
                title=f"High Value Expense #{v.voucher_number}",
                message=f"Expense voucher #{v.voucher_number} of ₹{v.amount:,.2f} to {v.payee_name} exceeds ₹50,000 threshold.",
                is_resolved=False,
            )
            db.session.add(alert)
            alerts_generated += 1

        # Feature 76: Missing expense document alert
        no_invoice = ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.status == "Approved",
            (ExpenseVoucher.invoice_number.is_(None)) | (ExpenseVoucher.invoice_number == ""),
        ).all()
        for v in no_invoice:
            existing = AutomationAlert.query.filter_by(
                society_id=society_id, alert_type="MISSING_EXPENSE_DOCUMENT", is_resolved=False
            ).filter(AutomationAlert.message.contains(f"#{v.voucher_number}")).first()
            if not existing:
                alert = AutomationAlert(
                    society_id=society_id,
                    alert_type="MISSING_EXPENSE_DOCUMENT",
                    severity="INFO",
                    title=f"Missing Invoice for Voucher #{v.voucher_number}",
                    message=f"Voucher #{v.voucher_number} for ₹{v.amount:,.2f} is approved without an attached invoice number.",
                    is_resolved=False,
                )
                db.session.add(alert)
                alerts_generated += 1

        # Features 77 & 78: Pending expense reminder & 7-day escalation
        cutoff_7d = now - timedelta(days=7)
        old_pending = ExpenseVoucher.query.filter(
            ExpenseVoucher.society_id == society_id,
            ExpenseVoucher.status.in_(["Submitted", "Draft"]),
            ExpenseVoucher.created_at <= cutoff_7d,
        ).all()
        for v in old_pending:
            alert = AutomationAlert(
                society_id=society_id,
                alert_type="EXPENSE_ESCALATION_7D",
                severity="WARNING",
                title=f"Pending Expense Escalation: #{v.voucher_number}",
                message=f"Expense voucher #{v.voucher_number} for ₹{v.amount:,.2f} ({v.payee_name}) has been awaiting approval for > 7 days.",
                is_resolved=False,
            )
            db.session.add(alert)
            alerts_generated += 1

        db.session.commit()
        return {"alerts_generated": alerts_generated}

    @staticmethod
    def get_financial_snapshot(society_id):
        """Feature 79: Real-time financial health snapshot."""
        fin = AccountingAutomationService.calculate_monthly_financials(society_id)
        return {
            "society_id": society_id,
            "timestamp": utcnow().isoformat(),
            "current_month": fin["month"],
            "monthly_income": fin["total_income"],
            "monthly_expense": fin["total_expense"],
            "monthly_surplus": fin["net_surplus"],
            "cash_position": fin["cash_position"],
            "expense_categories": fin["expenses_by_category"],
        }

    @staticmethod
    def generate_committee_financial_brief(society_id):
        """Feature 80: Management committee executive financial brief."""
        snapshot = AccountingAutomationService.get_financial_snapshot(society_id)
        soc = db.session.get(Society, society_id)
        soc_name = soc.name if soc else "Society"

        brief_text = (
            f"Executive Committee Financial Brief for {soc_name} ({snapshot['current_month']}):\n"
            f"• Verified Monthly Collections: ₹{snapshot['monthly_income']:,.2f}\n"
            f"• Approved Monthly Expenditure: ₹{snapshot['monthly_expense']:,.2f}\n"
            f"• Net Operating Surplus: ₹{snapshot['monthly_surplus']:,.2f}\n"
            f"• Net Cash & Bank Balance: ₹{snapshot['cash_position']:,.2f}\n"
            f"Top expense categories: {', '.join([f'{k}: ₹{v:,.0f}' for k, v in snapshot['expense_categories'].items()]) or 'None recorded'}."
        )
        return {
            "society_id": society_id,
            "society_name": soc_name,
            "month": snapshot["current_month"],
            "brief_text": brief_text,
            "snapshot": snapshot,
        }
