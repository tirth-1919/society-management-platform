<<<<<<< HEAD
"""
payments.py — Complete Razorpay payment routes.

Security principles:
- All amounts are loaded from DB, never from browser input.
- Resident ownership is verified server-side on every request.
- Webhook HMAC verification is performed before any DB mutations.
- Razorpay secret keys are NEVER sent to the browser.
- Only the public RAZORPAY_KEY_ID is included in checkout responses.
"""

=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
import secrets

from flask import (
    Blueprint,
<<<<<<< HEAD
    abort,
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

<<<<<<< HEAD
from app.config import Config
from app.models import (
    AuditLog,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    RefundRequest,
    Role,
    User,
    db,
)
=======
from app.models import db, MaintenanceBill, Payment, Role, User
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
from app.services.billing_service import BillingService
from app.services.payment_service import PaymentService
from app.services.receipt_service import ReceiptService
from app.services.tenant_service import TenantService
<<<<<<< HEAD
from app.utils import utcnow
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


payments_bp = Blueprint("payments", __name__, url_prefix="/payments")


<<<<<<< HEAD
# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _require_resident_session():
    """Return (user, resident) for logged-in resident; abort 403 otherwise."""
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(403)
    if user.role != Role.RESIDENT:
        abort(403)
    resident = user.residents[0] if user.residents else None
    if not resident:
        abort(403)
    return user, resident


def _require_admin_session():
    """Return user for logged-in admin; abort 403 otherwise."""
    user = db.session.get(User, session.get("user_id"))
    if not user or user.role == Role.RESIDENT:
        abort(403)
    return user


# ---------------------------------------------------------------------------
# Admin / staff routes — bill listing & generation
# ---------------------------------------------------------------------------


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
@payments_bp.route("/bills")
def bills():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
<<<<<<< HEAD
    if not society_id and user and user.society_id:
        society_id = user.society_id
        session["society_id"] = society_id
=======

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
    TenantService.enforce_tenant_isolation(user, society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
<<<<<<< HEAD
=======

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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

<<<<<<< HEAD
    return render_template("maintenance/bills.html", bills=bills_list)
=======
    return render_template(
        "maintenance/bills.html",
        bills=bills_list,
    )
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


@payments_bp.route("/generate-monthly-bills", methods=["POST"])
def generate_bills():
    society_id = session.get("society_id")
    user = db.session.get(User, session.get("user_id"))
<<<<<<< HEAD
    if not society_id and user and user.society_id:
        society_id = user.society_id
        session["society_id"] = society_id

    if not society_id:
        flash("Please select a society before generating bills.", "danger")
        return redirect(url_for("payments.bills"))
=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

    TenantService.enforce_tenant_isolation(user, society_id)

    billing_month = request.form.get("billing_month")
<<<<<<< HEAD
    try:
        created = BillingService.generate_monthly_bills(society_id, billing_month)
        flash(
            f"Successfully generated {len(created)} maintenance bills for {billing_month}!",
            "success",
        )
    except ValueError as err:
        flash(str(err), "danger")
    return redirect(url_for("payments.bills"))


# ---------------------------------------------------------------------------
# Pay single bill — Razorpay Checkout (GET) / Legacy mock form (POST)
# ---------------------------------------------------------------------------


@payments_bp.route("/pay", methods=["GET", "POST"], defaults={"bill_id": None})
@payments_bp.route("/pay/<int:bill_id>", methods=["GET", "POST"])
def pay_bill(bill_id=None):
    user = db.session.get(User, session.get("user_id"))
    if not user:
        return redirect(url_for("auth.login"))

    society_id = session.get("society_id") or user.society_id

    if bill_id is None:
        if user.role == Role.RESIDENT:
            resident = user.residents[0] if user.residents else None
            if resident:
                next_bill = (
                    MaintenanceBill.query.filter_by(society_id=society_id, resident_id=resident.id)
                    .filter(MaintenanceBill.status.in_(["Pending", "Overdue", "Partially Paid"]))
                    .order_by(MaintenanceBill.due_date.asc())
                    .first()
                )
                if not next_bill:
                    next_bill = (
                        MaintenanceBill.query.filter_by(society_id=society_id, resident_id=resident.id)
                        .order_by(MaintenanceBill.billing_month.desc())
                        .first()
                    )
                if next_bill:
                    return redirect(url_for("payments.pay_bill", bill_id=next_bill.id))
            return redirect(url_for("resident.bills"))
        return redirect(url_for("payments.bills"))

    bill = MaintenanceBill.query.get_or_404(bill_id)
    TenantService.enforce_tenant_isolation(user, bill.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
=======

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
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        if (
            not resident
            or (bill.resident_id is not None and bill.resident_id != resident.id)
            or (bill.resident_id is None and bill.flat_id != resident.flat_id)
        ):
            return "Forbidden", 403
<<<<<<< HEAD
    else:
        resident = None

    if bill.remaining_amount <= 0:
        flash("This bill is already paid.", "info")
=======

    if bill.remaining_amount <= 0:
        flash("This bill is already paid.", "info")

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        latest_payment = (
            Payment.query.filter_by(bill_id=bill.id)
            .order_by(Payment.payment_date.desc())
            .first()
        )
<<<<<<< HEAD
        if latest_payment:
            return redirect(url_for("payments.payment_success", payment_id=latest_payment.id))
        return redirect(url_for("payments.bills"))

    # Legacy mock POST path (backward-compatible for test/admin)
    if request.method == "POST":
        idempotency_key = request.form.get("idempotency_key")
        legacy_confirmation = (
            "amount" in request.form and "amount_to_pay" not in request.form
        )
        if legacy_confirmation:
            idempotency_key = f"IDEM-LEGACY-{bill_id}-{secrets.token_hex(16)}"
        elif not idempotency_key:
            flash("Your payment session expired. Please review and confirm again.", "danger")
            return redirect(url_for("payments.pay_bill", bill_id=bill.id))

        existing_payment = Payment.query.filter_by(idempotency_key=idempotency_key).first()
        if existing_payment:
            flash("This payment was already recorded. No second charge was made.", "info")
=======

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
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
            return redirect(url_for("payments.bills"))

        if legacy_confirmation:
            amount_to_pay = bill.remaining_amount
        else:
            try:
<<<<<<< HEAD
                amount_to_pay = float(request.form.get("amount_to_pay", bill.remaining_amount))
            except (TypeError, ValueError):
                flash("Enter a valid payment amount.", "danger")
                return redirect(url_for("payments.pay_bill", bill_id=bill.id))
=======
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
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32

            if amount_to_pay <= 0 or amount_to_pay > bill.remaining_amount + 0.01:
                flash(
                    "Payment amount must be greater than zero and "
                    "no more than the remaining balance.",
                    "danger",
                )
<<<<<<< HEAD
                return redirect(url_for("payments.pay_bill", bill_id=bill.id))

        payment_method = request.form.get("payment_method", "UPI")
=======
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

>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
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
<<<<<<< HEAD
        except ValueError as error:
            db.session.rollback()
            flash(str(error), "danger")
            return redirect(url_for("payments.pay_bill", bill_id=bill.id))
        except Exception:
            db.session.rollback()
            flash("Payment could not be completed. Please try again.", "danger")
            return redirect(url_for("payments.pay_bill", bill_id=bill.id))

        return redirect(url_for("payments.payment_success", payment_id=payment.id))

    # GET — show Razorpay Checkout page
    razorpay_provider = PaymentService.get_provider("Razorpay")
    return render_template(
        "maintenance/pay_now.html",
        bill=bill,
        resident=resident,
        society_id=bill.society_id,
        razorpay_configured=razorpay_provider.is_configured,
        razorpay_key_id=Config.RAZORPAY_KEY_ID if razorpay_provider.is_configured else None,
=======

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
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
        idempotency_key=(f"IDEM-{bill_id}-{secrets.token_hex(16)}"),
    )


<<<<<<< HEAD
# ---------------------------------------------------------------------------
# Razorpay Checkout API endpoints
# ---------------------------------------------------------------------------


@payments_bp.route("/razorpay/create-order", methods=["POST"])
def razorpay_create_order():
    """
    Server-side Razorpay order creation.
    Called by the payment checkout page via fetch().
    Returns only public data (no secrets).
    """
    user, resident = _require_resident_session()
    society_id = user.society_id

    data = request.get_json(silent=True) or {}
    bill_id = data.get("bill_id")

    if not bill_id:
        return jsonify({"error": "bill_id is required"}), 400

    try:
        result = PaymentService.create_razorpay_order(
            bill_id=int(bill_id),
            society_id=society_id,
            resident_id=resident.id,
        )
        # Return only public fields — never return key_secret
        return jsonify(
            {
                "order_id": result["order_id"],
                "amount": result["amount"],
                "amount_paise": result["amount_paise"],
                "currency": result["currency"],
                "key_id": Config.RAZORPAY_KEY_ID,
                "transaction_id": result["transaction_id"],
                "resident_name": resident.full_name,
                "flat_number": resident.flat.flat_number if resident.flat else "",
                "society_name": user.society.name if hasattr(user, "society") and user.society else "",
            }
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


@payments_bp.route("/razorpay/verify", methods=["POST"])
def razorpay_verify():
    """
    Server-side Razorpay payment signature verification.
    NEVER marks a bill as paid based on frontend signal alone.
    The HMAC signature must pass before any DB update.
    """
    user, resident = _require_resident_session()

    data = request.get_json(silent=True) or {}
    order_id = data.get("razorpay_order_id")
    payment_id = data.get("razorpay_payment_id")
    signature = data.get("razorpay_signature")

    if not all([order_id, payment_id, signature]):
        return jsonify({"error": "Missing payment verification parameters."}), 400

    try:
        payment = PaymentService.verify_and_capture(
            razorpay_order_id=order_id,
            razorpay_payment_id=payment_id,
            razorpay_signature=signature,
            society_id=user.society_id,
            resident_id=resident.id,
        )
        return jsonify(
            {
                "success": True,
                "payment_id": payment.id,
                "transaction_id": payment.transaction_id,
                "redirect_url": url_for(
                    "payments.payment_success", payment_id=payment.id
                ),
            }
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc), "success": False}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc), "success": False}), 400


