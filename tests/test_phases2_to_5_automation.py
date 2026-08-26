import pytest
from datetime import timedelta
from app.models import (
    db,
    Society,
    Building,
    Block,
    Flat,
    User,
    Role,
    Resident,
    RegistrationRequest,
    MaintenanceBill,
    MaintenanceConfig,
    Payment,
    PaymentReceipt,
    RefundRequest,
    ExpenseVoucher,
    Vendor,
    Document,
    AutomationAlert,
    NotificationLog,
)
from app.services.resident_automation_service import ResidentAutomationService
from app.services.billing_automation_service import BillingAutomationService
from app.services.payment_automation_service import PaymentAutomationService
from app.services.accounting_automation_service import AccountingAutomationService
from app.services.registration_service import RegistrationService
from app.utils import utcnow


@pytest.fixture
def p25_env(app):
    """Creates an isolated environment for testing Phases 2, 3, 4, and 5."""
    with app.app_context():
        soc = Society(
            name="Sunrise Heights Automated Society",
            registration_number="AUT-PHASE-25",
            address="789 Automation Blvd",
            city="Ahmedabad",
            state="Gujarat",
            pincode="380015",
            email="contact@autosoc.com",
            phone="9876543300",
            emergency_contact="9876543399",
        )
        db.session.add(soc)
        db.session.commit()

        # Config
        config = MaintenanceConfig(
            society_id=soc.id,
            fixed_monthly_rate=1500.0,
            due_day_of_month=10,
            late_fee_per_month=500.0,
        )
        db.session.add(config)

        admin = User(
            username="admin_p25",
            full_name="Super Admin 25",
            email="admin@autosoc.com",
            mobile="9876543300",
            role=Role.SOCIETY_ADMIN,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
        )
        admin.set_password("Admin@123")

        resident_user = User(
            username="res_user_p25",
            full_name="Resident Automation User",
            email="resident25@autosoc.com",
            mobile="9876543301",
            role=Role.RESIDENT,
            society_id=soc.id,
            account_status="ACTIVE",
            is_active=True,
            maintenance_start_month=utcnow().strftime("%Y-%m"),
        )
        resident_user.set_password("Resident@123")

        db.session.add_all([admin, resident_user])
        db.session.commit()

        wing = Building(society_id=soc.id, name="Wing ALPHA")
        db.session.add(wing)
        db.session.commit()

        block = Block(society_id=soc.id, building_id=wing.id, name="Block 1")
        db.session.add(block)
        db.session.commit()

        flat = Flat(
            society_id=soc.id,
            building_id=wing.id,
            block_id=block.id,
            flat_number="101",
            floor_number=1,
            occupancy_status="Occupied",
        )
        db.session.add(flat)
        db.session.commit()

        resident = Resident(
            society_id=soc.id,
            flat_id=flat.id,
            user_id=resident_user.id,
            full_name="Resident Automation User",
            mobile="9876543301",
            email="resident25@autosoc.com",
            resident_type="Owner",
            occupancy_status="Active",
            is_primary=True,
            move_in_date=utcnow().date(),
        )
        db.session.add(resident)
        db.session.commit()

        return {
            "society_id": soc.id,
            "admin_id": admin.id,
            "resident_user_id": resident_user.id,
            "resident_id": resident.id,
            "flat_id": flat.id,
            "wing_id": wing.id,
            "block_id": block.id,
        }


