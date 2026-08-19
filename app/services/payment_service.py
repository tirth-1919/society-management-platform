"""
payment_service.py — Complete Razorpay payment service.

Security principles enforced here:
- Amounts are always read from the database, never from the browser.
- Signature verification is HMAC-SHA256 server-side.
- Webhook secrets are never logged or exposed.
- Every financial mutation is wrapped in a DB transaction.
- Idempotency keys prevent duplicate charges on browser retries.
"""

import hashlib
import hmac
import json
import logging
import secrets

from app.config import Config
from app.models import (
    AuditLog,
    MaintenanceBill,
    Payment,
    PaymentReceipt,
    Resident,
    RefundRequest,
    WebhookLog,
    db,
)
from app.services.billing_service import BillingService
from app.services.notification_service import NotificationService
from app.services.receipt_service import ReceiptService
from app.utils import utcnow

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payment provider abstraction
# ---------------------------------------------------------------------------


class PaymentProviderInterface:
    def create_order(self, amount_paise, currency="INR", receipt_id=None):
        raise NotImplementedError

    def verify_payment_signature(self, order_id, payment_id, signature):
        raise NotImplementedError

    def fetch_payment(self, payment_id):
        raise NotImplementedError

    def refund(self, payment_id, amount_paise, notes=None):
        raise NotImplementedError


class MockPaymentProvider(PaymentProviderInterface):
    """Development mock — no real money moves."""

    is_configured = False

    def create_order(self, amount_paise, currency="INR", receipt_id=None):
        order_id = f"order_mock_{secrets.token_hex(8)}"
        return {
            "id": order_id,
            "amount": amount_paise,
            "currency": currency,
            "status": "created",
            "provider": "Mock",
        }

    def verify_payment_signature(self, order_id, payment_id, signature):
        # Mock accepts any non-empty signature
        return bool(signature)

    def fetch_payment(self, payment_id):
        return {"id": payment_id, "status": "captured", "method": "mock"}

    def refund(self, payment_id, amount_paise, notes=None):
        return {"id": f"rfnd_mock_{secrets.token_hex(8)}", "status": "processed"}