# ---------------------------------------------------------------------------
# Payment result pages
# ---------------------------------------------------------------------------


=======
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
@payments_bp.route("/success/<int:payment_id>")
def payment_success(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    user = db.session.get(User, session.get("user_id"))
<<<<<<< HEAD
    TenantService.enforce_tenant_isolation(user, payment.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or payment.resident_id != resident.id:
            return "Forbidden", 403

    return render_template("maintenance/payment_success.html", payment=payment)
=======

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
>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32


@payments_bp.route("/failed/<int:bill_id>")
def payment_failed(bill_id):
    bill = MaintenanceBill.query.get_or_404(bill_id)
    user = db.session.get(User, session.get("user_id"))
<<<<<<< HEAD
    TenantService.enforce_tenant_isolation(user, bill.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or bill.resident_id != resident.id:
            return "Forbidden", 403

    # Find latest failed payment for this bill (if any)
    failed_payment = (
        Payment.query.filter_by(bill_id=bill.id, status="failed")
        .order_by(Payment.payment_date.desc())
        .first()
    )

    return render_template(
        "maintenance/payment_failed.html",
        bill=bill,
        failed_payment=failed_payment,
    )


@payments_bp.route("/cancelled/<int:bill_id>")
def payment_cancelled(bill_id):
    bill = MaintenanceBill.query.get_or_404(bill_id)
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, bill.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or bill.resident_id != resident.id:
            return "Forbidden", 403

    return render_template("maintenance/payment_cancelled.html", bill=bill)


@payments_bp.route("/retry/<int:bill_id>")
def payment_retry(bill_id):
    bill = MaintenanceBill.query.get_or_404(bill_id)
    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, bill.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or bill.resident_id != resident.id:
            return "Forbidden", 403

    if bill.remaining_amount <= 0:
        flash("This bill is already paid.", "info")
        return redirect(url_for("payments.bills"))

    razorpay_provider = PaymentService.get_provider("Razorpay")
    return render_template(
        "maintenance/payment_retry.html",
        bill=bill,
        razorpay_configured=razorpay_provider.is_configured,
    )


# ---------------------------------------------------------------------------
# Multi-month payment
# ---------------------------------------------------------------------------


@payments_bp.route("/multi-month/<int:resident_id>", methods=["GET"])
def multi_month_payment(resident_id):
    user, resident = _require_resident_session()
    if resident.id != resident_id:
        abort(403)

    unpaid = BillingService.resident_dashboard_summary(
        resident.id, user.society_id
    )["unpaid_bills"]

    razorpay_provider = PaymentService.get_provider("Razorpay")
    return render_template(
        "maintenance/multi_month_payment.html",
        unpaid_bills=unpaid,
        resident=resident,
        razorpay_configured=razorpay_provider.is_configured,
    )


@payments_bp.route("/razorpay/create-multi-order", methods=["POST"])
def razorpay_create_multi_order():
    """Create a single Razorpay order for multiple pending bills."""
    user, resident = _require_resident_session()

    data = request.get_json(silent=True) or {}
    bill_ids = data.get("bill_ids", [])

    if not bill_ids or not isinstance(bill_ids, list):
        return jsonify({"error": "bill_ids list is required"}), 400

    try:
        result = PaymentService.create_multi_month_order(
            bill_ids=[int(b) for b in bill_ids],
            society_id=user.society_id,
            resident_id=resident.id,
        )
        return jsonify(
            {
                "order_id": result["order_id"],
                "amount": result["amount"],
                "amount_paise": result["amount_paise"],
                "currency": result["currency"],
                "key_id": Config.RAZORPAY_KEY_ID,
                "transaction_id": result["transaction_id"],
                "bills": result["bills"],
                "resident_name": resident.full_name,
            }
        )
    except PermissionError as exc:
        return jsonify({"error": str(exc)}), 403
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    except RuntimeError as exc:
        return jsonify({"error": str(exc)}), 503


# ---------------------------------------------------------------------------
# Payment history and transaction details
# ---------------------------------------------------------------------------


@payments_bp.route("/history")
def payment_history():
    user, resident = _require_resident_session()

    query = Payment.query.filter_by(
        society_id=user.society_id,
        resident_id=resident.id,
    )

    # Filters
    status_filter = request.args.get("status", "").strip()
    month_filter = request.args.get("month", "").strip()
    year_filter = request.args.get("year", "").strip()
    method_filter = request.args.get("method", "").strip()

    if status_filter:
        query = query.filter_by(status=status_filter)
    if month_filter and len(month_filter) == 7:
        query = query.filter(
            db.func.strftime("%Y-%m", Payment.payment_date) == month_filter
        )
    elif year_filter.isdigit() and len(year_filter) == 4:
        query = query.filter(
            db.func.strftime("%Y", Payment.payment_date) == year_filter
        )
    if method_filter:
        query = query.filter_by(payment_method=method_filter)

    page = max(request.args.get("page", 1, type=int), 1)
    pagination = query.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=10, error_out=False
    )

    years = [
        v[0]
        for v in db.session.query(
            db.func.strftime("%Y", Payment.payment_date)
        )
        .filter_by(society_id=user.society_id, resident_id=resident.id)
        .distinct()
        .order_by(db.desc(db.func.strftime("%Y", Payment.payment_date)))
        .all()
    ]

    return render_template(
        "maintenance/payment_history.html",
        payments=pagination.items,
        pagination=pagination,
        years=years,
        filters={
            "status": status_filter,
            "month": month_filter,
            "year": year_filter,
            "method": method_filter,
        },
    )


@payments_bp.route("/transaction/<txn_id>")
def transaction_detail(txn_id):
    user, resident = _require_resident_session()
    payment = Payment.query.filter_by(
        transaction_id=txn_id,
        society_id=user.society_id,
        resident_id=resident.id,
    ).first_or_404()

    return render_template("maintenance/transaction_details.html", payment=payment)


# ---------------------------------------------------------------------------
# Receipt download + QR verification (public)
# ---------------------------------------------------------------------------


@payments_bp.route("/receipt/<int:payment_id>")
def download_receipt(payment_id):
    payment = db.session.get(Payment, payment_id)
    if not payment:
        abort(404, description="Payment not found")

    user = db.session.get(User, session.get("user_id"))
    TenantService.enforce_tenant_isolation(user, payment.society_id)

    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or payment.resident_id != resident.id:
            return "Forbidden", 403

    # Receipt can only be downloaded/viewed for captured/paid payments
    valid_statuses = ("captured", "Success", "authorized")
    if payment.status not in valid_statuses:
        flash("Receipt is not available for unpaid or failed payments.", "warning")
        return redirect(url_for("payments.bills"))

    try:
        pdf_path = ReceiptService.generate_pdf_receipt(payment.id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).exception("Receipt generation error for payment #%s: %s", payment_id, exc)
        flash("Receipt could not be generated. Please try again.", "danger")
        return redirect(url_for("payments.bills"))

    from pathlib import Path
    pdf_path_obj = Path(pdf_path)
    if not pdf_path_obj.exists() or pdf_path_obj.stat().st_size == 0:
        import logging
        logging.getLogger(__name__).error("Receipt PDF file not found or 0 bytes at %s", pdf_path)
        flash("Receipt file unavailable. Please try again.", "danger")
        return redirect(url_for("payments.bills"))

    inline = request.args.get("view") == "1"
    rcpt_num = payment.receipt.receipt_number if payment.receipt else f"RCPT-{payment.id}"
    download_filename = f"{rcpt_num}.pdf"

    return send_file(
        str(pdf_path_obj),
        mimetype="application/pdf",
        as_attachment=not inline,
        download_name=download_filename,
    )


@payments_bp.route("/receipt/verify/<receipt_number>")
def verify_receipt(receipt_number):
    """Public receipt QR verification — no login required."""
    receipt = PaymentReceipt.query.filter_by(
        receipt_number=receipt_number
    ).first_or_404()
    payment = db.session.get(Payment, receipt.payment_id)
    bill = db.session.get(MaintenanceBill, payment.bill_id) if payment else None

    # Minimal info — do not expose sensitive resident data
    return render_template(
        "maintenance/receipt_verify.html",
        receipt=receipt,
        payment=payment,
        bill=bill,
    )


# ---------------------------------------------------------------------------
# Refund management (resident)
# ---------------------------------------------------------------------------


@payments_bp.route("/refund-request/<int:payment_id>", methods=["GET", "POST"])
def refund_request(payment_id):
    user, resident = _require_resident_session()
    payment = Payment.query.filter_by(
        id=payment_id,
        society_id=user.society_id,
        resident_id=resident.id,
    ).first_or_404()

    if request.method == "POST":
        try:
            amount = float(request.form.get("amount", 0))
            reason = request.form.get("reason", "").strip()
            if not reason:
                raise ValueError("Please provide a reason for the refund request.")
            req = PaymentService.submit_refund_request(
                payment_id=payment.id,
                society_id=user.society_id,
                resident_id=resident.id,
                amount=amount,
                reason=reason,
            )
            flash("Refund request submitted. Admin will review it shortly.", "success")
            return redirect(
                url_for("payments.refund_status", refund_id=req.id)
            )
        except (ValueError, PermissionError) as exc:
            flash(str(exc), "danger")

    return render_template(
        "maintenance/refund_request.html",
        payment=payment,
    )


@payments_bp.route("/refund/<int:refund_id>")
def refund_status(refund_id):
    user, resident = _require_resident_session()
    refund_req = RefundRequest.query.filter_by(
        id=refund_id,
        society_id=user.society_id,
        resident_id=resident.id,
    ).first_or_404()

    return render_template(
        "maintenance/refund_status.html",
        refund_request=refund_req,
    )


# ---------------------------------------------------------------------------
# Webhook endpoint (Razorpay)
# ---------------------------------------------------------------------------


@payments_bp.route("/webhook/<provider>", methods=["POST"])
def webhook(provider):
    """
    Razorpay webhook receiver.
    Raw body is captured before any JSON parsing for HMAC verification.
    Signature MUST be verified before any DB mutation.
    """
    body_bytes = request.get_data()  # raw bytes for HMAC verification
    signature = request.headers.get("X-Razorpay-Signature", "")

    payload = request.get_json(force=True, silent=True) or {}

    res = PaymentService.handle_webhook(
        provider_name=provider,
        payload_dict=payload,
        signature=signature,
        body_bytes=body_bytes,
    )

    status_code = 200 if res.get("status") in ("Success", "Ignored") else 400
    return jsonify(res), status_code


# ---------------------------------------------------------------------------
# Admin payment dashboard & management
# ---------------------------------------------------------------------------


@payments_bp.route("/admin/dashboard")
def admin_payment_dashboard():
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    # Summary stats
    from sqlalchemy import func

    total_collected = (
        db.session.query(func.sum(Payment.amount_paid))
        .filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success"]),
        )
        .scalar()
        or 0.0
    )

    today = utcnow().date()
    today_collected = (
        db.session.query(func.sum(Payment.amount_paid))
        .filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success"]),
            db.func.date(Payment.payment_date) == today,
        )
        .scalar()
        or 0.0
    )

    this_month = utcnow().strftime("%Y-%m")
    month_collected = (
        db.session.query(func.sum(Payment.amount_paid))
        .filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success"]),
            db.func.strftime("%Y-%m", Payment.payment_date) == this_month,
        )
        .scalar()
        or 0.0
    )

    failed_count = Payment.query.filter_by(
        society_id=society_id, status="failed"
    ).count()
    pending_count = Payment.query.filter_by(
        society_id=society_id, status="created"
    ).count()
    refunded_sum = (
        db.session.query(func.sum(Payment.refund_amount))
        .filter(
            Payment.society_id == society_id,
            Payment.refund_status.isnot(None),
        )
        .scalar()
        or 0.0
    )

    # Recent transactions (paginated)
    page = max(request.args.get("page", 1, type=int), 1)
    status_filter = request.args.get("status", "").strip()
    q = Payment.query.filter_by(society_id=society_id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    pagination = q.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "admin/payment_dashboard.html",
        total_collected=total_collected,
        today_collected=today_collected,
        month_collected=month_collected,
        failed_count=failed_count,
        pending_count=pending_count,
        refunded_sum=refunded_sum,
        payments=pagination.items,
        pagination=pagination,
        filters={"status": status_filter},
    )