def test_phase2_resident_automation_suite(app, p25_env):
    """
    Tests Features 1–20:
    - Auto-detect registration & task creation
    - 3-day and 7-day escalations
    - Incomplete data detection & request info
    - Post-approval onboarding sequence (Welcome, Checklist, Rules, Emergency, Payment, First-Bill)
    - Inactive resident account detection & reminders
    """
    with app.app_context():
        soc_id = p25_env["society_id"]
        admin = db.session.get(User, p25_env["admin_id"])
        wing_id = p25_env["wing_id"]
        block_id = p25_env["block_id"]

        # Feature 1 & 2: Registration Submission auto-detection & task creation
        flat2 = Flat(society_id=soc_id, building_id=wing_id, block_id=block_id, flat_number="202", floor_number=2, occupancy_status="Vacant")
        db.session.add(flat2)
        db.session.commit()

        req = RegistrationService.register_resident(
            full_name="New Test Resident",
            mobile="9876543388",
            email="newres@autosoc.com",
            society_id=soc_id,
            building_id=wing_id,
            block_id=block_id,
            flat_id=flat2.id,
            occupancy_type="OWNER",
            password="Password@123",
        )
        assert req.id is not None
        assert req.status == "PENDING_APPROVAL"

        # Check that an automation alert task was auto-created for admin
        reg_alert = AutomationAlert.query.filter_by(society_id=soc_id, alert_type="RESIDENT_REGISTRATION").first()
        assert reg_alert is not None
        assert "New Test Resident" in reg_alert.title

        # Features 3, 4, 5: Aging, 3-day & 7-day Escalation
        # Synthetic older registration (8 days ago)
        u_old = User(full_name="Old Applicant", mobile="9876543377", email="old@autosoc.com", role=Role.RESIDENT, society_id=soc_id)
        u_old.set_password("Temp@123")
        db.session.add(u_old)
        db.session.commit()

        flat3 = Flat(society_id=soc_id, building_id=wing_id, block_id=block_id, flat_number="303", floor_number=3, occupancy_status="Vacant")
        db.session.add(flat3)
        db.session.commit()

        req_old = RegistrationRequest(
            user_id=u_old.id,
            society_id=soc_id,
            building_id=wing_id,
            block_id=block_id,
            flat_id=flat3.id,
            full_name="Old Applicant",
            mobile="9876543377",
            email="old@autosoc.com",
            occupancy_type="TENANT",
            status="PENDING_APPROVAL",
            created_at=utcnow() - timedelta(days=8),
        )
        db.session.add(req_old)
        db.session.commit()

        esc_res = ResidentAutomationService.scan_and_escalate_pending_registrations(society_id=soc_id)
        assert esc_res["scanned"] >= 2
        assert esc_res["created"] >= 1  # 7-day critical alert created

        crit_alert = AutomationAlert.query.filter_by(society_id=soc_id, alert_type="REGISTRATION_ESCALATION_7D").first()
        assert crit_alert is not None
        assert crit_alert.severity == "CRITICAL"

        # Feature 6 & 7: Incomplete registration & request missing info
        incomplete_list = ResidentAutomationService.detect_incomplete_registrations(society_id=soc_id)
        assert isinstance(incomplete_list, list)

        req_info_res = ResidentAutomationService.request_missing_information(req.id, admin_user=admin)
        assert req_info_res["success"] is True

        # Features 11–18: Approve request and verify automated onboarding communications
        approved_req = RegistrationService.approve_request(req.id, admin_user=admin)
        assert approved_req.status == "APPROVED"

        # Verify resident notifications sent
        user_logs = NotificationLog.query.filter_by(user_id=approved_req.user_id).all()
        assert len(user_logs) >= 5  # Welcome, Checklist, Rules, Emergency, Payment, First-Bill
        assert any("Welcome to" in log.message for log in user_logs)
        assert any("Checklist" in log.message for log in user_logs)
        assert any("Guidelines" in log.message for log in user_logs)
        assert any("Emergency Contacts" in log.message for log in user_logs)
        assert any("Payment Center" in log.message for log in user_logs)

        # Features 19 & 20: Inactive resident detection & reminder
        # Set resident move_in_date to 40 days ago without emergency contact
        res_obj = db.session.get(Resident, p25_env["resident_id"])
        res_obj.move_in_date = utcnow().date() - timedelta(days=40)
        db.session.commit()

        inact_res = ResidentAutomationService.detect_and_remind_inactive_residents(society_id=soc_id, days_threshold=30)
        assert inact_res["scanned"] >= 1
        assert inact_res["reminded"] >= 1