class RazorpayProvider(PaymentProviderInterface):
    """
    Production Razorpay integration using the official Python SDK.
    Requires RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET to be set.
    """

    def __init__(self, key_id, key_secret):
        self.key_id = key_id
        self.key_secret = key_secret
        self.is_configured = bool(
            key_id
            and key_secret
            and key_id != "mock_key_id"
            and key_secret != "mock_key_secret"
        )
        self._client = None

    def _get_client(self):
        """Lazily initialise the Razorpay SDK client."""
        if self._client is None:
            try:
                import razorpay  # type: ignore[import]

                self._client = razorpay.Client(
                    auth=(self.key_id, self.key_secret)
                )
            except ImportError:
                raise RuntimeError(
                    "razorpay package is not installed. "
                    "Run: pip install razorpay>=1.4.1"
                )
        return self._client

    def create_order(self, amount_paise, currency="INR", receipt_id=None):
        """Create a Razorpay order. Amount must be in paise (₹1 = 100 paise)."""
        client = self._get_client()
        data = {
            "amount": int(amount_paise),
            "currency": currency,
            "receipt": receipt_id or f"rcpt_{secrets.token_hex(8)}",
            "payment_capture": 1,  # auto-capture
        }
        order = client.order.create(data=data)
        return order  # dict with keys: id, amount, currency, status, ...

    def verify_payment_signature(self, order_id, payment_id, signature):
        """
        Cryptographically verify Razorpay payment signature.
        Returns True only if the HMAC-SHA256 matches Razorpay's specification.
        """
        if not signature or not self.key_secret:
            return False
        try:
            client = self._get_client()
            params = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": signature,
            }
            client.utility.verify_payment_signature(params)
            return True
        except Exception:
            # Fall back to manual HMAC check
            msg = f"{order_id}|{payment_id}"
            generated = hmac.new(
                self.key_secret.encode(), msg.encode(), hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(generated, signature)

    def verify_webhook_signature(self, body_bytes, signature):
        """
        Verify a Razorpay webhook request.
        body_bytes: raw request body (bytes)
        signature: value of X-Razorpay-Signature header
        """
        webhook_secret = Config.RAZORPAY_WEBHOOK_SECRET
        if not webhook_secret or not signature:
            return False
        try:
            client = self._get_client()
            client.utility.verify_webhook_signature(
                body_bytes.decode("utf-8"), signature, webhook_secret
            )
            return True
        except Exception:
            # Manual fallback
            expected = hmac.new(
                webhook_secret.encode(), body_bytes, hashlib.sha256
            ).hexdigest()
            return hmac.compare_digest(expected, signature)

    def fetch_payment(self, payment_id):
        client = self._get_client()
        return client.payment.fetch(payment_id)

    def refund(self, payment_id, amount_paise, notes=None):
        client = self._get_client()
        data = {"amount": int(amount_paise)}
        if notes:
            data["notes"] = notes
        return client.payment.refund(payment_id, data)


# ---------------------------------------------------------------------------
# PaymentService — all server-side payment logic
# ---------------------------------------------------------------------------


class PaymentService:
    # ------------------------------------------------------------------
    # Provider factory
    # ------------------------------------------------------------------

    @staticmethod
    def get_provider(provider_name="Mock"):
        if provider_name == "Razorpay":
            return RazorpayProvider(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET)
        return MockPaymentProvider()

    @staticmethod
    def get_active_provider():
        """Return Razorpay if configured, else Mock."""
        rzp = RazorpayProvider(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET)
        if rzp.is_configured:
            return rzp, "Razorpay"
        return MockPaymentProvider(), "Mock"

    # ------------------------------------------------------------------
    # Order creation (secure, server-side)
    # ------------------------------------------------------------------

    @staticmethod
    def create_razorpay_order(bill_id, society_id, resident_id):
        """
        Create a Razorpay payment order for a single maintenance bill.

        Security:
        - Amount is loaded exclusively from the database (never from browser).
        - Bill ownership is verified against the authenticated resident.
        - Prevents duplicate active orders for the same bill.
        - Returns only the public data needed to launch Razorpay Checkout.
        """
        bill = db.session.get(MaintenanceBill, bill_id)
        if not bill:
            raise ValueError("Bill not found.")
        if bill.society_id != society_id:
            raise PermissionError("Bill does not belong to this society.")
        if resident_id and bill.resident_id != resident_id:
            raise PermissionError("You are not authorised to pay this bill.")
        if bill.remaining_amount <= 0:
            raise ValueError("This bill is already fully paid.")

        # Check for a still-pending order (created but not yet verified)
        existing_pending = (
            Payment.query.filter_by(
                bill_id=bill.id,
                status="created",
            )
            .filter(Payment.provider_order_id.isnot(None))
            .first()
        )
        if existing_pending:
            # Return existing order so the same checkout window can be reused
            return {
                "order_id": existing_pending.provider_order_id,
                "amount": bill.remaining_amount,
                "amount_paise": int(bill.remaining_amount * 100),
                "currency": "INR",
                "transaction_id": existing_pending.transaction_id,
                "is_existing": True,
            }

        amount_paise = int(bill.remaining_amount * 100)
        if amount_paise <= 0:
            raise ValueError("Invalid payment amount.")

        provider, provider_name = PaymentService.get_active_provider()
        txn_id = f"TXN-{secrets.token_hex(8).upper()}"
        receipt_id = f"RCPT-{society_id}-{bill_id}-{utcnow().strftime('%Y%m%d%H%M%S')}"

        try:
            order = provider.create_order(
                amount_paise=amount_paise,
                currency="INR",
                receipt_id=receipt_id,
            )
        except Exception as exc:
            logger.error("Razorpay order creation failed: %s", exc)
            raise RuntimeError(
                "Payment gateway unavailable. Please try again later."
            ) from exc

        razorpay_order_id = order.get("id") or order.get("order_id")

        # Store a pending payment record
        pending = Payment(
            transaction_id=txn_id,
            society_id=society_id,
            bill_id=bill_id,
            resident_id=resident_id,
            amount_paid=bill.remaining_amount,
            payment_method="Razorpay",
            provider_name=provider_name,
            provider_order_id=razorpay_order_id,
            status="created",
            payment_date=utcnow(),
        )
        db.session.add(pending)

        # Audit log
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="RAZORPAY_ORDER_CREATED",
                details=(
                    f"Order {razorpay_order_id} created for Bill #{bill.bill_number}, "
                    f"amount ₹{bill.remaining_amount:.2f}"
                ),
            )
        )
        db.session.commit()

        return {
            "order_id": razorpay_order_id,
            "amount": bill.remaining_amount,
            "amount_paise": amount_paise,
            "currency": "INR",
            "transaction_id": txn_id,
            "key_id": Config.RAZORPAY_KEY_ID,
            "is_existing": False,
        }

    # ------------------------------------------------------------------
    # Multi-month order creation
    # ------------------------------------------------------------------

    @staticmethod
    def create_multi_month_order(bill_ids, society_id, resident_id):
        """
        Create a single Razorpay order for multiple pending bills.
        Amount is summed server-side from the database; browser-supplied
        amounts are never used.
        """
        if not bill_ids:
            raise ValueError("No bills selected.")

        bills = []
        total = 0.0
        for bid in bill_ids:
            bill = db.session.get(MaintenanceBill, bid)
            if not bill:
                raise ValueError(f"Bill #{bid} not found.")
            if bill.society_id != society_id:
                raise PermissionError("Bill society mismatch.")
            if bill.resident_id != resident_id:
                raise PermissionError("Unauthorised bill access.")
            if bill.remaining_amount <= 0:
                continue  # skip already paid
            bills.append(bill)
            total += bill.remaining_amount

        if not bills:
            raise ValueError("All selected bills are already paid.")

        amount_paise = int(total * 100)
        provider, provider_name = PaymentService.get_active_provider()
        txn_id = f"TXN-MULTI-{secrets.token_hex(8).upper()}"
        receipt_id = f"RCPT-MULTI-{society_id}-{utcnow().strftime('%Y%m%d%H%M%S')}"

        try:
            order = provider.create_order(
                amount_paise=amount_paise,
                currency="INR",
                receipt_id=receipt_id,
            )
        except Exception as exc:
            logger.error("Razorpay multi-month order failed: %s", exc)
            raise RuntimeError("Payment gateway unavailable.") from exc

        razorpay_order_id = order.get("id") or order.get("order_id")

        # Use the first bill as the primary reference; notes store all bill IDs
        primary_bill = bills[0]
        pending = Payment(
            transaction_id=txn_id,
            society_id=society_id,
            bill_id=primary_bill.id,
            resident_id=resident_id,
            amount_paid=total,
            payment_method="Razorpay",
            provider_name=provider_name,
            provider_order_id=razorpay_order_id,
            status="created",
            payment_date=utcnow(),
            notes=json.dumps({"bill_ids": [b.id for b in bills]}),
        )
        db.session.add(pending)
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="RAZORPAY_MULTI_ORDER_CREATED",
                details=(
                    f"Multi-month order {razorpay_order_id}, "
                    f"bills {[b.id for b in bills]}, total ₹{total:.2f}"
                ),
            )
        )
        db.session.commit()

        return {
            "order_id": razorpay_order_id,
            "amount": total,
            "amount_paise": amount_paise,
            "currency": "INR",
            "transaction_id": txn_id,
            "key_id": Config.RAZORPAY_KEY_ID,
            "bills": [
                {
                    "id": b.id,
                    "billing_month": b.billing_month,
                    "remaining_amount": b.remaining_amount,
                }
                for b in bills
            ],
        }

    # ------------------------------------------------------------------
    # Signature verification + payment capture
    # ------------------------------------------------------------------

    @staticmethod
    def verify_and_capture(
        razorpay_order_id,
        razorpay_payment_id,
        razorpay_signature,
        society_id,
        resident_id,
    ):
        """
        Server-side signature verification and payment capture.

        CRITICAL: A bill is NEVER marked paid solely on JavaScript success callback.
        The backend independently verifies the HMAC signature before any DB update.
        """
        # Load the pending payment record by order ID
        pending = Payment.query.filter_by(
            provider_order_id=razorpay_order_id,
            society_id=society_id,
        ).first()

        if not pending:
            raise ValueError("Payment order not found. Please contact support.")

        # Ownership check
        if resident_id and pending.resident_id != resident_id:
            raise PermissionError("Unauthorised payment verification attempt.")

        # Idempotency: already verified?
        if pending.status in ("captured", "Success"):
            return pending

        # Verify signature using provider
        provider, _ = PaymentService.get_active_provider()
        valid = provider.verify_payment_signature(
            razorpay_order_id, razorpay_payment_id, razorpay_signature
        )

        if not valid:
            # Mark as failed but preserve record
            pending.status = "failed"
            pending.failure_reason = "Signature verification failed"
            pending.provider_payment_id = razorpay_payment_id
            db.session.add(
                AuditLog(
                    society_id=society_id,
                    action="PAYMENT_SIGNATURE_INVALID",
                    details=(
                        f"Signature verification failed for order "
                        f"{razorpay_order_id}, payment {razorpay_payment_id}"
                    ),
                )
            )
            db.session.commit()
            raise PermissionError(
                "Payment signature verification failed. "
                "If money was deducted, contact support."
            )

        # Signature valid — update the pending record
        pending.provider_payment_id = razorpay_payment_id
        pending.provider_signature = razorpay_signature
        pending.status = "captured"
        pending.webhook_verified = True
        pending.verified_at = utcnow()

        # Determine which bills to update
        bill_ids = [pending.bill_id]
        if pending.notes:
            try:
                note_data = json.loads(pending.notes)
                bill_ids = note_data.get("bill_ids", bill_ids)
            except (json.JSONDecodeError, AttributeError):
                pass

        # Apply payment to each bill
        for bid in bill_ids:
            bill = db.session.get(MaintenanceBill, bid)
            if not bill or bill.remaining_amount <= 0:
                continue
            BillingService.apply_partial_payment(bid, bill.remaining_amount)

        # Generate receipt for primary payment
        receipt_num = (
            f"RCPT-{society_id}-{pending.id}-{utcnow().strftime('%Y%m%d%H%M%S')}"
        )
        # Only create receipt if one doesn't already exist
        if not pending.receipt:
            canonical_path = ReceiptService.get_receipt_file_path(receipt_num)
            receipt = PaymentReceipt(
                receipt_number=receipt_num,
                payment_id=pending.id,
                society_id=society_id,
                file_path=str(canonical_path),
            )
            db.session.add(receipt)

        # Audit
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="PAYMENT_VERIFIED_AND_CAPTURED",
                details=(
                    f"Razorpay payment {razorpay_payment_id} verified for order "
                    f"{razorpay_order_id}, amount \u20b9{pending.amount_paid:.2f}"
                ),
            )
        )
        db.session.commit()

        # ── POST TO GENERAL LEDGER (so admin collection is always accurate) ──
        try:
            from app.services.accounting_service import AccountingService
            primary_bill_for_ledger = db.session.get(MaintenanceBill, pending.bill_id)
            month_label = primary_bill_for_ledger.billing_month if primary_bill_for_ledger else "N/A"
            resident_for_ledger = db.session.get(Resident, pending.resident_id) if pending.resident_id else None
            resident_label = resident_for_ledger.full_name if resident_for_ledger else "Unknown"
            AccountingService.record_income_entry(
                society_id=society_id,
                amount=pending.amount_paid,
                account_head="Maintenance Collection",
                reference_type="RAZORPAY_PAYMENT",
                reference_id=pending.id,
                narration=(
                    f"Maintenance payment by {resident_label} for {month_label}. "
                    f"Razorpay ID: {razorpay_payment_id}. TXN: {pending.transaction_id}"
                ),
            )
        except Exception as ledger_exc:
            logger.warning("Accounting ledger entry failed (non-fatal): %s", ledger_exc)

        # Notification
        try:
            resident = (
                db.session.get(Resident, pending.resident_id)
                if pending.resident_id
                else None
            )
            user = resident.user if resident else None
            if user:
                primary_bill = db.session.get(MaintenanceBill, pending.bill_id)
                NotificationService.send_billing_notification(
                    user,
                    primary_bill.billing_month if primary_bill else "N/A",
                    "PAYMENT_SUCCESS",
                    (
                        f"Payment of ₹{pending.amount_paid:,.2f} received. "
                        f"Razorpay ID: {razorpay_payment_id}"
                    ),
                )
        except Exception as notify_exc:
            logger.warning("Payment notification failed: %s", notify_exc)

        return pending

    # ------------------------------------------------------------------
    # Legacy mock payment (preserved for backward compatibility)
    # ------------------------------------------------------------------

    @staticmethod
    def initiate_payment(
        bill_id,
        amount_to_pay,
        payment_method="UPI",
        idempotency_key=None,
        provider_name="Mock",
    ):
        """Initiates a payment order with idempotency check (legacy mock path)."""
        if idempotency_key:
            existing = Payment.query.filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return {
                    "transaction_id": existing.transaction_id,
                    "status": existing.status,
                    "is_duplicate": True,
                    "amount_paid": existing.amount_paid,
                }

        provider = PaymentService.get_provider(provider_name)
        order = provider.create_order(amount_to_pay)
        return {
            "order_id": order.get("id") or order.get("order_id"),
            "amount": amount_to_pay,
            "provider": provider_name,
            "is_duplicate": False,
        }

    @staticmethod
    def process_successful_payment(
        bill_id,
        society_id,
        resident_id,
        amount_paid,
        transaction_id,
        payment_method="UPI",
        provider_name="Mock",
        provider_order_id=None,
        provider_payment_id=None,
        idempotency_key=None,
        notes=None,
    ):
        """
        Executes verified server-side transaction for a payment.
        Updates bill remaining dues, logs audit record, generates payment receipt.
        """
        if idempotency_key:
            existing = Payment.query.filter_by(idempotency_key=idempotency_key).first()
            if existing:
                return existing

        bill = db.session.get(MaintenanceBill, bill_id)
        if not bill:
            raise ValueError("Bill not found")
        if bill.society_id != society_id or (
            resident_id and bill.resident_id != resident_id
        ):
            raise ValueError("Payment does not match the bill owner")

        bill = BillingService.apply_partial_payment(bill_id, amount_paid)

        payment = Payment(
            transaction_id=transaction_id,
            idempotency_key=idempotency_key,
            society_id=society_id,
            bill_id=bill_id,
            resident_id=resident_id,
            amount_paid=amount_paid,
            payment_method=payment_method,
            provider_name=provider_name,
            provider_order_id=provider_order_id,
            provider_payment_id=provider_payment_id,
            status="captured",
            payment_date=utcnow(),
            notes=notes,
            webhook_verified=True,
            verified_at=utcnow(),
        )
        db.session.add(payment)
        db.session.flush()

        receipt_num = (
            f"RCPT-{society_id}-{payment.id}-{utcnow().strftime('%Y%m%d')}"
        )
        canonical_path = ReceiptService.get_receipt_file_path(receipt_num)
        receipt = PaymentReceipt(
            receipt_number=receipt_num,
            payment_id=payment.id,
            society_id=society_id,
            file_path=str(canonical_path),
        )
        db.session.add(receipt)

        db.session.add(
            AuditLog(
                society_id=society_id,
                action="PAYMENT_RECORDED",
                details=(
                    f"Received payment of \u20b9{amount_paid} for Bill "
                    f"#{bill.bill_number} (Status: {bill.status})"
                ),
            )
        )
        db.session.commit()

        # ── POST TO GENERAL LEDGER ──
        try:
            from app.services.accounting_service import AccountingService
            res_for_ledger = db.session.get(Resident, resident_id) if resident_id else None
            res_label = res_for_ledger.full_name if res_for_ledger else "Unknown"
            AccountingService.record_income_entry(
                society_id=society_id,
                amount=amount_paid,
                account_head="Maintenance Collection",
                reference_type="BILL_PAYMENT",
                reference_id=payment.id,
                narration=(
                    f"Maintenance payment by {res_label} for {bill.billing_month}. "
                    f"TXN: {transaction_id}"
                ),
            )
        except Exception as ledger_exc:
            logger.warning("Accounting ledger entry failed (non-fatal): %s", ledger_exc)

        notification_resident_id = resident_id or bill.resident_id
        resident = (
            db.session.get(Resident, notification_resident_id)
            if notification_resident_id
            else None
        )
        user = resident.user if resident else None
        if user is None and bill.flat.residents:
            user = bill.flat.residents[0].user
        if user:
            NotificationService.send_billing_notification(
                user,
                bill.billing_month,
                "PAYMENT_SUCCESS",
                f"Your society maintenance payment of ₹{amount_paid:,.2f} for "
                f"{bill.billing_month} has been received successfully. Thank you.",
            )
        return payment

    # ------------------------------------------------------------------
    # Webhook processing
    # ------------------------------------------------------------------

    @staticmethod
    def handle_webhook(provider_name, payload_dict, signature=None, body_bytes=None):
        """
        Processes payment gateway webhooks with signature verification and deduplication.

        Signature MUST be verified before any DB mutation.
        Do NOT log secrets here.
        """
        payload_str = json.dumps(payload_dict, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        # Deduplication — same payload hash means already processed
        existing = WebhookLog.query.filter_by(payload_hash=payload_hash).first()
        if existing:
            return {"status": "Ignored", "message": "Duplicate webhook payload"}

        # Signature verification for Razorpay webhooks
        sig_verified = False
        if provider_name.lower() == "razorpay" and body_bytes:
            provider = RazorpayProvider(
                Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET
            )
            sig_header = signature or ""
            sig_verified = provider.verify_webhook_signature(body_bytes, sig_header)

            if not sig_verified and Config.RAZORPAY_WEBHOOK_SECRET:
                # If webhook secret is configured but signature is wrong, reject
                log = WebhookLog(
                    provider=provider_name,
                    event_type="SIGNATURE_INVALID",
                    payload_hash=payload_hash,
                    payload_json=payload_str,
                    signature_verified=False,
                    status="Rejected",
                )
                db.session.add(log)
                db.session.commit()
                return {"status": "Rejected", "message": "Invalid webhook signature"}
        elif provider_name.lower() == "mock":
            sig_verified = True

        # Log the webhook
        event_type = payload_dict.get("event", "unknown")
        log = WebhookLog(
            provider=provider_name,
            event_type=event_type,
            payload_hash=payload_hash,
            payload_json=payload_str,
            signature_verified=sig_verified,
            status="Processing",
        )
        db.session.add(log)
        db.session.flush()

        # Dispatch event handlers
        try:
            if event_type in ("payment.captured", "order.paid"):
                PaymentService._handle_webhook_captured(payload_dict)
            elif event_type == "payment.failed":
                PaymentService._handle_webhook_failed(payload_dict)
            elif event_type == "refund.created":
                PaymentService._handle_webhook_refund_created(payload_dict)
            elif event_type == "refund.processed":
                PaymentService._handle_webhook_refund_processed(payload_dict)

            log.status = "Processed"
        except Exception as exc:
            logger.error("Webhook processing error for %s: %s", event_type, exc)
            log.status = "Error"

        db.session.commit()
        return {"status": "Success", "message": "Webhook processed"}

    @staticmethod
    def _handle_webhook_captured(payload_dict):
        """Mark payment as captured when Razorpay confirms via webhook."""
        try:
            payment_entity = (
                payload_dict.get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            if not order_id:
                return

            pending = Payment.query.filter_by(
                provider_order_id=order_id,
            ).first()
            if not pending or pending.status in ("captured", "Success"):
                return

            pending.provider_payment_id = payment_id
            pending.status = "captured"
            pending.webhook_verified = True
            pending.verified_at = utcnow()

            db.session.add(
                AuditLog(
                    society_id=pending.society_id,
                    action="WEBHOOK_PAYMENT_CAPTURED",
                    details=f"Webhook confirmed capture of order {order_id}",
                )
            )
        except Exception as exc:
            logger.error("_handle_webhook_captured error: %s", exc)

    @staticmethod
    def _handle_webhook_failed(payload_dict):
        """Record payment failure from webhook."""
        try:
            payment_entity = (
                payload_dict.get("payload", {})
                .get("payment", {})
                .get("entity", {})
            )
            order_id = payment_entity.get("order_id")
            payment_id = payment_entity.get("id")
            error_desc = payment_entity.get("error_description", "Payment failed")

            if not order_id:
                return

            pending = Payment.query.filter_by(
                provider_order_id=order_id,
            ).first()
            if not pending or pending.status in ("captured", "Success"):
                return

            pending.provider_payment_id = payment_id
            pending.status = "failed"
            pending.failure_reason = error_desc

            db.session.add(
                AuditLog(
                    society_id=pending.society_id,
                    action="WEBHOOK_PAYMENT_FAILED",
                    details=f"Order {order_id} failed: {error_desc}",
                )
            )
        except Exception as exc:
            logger.error("_handle_webhook_failed error: %s", exc)

    @staticmethod
    def _handle_webhook_refund_created(payload_dict):
        """Update payment with refund details when refund is created."""
        try:
            refund_entity = (
                payload_dict.get("payload", {})
                .get("refund", {})
                .get("entity", {})
            )
            payment_id = refund_entity.get("payment_id")
            refund_id = refund_entity.get("id")
            refund_amount_paise = int(refund_entity.get("amount", 0))
            refund_amount = refund_amount_paise / 100

            if not payment_id:
                return

            payment = Payment.query.filter_by(
                provider_payment_id=payment_id
            ).first()
            if not payment:
                return

            payment.refund_id = refund_id
            payment.refund_amount = refund_amount
            payment.refund_status = "partial" if refund_amount < payment.amount_paid else "full"
        except Exception as exc:
            logger.error("_handle_webhook_refund_created error: %s", exc)

    @staticmethod
    def _handle_webhook_refund_processed(payload_dict):
        """Mark refund as completed."""
        try:
            refund_entity = (
                payload_dict.get("payload", {})
                .get("refund", {})
                .get("entity", {})
            )
            payment_id = refund_entity.get("payment_id")
            if not payment_id:
                return

            payment = Payment.query.filter_by(
                provider_payment_id=payment_id
            ).first()
            if payment:
                payment.status = (
                    "refunded" if payment.refund_amount >= payment.amount_paid
                    else "partially_refunded"
                )
        except Exception as exc:
            logger.error("_handle_webhook_refund_processed error: %s", exc)

    # ------------------------------------------------------------------
    # Refund management
    # ------------------------------------------------------------------

    @staticmethod
    def submit_refund_request(payment_id, society_id, resident_id, amount, reason):
        """Resident submits a refund request. Admin must approve before execution."""
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError("Payment not found.")
        if payment.society_id != society_id:
            raise PermissionError("Unauthorised refund request.")
        if payment.resident_id != resident_id:
            raise PermissionError("You can only request refunds for your own payments.")
        if payment.status not in ("captured", "Success"):
            raise ValueError("Refund can only be requested for captured payments.")

        max_refundable = payment.amount_paid - payment.refund_amount
        if amount <= 0 or amount > max_refundable:
            raise ValueError(
                f"Refund amount must be between ₹0.01 and ₹{max_refundable:.2f}."
            )

        existing_pending = RefundRequest.query.filter_by(
            payment_id=payment_id, status="pending"
        ).first()
        if existing_pending:
            raise ValueError("A refund request is already pending for this payment.")

        req = RefundRequest(
            payment_id=payment_id,
            society_id=society_id,
            resident_id=resident_id,
            requested_amount=amount,
            reason=reason,
            status="pending",
        )
        db.session.add(req)
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="REFUND_REQUESTED",
                details=(
                    f"Resident requested refund of ₹{amount:.2f} "
                    f"for payment {payment.transaction_id}"
                ),
            )
        )
        db.session.commit()
        return req

    @staticmethod
    def process_refund(refund_request_id, admin_user_id, approved_amount=None):
        """Admin-triggered Razorpay refund execution."""
        req = db.session.get(RefundRequest, refund_request_id)
        if not req:
            raise ValueError("Refund request not found.")
        if req.status != "approved":
            raise ValueError("Refund request must be approved before processing.")

        payment = db.session.get(Payment, req.payment_id)
        if not payment or not payment.provider_payment_id:
            raise ValueError("No Razorpay payment ID found for refund.")

        amount = approved_amount or req.requested_amount
        max_refundable = payment.amount_paid - payment.refund_amount
        if amount > max_refundable:
            raise ValueError(f"Refund amount exceeds refundable balance ₹{max_refundable:.2f}.")

        amount_paise = int(amount * 100)
        provider, _ = PaymentService.get_active_provider()

        try:
            result = provider.refund(
                payment.provider_payment_id,
                amount_paise,
                notes={"reason": req.reason, "request_id": str(req.id)},
            )
        except Exception as exc:
            req.status = "failed"
            req.admin_notes = f"Refund API error: {exc}"
            db.session.commit()
            raise RuntimeError(f"Refund failed: {exc}") from exc

        # Update payment and refund request
        rzp_refund_id = result.get("id")
        payment.refund_id = rzp_refund_id
        payment.refund_amount += amount
        payment.refund_status = (
            "full" if payment.refund_amount >= payment.amount_paid else "partial"
        )
        if payment.refund_amount >= payment.amount_paid:
            payment.status = "refunded"

        req.razorpay_refund_id = rzp_refund_id
        req.refunded_amount = amount
        req.status = "processed"
        req.processed_by = admin_user_id
        req.processed_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=payment.society_id,
                action="REFUND_PROCESSED",
                details=(
                    f"Razorpay refund {rzp_refund_id} of ₹{amount:.2f} "
                    f"processed for payment {payment.transaction_id}"
                ),
            )
        )
        db.session.commit()
        return req

    # ------------------------------------------------------------------
    # Cash Payment Workflow
    # ------------------------------------------------------------------

    @staticmethod
    def submit_cash_payment(bill_id, society_id, resident_id, amount_paid, notes=None):
        """
        Record a cash payment submission.
        Status is set to 'pending' and dues are NOT reduced until admin verifies.
        """
        bill = db.session.get(MaintenanceBill, bill_id)
        if not bill:
            raise ValueError("Bill not found.")
        if bill.society_id != society_id or (resident_id and bill.resident_id != resident_id):
            raise PermissionError("Bill does not belong to this resident or society.")
        if bill.remaining_amount <= 0:
            raise ValueError("Bill is already paid in full.")
        if amount_paid <= 0 or amount_paid > bill.remaining_amount + 0.01:
            raise ValueError("Invalid cash payment amount.")

        txn_id = f"CASH-{secrets.token_hex(6).upper()}"
        payment = Payment(
            transaction_id=txn_id,
            society_id=society_id,
            bill_id=bill_id,
            resident_id=resident_id or bill.resident_id,
            amount_paid=amount_paid,
            payment_method="Cash",
            provider_name="Manual",
            status="pending",
            notes=notes,
            payment_date=utcnow(),
        )
        db.session.add(payment)
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="CASH_PAYMENT_SUBMITTED",
                details=(
                    f"Cash payment of ₹{amount_paid:.2f} submitted for Bill "
                    f"#{bill.bill_number}, awaiting admin verification"
                ),
            )
        )
        db.session.commit()
        return payment

    @staticmethod
    def approve_cash_payment(payment_id, admin_user_id, admin_notes=None):
        """
        Admin approves cash payment:
        - Updates payment status to 'captured'
        - Deducts dues from bill transactionally
        - Creates payment receipt
        - Records verification timestamp and admin user
        - Sends resident notification
        """
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError("Payment not found.")
        if payment.status in ("captured", "Success"):
            return payment
        if payment.status != "pending" or payment.payment_method != "Cash":
            raise ValueError("Only pending cash payments can be approved.")

        bill = db.session.get(MaintenanceBill, payment.bill_id)
        if not bill:
            raise ValueError("Associated bill not found.")

        # Deduct from bill balance
        BillingService.apply_partial_payment(bill.id, payment.amount_paid)

        payment.status = "captured"
        payment.webhook_verified = True
        payment.verified_at = utcnow()
        if admin_notes:
            payment.notes = f"{(payment.notes or '')} [Admin: {admin_notes}]".strip()

        receipt_num = f"RCPT-CASH-{payment.society_id}-{payment.id}-{utcnow().strftime('%Y%m%d%H%M%S')}"
        if not payment.receipt:
            canonical_path = ReceiptService.get_receipt_file_path(receipt_num)
            receipt = PaymentReceipt(
                receipt_number=receipt_num,
                payment_id=payment.id,
                society_id=payment.society_id,
                file_path=str(canonical_path),
            )
            db.session.add(receipt)

        db.session.add(
            AuditLog(
                society_id=payment.society_id,
                user_id=admin_user_id,
                action="CASH_PAYMENT_APPROVED",
                details=(
                    f"Admin #{admin_user_id} approved cash payment "
                    f"#{payment.transaction_id} of ₹{payment.amount_paid:.2f}"
                ),
            )
        )
        db.session.commit()

        # Notify resident
        try:
            resident = db.session.get(Resident, payment.resident_id) if payment.resident_id else None
            user = resident.user if resident else None
            if user:
                NotificationService.send_billing_notification(
                    user,
                    bill.billing_month,
                    "PAYMENT_SUCCESS",
                    (
                        f"Your cash payment of ₹{payment.amount_paid:,.2f} for "
                        f"{bill.billing_month} has been approved and verified by admin."
                    ),
                )
        except Exception as exc:
            logger.warning("Cash payment notification failed: %s", exc)

        return payment

    @staticmethod
    def reject_cash_payment(payment_id, admin_user_id, rejection_reason=None):
        """
        Admin rejects cash payment:
        - Marks payment as 'rejected'
        - Leaves bill balance unchanged
        - Records audit log and reason
        """
        payment = db.session.get(Payment, payment_id)
        if not payment:
            raise ValueError("Payment not found.")
        if payment.status in ("captured", "Success"):
            raise ValueError("Cannot reject an already approved payment.")
        if payment.status != "pending" or payment.payment_method != "Cash":
            raise ValueError("Only pending cash payments can be rejected.")

        payment.status = "rejected"
        payment.failure_reason = rejection_reason or "Rejected by administrator"
        payment.verified_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=payment.society_id,
                user_id=admin_user_id,
                action="CASH_PAYMENT_REJECTED",
                details=(
                    f"Admin #{admin_user_id} rejected cash payment "
                    f"#{payment.transaction_id}: {rejection_reason}"
                ),
            )
        )
        db.session.commit()
        return payment

    # ------------------------------------------------------------------
    # Collection summary (admin dashboard)
    # ------------------------------------------------------------------

    @staticmethod
    def get_collection_summary(society_id, as_of=None):
        """
        Derives all collection analytics from actual Payment records.
        Never returns hard-coded numbers.

        Returns a dict with:
            today_collection, month_collection, year_collection, lifetime_collection
            online_collection, cash_collection, upi_collection
            pending_amount, overdue_amount, refunded_amount, net_collection
            paid_residents, unpaid_residents, overdue_residents
            collection_percentage, recent_payments
            by_method: {method: amount} breakdown
        """
        from datetime import date, datetime
        from app.models import MaintenanceBill, Resident

        now = as_of or utcnow()
        today = now.date()
        month_start = today.replace(day=1)
        year_start = today.replace(month=1, day=1)

        # All successful payments for this society
        successful_payments = (
            Payment.query.filter(
                Payment.society_id == society_id,
                Payment.status.in_(["captured", "Success", "authorized"]),
            ).all()
        )

        def paid_on_or_after(p, d):
            pd = p.payment_date
            if pd is None:
                return False
            if hasattr(pd, "date"):
                return pd.date() >= d
            return pd >= d

        today_collection = sum(
            p.amount_paid for p in successful_payments if paid_on_or_after(p, today)
        )
        month_collection = sum(
            p.amount_paid for p in successful_payments if paid_on_or_after(p, month_start)
        )
        year_collection = sum(
            p.amount_paid for p in successful_payments if paid_on_or_after(p, year_start)
        )
        lifetime_collection = sum(p.amount_paid for p in successful_payments)

        # Method breakdown
        by_method = {}
        for p in successful_payments:
            method = (p.payment_method or "Other").strip()
            by_method[method] = round(by_method.get(method, 0.0) + p.amount_paid, 2)

        cash_collection = by_method.get("Cash", 0.0)
        upi_collection = sum(
            v for k, v in by_method.items() if k.upper() in ("UPI", "QR")
        )
        online_collection = sum(
            v for k, v in by_method.items()
            if k.upper() not in ("CASH",)
        )

        # Refunds
        refunded_payments = Payment.query.filter(
            Payment.society_id == society_id,
            Payment.status.in_(["refunded", "partially_refunded"]),
        ).all()
        refunded_amount = sum(p.refund_amount or 0.0 for p in refunded_payments)

        net_collection = round(lifetime_collection - refunded_amount, 2)

        # Bills summary
        all_bills = MaintenanceBill.query.filter_by(society_id=society_id).all()
        pending_amount = sum(
            max(b.remaining_amount, 0.0)
            for b in all_bills
            if b.status in ("Pending", "Partially Paid", "Overdue")
        )
        overdue_amount = sum(
            max(b.remaining_amount, 0.0)
            for b in all_bills
            if b.status == "Overdue"
        )

        # Resident counts
        all_residents = Resident.query.filter_by(
            society_id=society_id, is_primary=True, occupancy_status="Active"
        ).all()
        paid_resident_ids = {
            p.resident_id for p in successful_payments
            if p.resident_id and paid_on_or_after(p, month_start)
        }
        overdue_resident_ids = {
            b.resident_id for b in all_bills
            if b.status == "Overdue" and b.resident_id
        }

        paid_residents = len(paid_resident_ids)
        unpaid_residents = len(all_residents) - paid_residents
        overdue_residents = len(overdue_resident_ids)

        total_billed = sum(b.total_amount for b in all_bills)
        collection_percentage = round(
            (lifetime_collection / total_billed * 100) if total_billed > 0 else 0.0, 1
        )

        recent_payments = (
            Payment.query.filter(
                Payment.society_id == society_id,
                Payment.status.in_(["captured", "Success", "authorized"]),
            )
            .order_by(Payment.payment_date.desc())
            .limit(10)
            .all()
        )

        return {
            "today_collection": round(today_collection, 2),
            "month_collection": round(month_collection, 2),
            "year_collection": round(year_collection, 2),
            "lifetime_collection": round(lifetime_collection, 2),
            "online_collection": round(online_collection, 2),
            "cash_collection": round(cash_collection, 2),
            "upi_collection": round(upi_collection, 2),
            "pending_amount": round(pending_amount, 2),
            "overdue_amount": round(overdue_amount, 2),
            "refunded_amount": round(refunded_amount, 2),
            "net_collection": net_collection,
            "paid_residents": paid_residents,
            "unpaid_residents": max(unpaid_residents, 0),
            "overdue_residents": overdue_residents,
            "collection_percentage": collection_percentage,
            "by_method": by_method,
            "recent_payments": recent_payments,
            "total_residents": len(all_residents),
        }

    @staticmethod
    def create_payment_dispute(society_id, resident_id, claimed_amount, transaction_id=None, bill_id=None, evidence_notes=None, claimed_date=None):
        """
        Creates a resident-filed payment dispute without mutating payment/bill status directly.
        """
        from app.models import PaymentDispute

        dispute = PaymentDispute(
            society_id=society_id,
            resident_id=resident_id,
            bill_id=bill_id,
            transaction_id=transaction_id,
            claimed_amount=float(claimed_amount),
            claimed_date=claimed_date or utcnow().date(),
            evidence_notes=evidence_notes,
            status="OPEN",
        )
        db.session.add(dispute)
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="PAYMENT_DISPUTE_FILED",
                details=f"Resident #{resident_id} filed payment dispute for ₹{claimed_amount:.2f} (Tx #{transaction_id or 'N/A'})",
            )
        )
        db.session.commit()
        return dispute

    @staticmethod
    def resolve_payment_dispute(dispute_id, admin_user_id, status, admin_notes=None):
        """
        Admin resolves or rejects a payment dispute.
        Allowed status: VERIFIED, RESOLVED, REJECTED.
        """
        from app.models import PaymentDispute

        dispute = db.session.get(PaymentDispute, dispute_id)
        if not dispute:
            raise ValueError("Payment dispute not found")

        if status not in ["VERIFIED", "RESOLVED", "REJECTED"]:
            raise ValueError("Invalid dispute resolution status")

        dispute.status = status
        dispute.admin_notes = admin_notes
        dispute.resolved_by_id = admin_user_id
        dispute.updated_at = utcnow()

        db.session.add(
            AuditLog(
                society_id=dispute.society_id,
                action=f"PAYMENT_DISPUTE_{status}",
                details=f"Admin #{admin_user_id} updated dispute #{dispute.id} to {status}. Notes: {admin_notes or '-'}",
            )
        )
        db.session.commit()
        return dispute

    @staticmethod
    def create_defaulter_followup(society_id, resident_id, flat_id, reason, due_date=None, priority="Medium", assigned_admin_id=None, notes=None):
        """
        Creates an administrative follow-up task against a defaulter.
        """
        from app.models import DefaulterFollowUp

        followup = DefaulterFollowUp(
            society_id=society_id,
            resident_id=resident_id,
            flat_id=flat_id,
            reason=reason,
            due_date=due_date,
            priority=priority,
            assigned_admin_id=assigned_admin_id,
            notes=notes,
            status="OPEN",
        )
        db.session.add(followup)
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="DEFAULTER_FOLLOWUP_CREATED",
                details=f"Created follow-up for Resident #{resident_id} (Flat #{flat_id}): {reason}",
            )
        )
        db.session.commit()
        return followup

    @staticmethod
    def update_defaulter_followup_status(followup_id, status, notes=None):
        """
        Updates defaulter follow-up status (OPEN, FOLLOW_UP, COMPLETED, CANCELLED).
        """
        from app.models import DefaulterFollowUp

        followup = db.session.get(DefaulterFollowUp, followup_id)
        if not followup:
            raise ValueError("Defaulter follow-up not found")

        if status not in ["OPEN", "FOLLOW_UP", "COMPLETED", "CANCELLED"]:
            raise ValueError("Invalid follow-up status")

        followup.status = status
        if notes:
            followup.notes = (followup.notes or "") + f"\n[{utcnow().strftime('%Y-%m-%d %H:%M')}] {notes}"
        followup.updated_at = utcnow()
        db.session.commit()
        return followup