@payments_bp.route("/admin/reconciliation")
def admin_reconciliation():
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    # Find payments that may need attention
    pending_old = (
        Payment.query.filter_by(society_id=society_id, status="created")
        .filter(Payment.provider_order_id.isnot(None))
        .order_by(Payment.payment_date.desc())
        .all()
    )

    failed = (
        Payment.query.filter_by(society_id=society_id, status="failed")
        .order_by(Payment.payment_date.desc())
        .limit(50)
        .all()
    )

    unverified_captured = (
        Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["captured", "Success"]),
            Payment.webhook_verified.is_(False),
        )
        .order_by(Payment.payment_date.desc())
        .all()
    )

    return render_template(
        "admin/payment_reconciliation.html",
        pending_old=pending_old,
        failed=failed,
        unverified_captured=unverified_captured,
    )


@payments_bp.route("/admin/refunds")
def admin_refunds():
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    status_filter = request.args.get("status", "pending").strip()
    q = RefundRequest.query.filter_by(society_id=society_id)
    if status_filter:
        q = q.filter_by(status=status_filter)

    page = max(request.args.get("page", 1, type=int), 1)
    pagination = q.order_by(RefundRequest.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "admin/admin_refunds.html",
        refund_requests=pagination.items,
        pagination=pagination,
        filters={"status": status_filter},
    )