def test_phase3_billing_automation_suite(app, p25_env):
    """
    Tests Features 21–40:
    - Monthly bill generation & missing bill detection
    - Duplicate, incorrect month, missing amount, and abnormal bill detection
    - Aging buckets & pending months assistant
    - Billing reminder pipeline & chronic defaulter escalation
    - Defaulter, collection, unpaid, and reconciliation reports
    - Payment/bill anomaly detectors
    """
    with app.app_context():
        soc_id = p25_env["society_id"]
        flat_id = p25_env["flat_id"]
        resident_id = p25_env["resident_id"]
        current_m = utcnow().strftime("%Y-%m")

        # Feature 21: Auto monthly bill generation
        gen_res = BillingAutomationService.generate_monthly_bills_automation(society_id=soc_id, billing_month=current_m)
        assert "created" in gen_res

        # Feature 22: Missing bills detector
        missing_bills = BillingAutomationService.detect_missing_bills(society_id=soc_id, billing_month=current_m)
        assert isinstance(missing_bills, list)

        # Feature 23: Duplicate bills detector
        dupes = BillingAutomationService.detect_duplicate_bills(society_id=soc_id)
        assert isinstance(dupes, list)

        # Feature 24: Incorrect billing month detector
        bad_bills = BillingAutomationService.detect_incorrect_billing_months(society_id=soc_id)
        assert isinstance(bad_bills, list)

        # Feature 25: Missing maintenance amount detector
        zero_bills = BillingAutomationService.detect_missing_maintenance_amounts(society_id=soc_id)
        assert isinstance(zero_bills, list)

        # Feature 26: Abnormal bill amounts detector
        abnormal = BillingAutomationService.detect_abnormal_bill_amounts(society_id=soc_id)
        assert isinstance(abnormal, list)

        # Feature 27: Pending months calculation assistant
        pending_asst = BillingAutomationService.calculate_pending_months_assistant(flat_id=flat_id, society_id=soc_id)
        assert "total_due" in pending_asst
        assert "current_month_maintenance" in pending_asst

        # Feature 28: 5-tier Aging Buckets
        aging = BillingAutomationService.get_billing_aging_buckets(society_id=soc_id)
        assert "current" in aging
        assert "bucket_1_30" in aging
        assert "bucket_31_60" in aging
        assert "bucket_61_90" in aging
        assert "bucket_90_plus" in aging

        # Features 29–33: Reminders, Overdue, Final Notice, Chronic Defaulter Escalation
        # Seed an overdue bill 45 days ago
        old_due = utcnow().date() - timedelta(days=45)
        old_bill = MaintenanceBill(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_number=f"BILL-{soc_id}-{flat_id}-OLD-01",
            billing_month="2026-01",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=0.0,
            remaining_amount=1500.0,
            due_date=old_due,
            status="Overdue",
        )
        db.session.add(old_bill)
        db.session.commit()

        dispatch_res = BillingAutomationService.dispatch_billing_reminders_and_escalations(society_id=soc_id)
        assert dispatch_res["reminders_sent"] >= 1

        # Feature 34: Defaulter Report
        def_report = BillingAutomationService.generate_defaulter_report(society_id=soc_id)
        assert len(def_report) >= 1
        assert def_report[0]["resident_id"] == resident_id

        # Feature 35: Monthly Collection Report
        coll_report = BillingAutomationService.generate_monthly_collection_report(society_id=soc_id, billing_month=current_m)
        assert "collection_efficiency" in coll_report
        assert "total_billed" in coll_report

        # Feature 36: Unpaid Bills Report
        unpaid_rep = BillingAutomationService.generate_unpaid_bills_report(society_id=soc_id)
        assert len(unpaid_rep) >= 1

        # Feature 37: Billing Reconciliation Report
        recon_rep = BillingAutomationService.generate_billing_reconciliation_report(society_id=soc_id)
        assert "total_billed" in recon_rep
        assert recon_rep["discrepancies_count"] == 0

        # Features 38, 39, 40: Detectors
        no_bills = BillingAutomationService.detect_payments_without_bills(society_id=soc_id)
        assert isinstance(no_bills, list)

        no_pmts = BillingAutomationService.detect_bills_without_payments(society_id=soc_id)
        assert len(no_pmts) >= 1

        partials = BillingAutomationService.detect_partial_payments(society_id=soc_id)
        assert isinstance(partials, list)


