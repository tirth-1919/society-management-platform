# Razorpay Payment System — Setup Guide

## Prerequisites

- Python ≥ 3.9  
- Flask application running (XAMPP MySQL or SQLite for dev)  
- A [Razorpay account](https://razorpay.com) (free to create)

---

## 1. Install Dependencies

```bash
pip install razorpay>=1.4.1
# or
pip install -r requirements.txt
```

---

## 2. Get Your Razorpay API Keys

1. Log in to [Razorpay Dashboard](https://dashboard.razorpay.com/)
2. Go to **Settings → API Keys**
3. Click **Generate Test Key** (for development) or **Generate Live Key** (for production)
4. Copy the **Key ID** and **Key Secret**

---

## 3. Configure Environment Variables

Edit your `.env` file (copy `.env.example` if you haven't already):

```env
# Razorpay Payment Gateway
RAZORPAY_KEY_ID=rzp_test_xxxxxxxxxxxx          # Your Key ID
RAZORPAY_KEY_SECRET=your_secret_key_here       # Your Key Secret — NEVER expose this

# Webhook
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret_here
```

> **WARNING:** Never commit `.env` to Git. It is already in `.gitignore`.

---

## 4. Run the Database Migration

### MySQL (Production / XAMPP)

Run the migration file against your MySQL database:

```sql
-- Using phpMyAdmin: Import this file
-- Using command line:
mysql -u root -p society_db < migrations/add_razorpay_fields.sql
```

### SQLite (Development)

No action needed — the `patch_sqlite_schema()` function in `app/models/tenant.py` automatically patches the schema on app startup.

---

## 5. Configure Razorpay Webhooks

1. In Razorpay Dashboard, go to **Settings → Webhooks**
2. Click **Add New Webhook**
3. Set Webhook URL: `https://your-domain.com/razorpay/webhook`
4. Set Secret: same value as `RAZORPAY_WEBHOOK_SECRET` in your `.env`
5. Select these events:
   - `payment.captured`
   - `payment.failed`
   - `refund.created`
   - `refund.processed`
6. Click **Save**

> For local development, use [ngrok](https://ngrok.com) to expose your local server:
> ```bash
> ngrok http 5000
> # Use the ngrok HTTPS URL as your webhook URL
> ```

---

## 6. Test the Payment Flow

Use Razorpay's test cards/UPI IDs:

| Method | Test Value | Expected |
|--------|-----------|---------|
| Card | `4111 1111 1111 1111` | Success |
| Card (CVV) | Any 3 digits | — |
| Card (Expiry) | Any future date | — |
| Card (Failure) | `4000 0000 0000 0002` | Failure |
| UPI | `success@razorpay` | Success |
| UPI (Failure) | `failure@razorpay` | Failure |
| Net Banking | Any bank | Success |

---

## 7. Payment Flow Architecture

```
Resident clicks "Pay Now"
       ↓
[POST /razorpay/create-order]  — Server creates Razorpay order (amount in paise)
       ↓
Razorpay Checkout Modal opens in browser
       ↓
Resident pays (UPI/Card/NetBanking/Wallet)
       ↓
Razorpay returns {order_id, payment_id, signature} to browser
       ↓
[POST /razorpay/verify]  — Server verifies HMAC signature
       ↓
If valid → Payment captured, bill marked paid, receipt generated
If invalid → Payment rejected, failure recorded
       ↓
[POST /razorpay/webhook]  — Razorpay sends server-to-server event (backup)
       ↓
Webhook HMAC verified → Payment/refund status updated
```

> **Security Rule:** Payment success is NEVER decided by the frontend. The server is the only authority.

---

## 8. Admin Panel

Access payment management from the Admin dashboard:

| URL | Purpose |
|-----|---------|
| `/admin/payments` | All transactions with filters |
| `/admin/payments/reconciliation` | Stale orders, failures, unverified |
| `/admin/refunds` | Approve / reject / process refunds |

---

## 9. Going Live

1. Switch from `rzp_test_*` keys to `rzp_live_*` keys in `.env`
2. Update webhook URL to your production domain
3. Run the MySQL migration on the production database (if not already done)
4. Enable TLS/HTTPS on your server (required for Razorpay live mode)

---

## Troubleshooting

| Issue | Solution |
|-------|---------|
| `razorpay.errors.BadRequestError` | Check Key ID / Secret in `.env` |
| Webhook signature mismatch | Verify `RAZORPAY_WEBHOOK_SECRET` matches Razorpay Dashboard |
| Payment captured but bill still unpaid | Check webhook is reaching your server; check `/admin/payments/reconciliation` |
| `Module 'razorpay' not found` | Run `pip install razorpay>=1.4.1` |
| SQLite schema error on startup | `patch_sqlite_schema()` failed — check `app/models/tenant.py` |