@payments_bp.route("/admin/refunds/<int:request_id>/approve", methods=["POST"])
def admin_approve_refund(request_id):
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id

    req = RefundRequest.query.filter_by(
        id=request_id, society_id=society_id
    ).first_or_404()

    if req.status != "pending":
        flash("Only pending refund requests can be approved.", "danger")
        return redirect(url_for("payments.admin_refunds"))

    req.status = "approved"
    req.admin_notes = request.form.get("admin_notes", "").strip()
    db.session.add(
        AuditLog(
            society_id=society_id,
            action="REFUND_APPROVED",
            details=(
                f"Admin approved refund request #{req.id} "
                f"for ₹{req.requested_amount:.2f}"
            ),
        )
    )
    db.session.commit()
    flash(f"Refund request #{request_id} approved.", "success")
    return redirect(url_for("payments.admin_refunds"))


@payments_bp.route("/admin/refunds/<int:request_id>/process", methods=["POST"])
def admin_process_refund(request_id):
    user = _require_admin_session()

    try:
        req = PaymentService.process_refund(
            refund_request_id=request_id,
            admin_user_id=user.id,
        )
        flash(
            f"Refund of ₹{req.refunded_amount:.2f} processed via Razorpay "
            f"(Refund ID: {req.razorpay_refund_id}).",
            "success",
        )
    except (ValueError, RuntimeError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("payments.admin_refunds"))