def test_phase4_payment_automation_suite(app, p25_env):
    """
    Tests Features 41–60:
    - Payment-to-bill matching & reference matching
    - Duplicate, unmatched, and suspicious payment detection
    - Failed/pending payment alerts
    - Post-payment automated workflow (confirmation, receipt trigger, bill status sync, history sync)
    - Reconciliation pipeline & 3-day issue escalation
    - Unusual refund & cash alerts
    - Daily payment summary
    """
    with app.app_context():
        soc_id = p25_env["society_id"]
        flat_id = p25_env["flat_id"]
        resident_id = p25_env["resident_id"]
        now = utcnow()

        # Seed bill
        bill = MaintenanceBill(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_number=f"BILL-P4-{soc_id}-{flat_id}",
            billing_month="2026-06",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=0.0,
            remaining_amount=1500.0,
            due_date=now.date(),
            status="Pending",
        )
        db.session.add(bill)
        db.session.commit()

        # Feature 41 & 42: Payment creation and auto-matching
        payment = Payment(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_id=bill.id,
            transaction_id="TXN-P4-112233",
            amount_paid=1500.0,
            payment_method="UPI",
            status="captured",
            payment_date=now,
        )
        db.session.add(payment)
        db.session.commit()

        # Feature 48, 49, 50, 51, 52: on_payment_success automated workflows
        PaymentAutomationService.on_payment_success(payment.id)

        # Check bill was synchronized to Paid
        updated_bill = db.session.get(MaintenanceBill, bill.id)
        assert updated_bill.status == "Paid"
        assert updated_bill.remaining_amount == 0.0

        # Check receipt was generated
        receipt = PaymentReceipt.query.filter_by(payment_id=payment.id).first()
        assert receipt is not None
        assert receipt.receipt_number.startswith("RCPT-")

        # Feature 43: Duplicate payment detector
        dupes = PaymentAutomationService.detect_duplicate_payments(society_id=soc_id)
        assert isinstance(dupes, list)

        # Feature 44: Unmatched payment detector
        unmatched = PaymentAutomationService.detect_unmatched_payments(society_id=soc_id)
        assert isinstance(unmatched, list)

        # Feature 45: Suspicious payment detector
        suspicious = PaymentAutomationService.detect_suspicious_payments(society_id=soc_id)
        assert isinstance(suspicious, list)

        # Feature 46: Failed payment alert
        PaymentAutomationService.on_payment_failed(payment.id, error_reason="Gateway bank network timeout")
        failed_alert = AutomationAlert.query.filter_by(society_id=soc_id, alert_type="PAYMENT_FAILED").first()
        assert failed_alert is not None

        # Feature 47: Pending payment scanner
        pending_pmts = PaymentAutomationService.scan_pending_payments(society_id=soc_id, hours_threshold=0)
        assert isinstance(pending_pmts, list)

        # Features 53–57: Reconciliation pipeline & issue escalation
        recon_pipe = PaymentAutomationService.run_reconciliation_pipeline(society_id=soc_id)
        assert "reconciliation_stats" in recon_pipe

        # Feature 58: Unusual refund detection
        refund_req = RefundRequest(
            society_id=soc_id,
            payment_id=payment.id,
            resident_id=resident_id,
            requested_amount=5000.0,  # Exceeds payment (1500)
            reason="Accidental double payment",
            status="pending",
        )
        db.session.add(refund_req)
        db.session.commit()

        unusual_refunds = PaymentAutomationService.detect_unusual_refunds(society_id=soc_id)
        assert len(unusual_refunds) >= 1
        assert unusual_refunds[0]["refund_id"] == refund_req.id

        # Feature 59: Unusual cash payment alert
        cash_pmt = Payment(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_id=bill.id,
            transaction_id="TXN-CASH-BIG",
            amount_paid=25000.0,  # > 20k
            payment_method="Cash",
            status="pending",
            payment_date=now - timedelta(hours=50),
        )
        db.session.add(cash_pmt)
        db.session.commit()

        cash_alerts = PaymentAutomationService.alert_unusual_cash_payments(society_id=soc_id)
        assert len(cash_alerts) >= 1

        # Feature 60: Daily payment summary
        summary = PaymentAutomationService.generate_daily_payment_summary(society_id=soc_id, target_date=now.date())
        assert summary["total_transactions"] >= 1
        assert "UPI" in summary["by_method"]


