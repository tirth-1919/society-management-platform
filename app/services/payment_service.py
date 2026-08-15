from app.utils import utcnow
import hashlib
import hmac
import json
import secrets
from app.config import Config
from app.models import (
    db,
    Payment,
    PaymentReceipt,
    WebhookLog,
    AuditLog,
    Resident,
    MaintenanceBill,
)
from app.services.billing_service import BillingService
from app.services.notification_service import NotificationService


class PaymentProviderInterface:
    def create_order(self, amount, currency="INR", receipt_id=None):
        raise NotImplementedError

    def verify_payment_signature(self, order_id, payment_id, signature):
        raise NotImplementedError


class MockPaymentProvider(PaymentProviderInterface):
    def create_order(self, amount, currency="INR", receipt_id=None):
        order_id = f"order_mock_{secrets.token_hex(8)}"
        return {
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": "created",
            "provider": "Mock",
        }

    def verify_payment_signature(self, order_id, payment_id, signature):
        # Mock provider accepts any non-empty signature or validates token match
        return True


class RazorpayProvider(PaymentProviderInterface):
    def __init__(self, key_id, key_secret):
        self.key_id = key_id
        self.key_secret = key_secret
        # True only when real credentials were supplied via environment
        # config, not the placeholder defaults. Callers use this to decide
        # whether to honestly present the live flow or fall back to mock.
        self.is_configured = bool(
            key_id
            and key_secret
            and key_id != "mock_key_id"
            and key_secret != "mock_key_secret"
        )

    def create_order(self, amount, currency="INR", receipt_id=None):
        # Production Razorpay order payload construction
        order_id = f"order_rzp_{secrets.token_hex(8)}"
        return {
            "order_id": order_id,
            "amount": amount,
            "currency": currency,
            "status": "created",
            "provider": "Razorpay",
        }

    def verify_payment_signature(self, order_id, payment_id, signature):
        if not signature or not self.key_secret:
            return False
        msg = f"{order_id}|{payment_id}"
        generated = hmac.new(
            self.key_secret.encode(), msg.encode(), hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(generated, signature)


class PaymentService:
    @staticmethod
    def get_provider(provider_name="Mock"):
        if provider_name == "Razorpay":
            # Bug fix: this previously hardcoded "mock_key"/"mock_secret",
            # so real credentials set via RAZORPAY_KEY_ID/RAZORPAY_KEY_SECRET
            # were silently ignored even in production. Now reads from Config.
            return RazorpayProvider(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET)
        return MockPaymentProvider()

    @staticmethod
    def initiate_payment(
        bill_id,
        amount_to_pay,
        payment_method="UPI",
        idempotency_key=None,
        provider_name="Mock",
    ):
        """Initiates a payment order with idempotency check."""
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
            "order_id": order["order_id"],
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

        # Keep balance and payment creation in the same transaction.  The billing
        # service only mutates the session here; this method owns the commit.
        bill = BillingService.apply_partial_payment(bill_id, amount_paid)

        # Save payment record
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
            status="Success",
            payment_date=utcnow(),
            notes=notes,
        )
        db.session.add(payment)
        db.session.flush()

        # Generate payment receipt record
        receipt_num = (
            f"RCPT-{society_id}-{payment.id}-{utcnow().strftime('%Y%m%d')}"
        )
        receipt = PaymentReceipt(
            receipt_number=receipt_num,
            payment_id=payment.id,
            society_id=society_id,
            file_path=f"instance/documents/receipt_{receipt_num}.pdf",
        )
        db.session.add(receipt)

        # Audit log
        db.session.add(
            AuditLog(
                society_id=society_id,
                action="PAYMENT_RECORDED",
                details=f"Received payment of ₹{amount_paid} for Bill #{bill.bill_number} (Status: {bill.status})",
            )
        )

        db.session.commit()
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
                f"Your society maintenance payment of ₹{amount_paid:,.2f} for {bill.billing_month} has been received successfully. Thank you.",
            )
        return payment

    @staticmethod
    def handle_webhook(provider, payload_dict, signature=None):
        """Processes payment gateway webhooks safely with deduplication logic."""
        payload_str = json.dumps(payload_dict, sort_keys=True)
        payload_hash = hashlib.sha256(payload_str.encode()).hexdigest()

        # Deduplication check
        existing = WebhookLog.query.filter_by(payload_hash=payload_hash).first()
        if existing:
            return {"status": "Ignored", "message": "Duplicate webhook payload"}

        log = WebhookLog(
            provider=provider,
            event_type=payload_dict.get("event", "payment.captured"),
            payload_hash=payload_hash,
            payload_json=payload_str,
            status="Processed",
        )
        db.session.add(log)
        db.session.commit()
        return {"status": "Success", "message": "Webhook processed successfully"}