@payments_bp.route("/admin/refunds/<int:request_id>/reject", methods=["POST"])
def admin_reject_refund(request_id):
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id

    req = RefundRequest.query.filter_by(
        id=request_id, society_id=society_id
    ).first_or_404()

    req.status = "rejected"
    req.admin_notes = request.form.get("admin_notes", "").strip()
    req.processed_by = user.id
    req.processed_at = utcnow()
    db.session.add(
        AuditLog(
            society_id=society_id,
            action="REFUND_REJECTED",
            details=f"Admin rejected refund request #{req.id}",
        )
    )
    db.session.commit()
    flash(f"Refund request #{request_id} rejected.", "info")
    return redirect(url_for("payments.admin_refunds"))


# ---------------------------------------------------------------------------
# Cash Payment Workflow Routes
# ---------------------------------------------------------------------------


@payments_bp.route("/cash/submit", methods=["POST"])
def submit_cash_payment():
    """Submit a cash payment for verification by society admin."""
    user = db.session.get(User, session.get("user_id"))
    if not user:
        abort(403)

    bill_id = request.form.get("bill_id", type=int)
    amount_paid = request.form.get("amount_paid", type=float)
    notes = request.form.get("notes", "").strip()

    if not bill_id or not amount_paid or amount_paid <= 0:
        flash("Valid Bill ID and payment amount are required.", "danger")
        return redirect(url_for("payments.bills"))

    bill = MaintenanceBill.query.get_or_404(bill_id)
    TenantService.enforce_tenant_isolation(user, bill.society_id)

    resident_id = None
    if user.role == Role.RESIDENT:
        resident = user.residents[0] if user.residents else None
        if not resident or (bill.resident_id and bill.resident_id != resident.id):
            abort(403)
        resident_id = resident.id
    else:
        resident_id = bill.resident_id

    try:
        payment = PaymentService.submit_cash_payment(
            bill_id=bill.id,
            society_id=bill.society_id,
            resident_id=resident_id,
            amount_paid=amount_paid,
            notes=notes,
        )
        flash(
            f"Cash payment of ₹{amount_paid:,.2f} recorded (#{payment.transaction_id}). Awaiting admin verification.",
            "success",
        )
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("payments.bills"))