def test_phase5_accounting_automation_suite(app, p25_env):
    """
    Tests Features 61–80:
    - Ledger credit entry on verified payment
    - Ledger debit entry on approved expense voucher
    - Invoice matching & duplicate invoice/expense detection
    - Unusual expense detection & vendor price increase detection
    - Monthly totals, surplus, and cash position calculations
    - Financial reporting suite (Summary, Expense report, Income-vs-Expense)
    - Alerts (Budget overrun, unusual spending, missing invoice, pending voucher escalation)
    - Financial snapshot & Committee brief
    """
    with app.app_context():
        soc_id = p25_env["society_id"]
        admin = db.session.get(User, p25_env["admin_id"])
        flat_id = p25_env["flat_id"]
        resident_id = p25_env["resident_id"]
        now = utcnow()

        # Seed bill and payment
        bill = MaintenanceBill(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_number=f"BILL-P5-{soc_id}",
            billing_month="2026-07",
            base_amount=1500.0,
            total_amount=1500.0,
            amount_paid=1500.0,
            remaining_amount=0.0,
            due_date=now.date(),
            status="Paid",
        )
        db.session.add(bill)
        db.session.commit()

        payment = Payment(
            society_id=soc_id,
            resident_id=resident_id,
            flat_id=flat_id,
            bill_id=bill.id,
            transaction_id="TXN-P5-LEDGER",
            amount_paid=1500.0,
            payment_method="UPI",
            status="Success",
            payment_date=now,
        )
        db.session.add(payment)
        db.session.commit()

        # Feature 61: Record ledger CREDIT entry on verified payment
        ledger_credit = AccountingAutomationService.record_payment_ledger_entry(payment.id)
        assert ledger_credit is not None
        assert ledger_credit.entry_type == "CREDIT"
        assert ledger_credit.amount == 1500.0

        # Feature 62: Record ledger DEBIT entry on approved ExpenseVoucher
        voucher = ExpenseVoucher(
            voucher_number="VCHR-P5-001",
            society_id=soc_id,
            category="Security",
            amount=800.0,
            payee_name="SecureGuard Pvt Ltd",
            description="Monthly guard service",
            invoice_number="INV-SG-101",
            expense_date=now.date(),
            status="Approved",
            approved_by_id=admin.id,
        )
        db.session.add(voucher)
        db.session.commit()

        ledger_debit = AccountingAutomationService.record_expense_ledger_entry(voucher.id, approved_by_id=admin.id)
        assert ledger_debit is not None
        assert ledger_debit.entry_type == "DEBIT"
        assert ledger_debit.amount == 800.0

        # Feature 63: Match invoice to document vault
        doc = Document(
            society_id=soc_id,
            title="Invoice INV-SG-101 SecureGuard",
            category="Invoices",
            file_path="invoices/inv_sg_101.pdf",
            uploaded_by_id=admin.id,
        )
        db.session.add(doc)
        db.session.commit()

        matched_doc = AccountingAutomationService.match_expense_to_invoice(voucher.id)
        assert matched_doc is not None
        assert matched_doc.id == doc.id

        # Feature 64 & 65: Duplicate invoice and expense detection
        dupe_invs = AccountingAutomationService.detect_duplicate_invoices(society_id=soc_id)
        assert isinstance(dupe_invs, list)

        dupe_exps = AccountingAutomationService.detect_duplicate_expenses(society_id=soc_id)
        assert isinstance(dupe_exps, list)

        # Feature 66: Unusual expense detection
        unusual_exps = AccountingAutomationService.detect_unusual_expenses(society_id=soc_id)
        assert isinstance(unusual_exps, list)

        # Feature 67: Vendor price increase detection
        vendor = Vendor(society_id=soc_id, company_name="SecureGuard Pvt Ltd", contact_person="John", phone="9876543311", category="Security")
        db.session.add(vendor)
        db.session.commit()

        price_hikes = AccountingAutomationService.detect_vendor_price_increases(society_id=soc_id)
        assert isinstance(price_hikes, list)

        # Features 68, 69, 70: Monthly Financials, Surplus, Cash Position
        fin = AccountingAutomationService.calculate_monthly_financials(society_id=soc_id)
        assert fin["total_income"] >= 1500.0
        assert fin["total_expense"] >= 800.0
        assert fin["net_surplus"] == round(fin["total_income"] - fin["total_expense"], 2)
        assert "cash_position" in fin

        # Feature 71: Monthly accounting summary
        summary = AccountingAutomationService.generate_monthly_accounting_summary(society_id=soc_id)
        assert summary["month"] == fin["month"]

        # Feature 72: Expense report
        exp_rep = AccountingAutomationService.generate_expense_report(society_id=soc_id)
        assert len(exp_rep) >= 1

        # Feature 73: Income vs expense report
        ive_rep = AccountingAutomationService.generate_income_vs_expense_report(society_id=soc_id, months_count=3)
        assert len(ive_rep) == 3

        # Features 74–78: Financial Alerts & Audits
        audit_res = AccountingAutomationService.run_financial_alerts_and_audits(society_id=soc_id)
        assert "alerts_generated" in audit_res

        # Feature 79: Real-time financial snapshot
        snapshot = AccountingAutomationService.get_financial_snapshot(society_id=soc_id)
        assert snapshot["monthly_surplus"] == fin["net_surplus"]

        # Feature 80: Committee / Board financial brief
        brief = AccountingAutomationService.generate_committee_financial_brief(society_id=soc_id)
        assert "Executive Committee Financial Brief" in brief["brief_text"]
        assert brief["society_id"] == soc_id
