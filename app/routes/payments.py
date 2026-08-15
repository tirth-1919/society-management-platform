import secrets

from flask import (
    Blueprint,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from app.models import db, MaintenanceBill, Payment, Role, User
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.receipt_service import ReceiptService
from app.services.tenant_service import TenantService


payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


@payments_bp.route("/bills")
def bills():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))

    TenantService.enforce_tenant_isolation(user, society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None

        bills_list = (
            MaintenanceBill.query.filter_by(
                society_id=society_id,
                resident_id=resident.id,
            )
            .order_by(MaintenanceBill.billing_month.desc())
            .all()
            if resident
            else []
        )
    else:
        bills_list = (
            MaintenanceBill.query.filter_by(society_id=society_id)
            .order_by(MaintenanceBill.created_at.desc())
            .all()
        )

    return render_template(
        "maintenance/bills.html",
        bills=bills_list,
    )


@payments_bp.route("/generate-monthly-bills", methods=["POST"])
def generate_bills():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))

    TenantService.enforce_tenant_isolation(user, society_id)

    billing_month = request.form.get("billing_month")

    created = BillingService.generate_monthly_bills(
        society_id,
        billing_month,
    )

    flash(
        f"Successfully generated {len(created)} maintenance bills for {billing_month}!",
        "success",
    )

    return redirect(url_for("payments.bills"))


@payments_bp.route("/pay/<int:bill_id>", methods=["GET", "POST"])
def pay_bill(bill_id):
    bill = MaintenanceBill.query.get_or_404(bill_id)
    user = db.session.get(User, session.get("user_id"))

    # Use the bill's society_id directly.
    # This removes the unused local society_id variable while preserving
    # tenant-isolation protection.
    TenantService.enforce_tenant_isolation(
        user,
        bill.society_id,
    )

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None

        # Legacy records without an occupant owner remain accessible to the
        # current flat resident. New bills always have resident_id and are
        # strictly isolated by that immutable occupancy reference.
        if (
            not resident
            or (bill.resident_id is not None and bill.resident_id != resident.id)
            or (bill.resident_id is None and bill.flat_id != resident.flat_id)
        ):
            return "Forbidden", 403

    if bill.remaining_amount <= 0:
        flash("This bill is already paid.", "info")

        latest_payment = (
            Payment.query.filter_by(bill_id=bill.id)
            .order_by(Payment.payment_date.desc())
            .first()
        )

        if latest_payment:
            return redirect(
                url_for(
                    "payments.payment_success",
                    payment_id=latest_payment.id,
                )
            )

        return redirect(url_for("payments.bills"))

    if request.method == "POST":
        idempotency_key = request.form.get("idempotency_key")

        # Backward-compatible legacy confirmation:
        # old clients posted an "amount" field.
        # Its value is intentionally ignored and the entire outstanding
        # balance is collected.
        legacy_confirmation = (
            "amount" in request.form and "amount_to_pay" not in request.form
        )

        if legacy_confirmation:
            idempotency_key = f"IDEM-LEGACY-{bill_id}-{secrets.token_hex(16)}"
        elif not idempotency_key:
            flash(
                "Your payment session expired. Please review and confirm again.",
                "danger",
            )
            return redirect(
                url_for(
                    "payments.pay_bill",
                    bill_id=bill.id,
                )
            )

        # A browser retry with the same confirmation token is a successful
        # replay, not a second charge.
        existing_payment = Payment.query.filter_by(
            idempotency_key=idempotency_key
        ).first()

        if existing_payment:
            flash(
                "This payment was already recorded. No second charge was made.",
                "info",
            )
            return redirect(url_for("payments.bills"))

        if legacy_confirmation:
            amount_to_pay = bill.remaining_amount
        else:
            try:
                amount_to_pay = float(
                    request.form.get(
                        "amount_to_pay",
                        bill.remaining_amount,
                    )
                )
            except (TypeError, ValueError):
                flash(
                    "Enter a valid payment amount.",
                    "danger",
                )
                return redirect(
                    url_for(
                        "payments.pay_bill",
                        bill_id=bill.id,
                    )
                )

            if amount_to_pay <= 0 or amount_to_pay > bill.remaining_amount + 0.01:
                flash(
                    "Payment amount must be greater than zero and "
                    "no more than the remaining balance.",
                    "danger",
                )
                return redirect(
                    url_for(
                        "payments.pay_bill",
                        bill_id=bill.id,
                    )
                )

        payment_method = request.form.get(
            "payment_method",
            "UPI",
        )

        txn_id = f"TXN-{secrets.token_hex(8).upper()}"

        try:
            payment = PaymentService.process_successful_payment(
                bill_id=bill.id,
                society_id=bill.society_id,
                resident_id=bill.resident_id,
                amount_paid=amount_to_pay,
                transaction_id=txn_id,
                payment_method=payment_method,
                provider_name="Mock",
                idempotency_key=idempotency_key,
            )

        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")

            return redirect(
                url_for(
                    "payments.pay_bill",
                    bill_id=bill.id,
                )
            )

        except Exception:
            db.session.rollback()
            flash(
                "Payment could not be completed. Please try again.",
                "danger",
            )

            return redirect(
                url_for(
                    "payments.pay_bill",
                    bill_id=bill.id,
                )
            )

        return redirect(
            url_for(
                "payments.payment_success",
                payment_id=payment.id,
            )
        )

    razorpay_provider = PaymentService.get_provider("Razorpay")

    return render_template(
        "maintenance/pay_now.html",
        bill=bill,
        razorpay_configured=razorpay_provider.is_configured,
        idempotency_key=(f"IDEM-{bill_id}-{secrets.token_hex(16)}"),
    )


@payments_bp.route("/success/<int:payment_id>")
def payment_success(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user = db.session.get(User, session.get("user_id"))

    TenantService.enforce_tenant_isolation(
        user,
        payment.society_id,
    )

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None

        if not resident or payment.resident_id != resident.id:
            return "Forbidden", 403

    return render_template(
        "maintenance/payment_success.html",
        payment=payment,
    )


@payments_bp.route("/failed/<int:bill_id>")
def payment_failed(bill_id):
    bill = MaintenanceBill.query.get_or_404(bill_id)
    user = db.session.get(User, session.get("user_id"))

    TenantService.enforce_tenant_isolation(
        user,
        bill.society_id,
    )

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None

        if not resident or bill.resident_id != resident.id:
            return "Forbidden", 403

    return render_template(
        "maintenance/payment_failed.html",
        bill=bill,
    )


@payments_bp.route("/receipt/<int:payment_id>")
def download_receipt(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user = db.session.get(User, session.get("user_id"))

    TenantService.enforce_tenant_isolation(
        user,
        payment.society_id,
    )

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None

        if not resident or payment.resident_id != resident.id:
            return "Forbidden", 403

    pdf_path = ReceiptService.generate_pdf_receipt(payment.id)

    # ?view=1 opens the PDF inline in the browser so the resident's
    # native PDF viewer print dialog can be used.
    # Default behaviour remains a forced download.
    inline = request.args.get("view") == "1"

    return send_file(
        pdf_path,
        as_attachment=not inline,
        download_name=(f"Receipt_{payment.transaction_id}.pdf"),
    )


@payments_bp.route("/webhook/<provider>", methods=["POST"])
def webhook(provider):
    payload = (
        request.get_json(
            force=True,
            silent=True,
        )
        or {}
    )

    res = PaymentService.handle_webhook(
        provider,
        payload,
    )

    return jsonify(res), 200