@payments_bp.route("/admin/cash-verifications")
def admin_cash_verifications():
    """List cash payments requiring verification for admin."""
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id
    TenantService.enforce_tenant_isolation(user, society_id)

    status_filter = request.args.get("status", "pending").strip()
    q = Payment.query.filter_by(society_id=society_id, payment_method="Cash")
    if status_filter:
        q = q.filter_by(status=status_filter)

    page = max(request.args.get("page", 1, type=int), 1)
    pagination = q.order_by(Payment.payment_date.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "admin/cash_verifications.html",
        payments=pagination.items,
        pagination=pagination,
        filters={"status": status_filter},
    )


@payments_bp.route("/admin/cash/<int:payment_id>/approve", methods=["POST"])
def admin_approve_cash_payment(payment_id):
    """Admin approves a cash payment."""
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id

    payment = Payment.query.filter_by(
        id=payment_id, society_id=society_id
    ).first_or_404()

    admin_notes = request.form.get("admin_notes", "").strip()
    try:
        PaymentService.approve_cash_payment(
            payment_id=payment.id,
            admin_user_id=user.id,
            admin_notes=admin_notes,
        )
        flash(
            f"Cash payment #{payment.transaction_id} of ₹{payment.amount_paid:,.2f} approved and receipt generated.",
            "success",
        )
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("payments.admin_cash_verifications"))


@payments_bp.route("/admin/cash/<int:payment_id>/reject", methods=["POST"])
def admin_reject_cash_payment(payment_id):
    """Admin rejects a cash payment."""
    user = _require_admin_session()
    society_id = session.get("society_id") or user.society_id

    payment = Payment.query.filter_by(
        id=payment_id, society_id=society_id
    ).first_or_404()

    rejection_reason = request.form.get("rejection_reason", "").strip() or "Rejected by administrator"
    try:
        PaymentService.reject_cash_payment(
            payment_id=payment.id,
            admin_user_id=user.id,
            rejection_reason=rejection_reason,
        )
        flash(
            f"Cash payment #{payment.transaction_id} rejected.",
            "info",
        )
    except (ValueError, PermissionError) as exc:
        flash(str(exc), "danger")

    return redirect(url_for("payments.admin_cash_verifications"))

=======

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




>>>>>>> c4eff3ccaafe1830d27d73a4d6db5050498d5d32
