# Developer Quick Reference — 50 User Features

## Route Map (18 New Routes)

```python
# Bills & Receipts
GET  /resident/bills/<id>/pdf                    # Feature 17: PDF download
GET  /resident/payments/yearly                   # Feature 18: Yearly summary
GET  /resident/receipts/<id>/qr                  # Feature 34: QR image
GET  /resident/payments/export.csv               # Feature 26: CSV export

# Complaints
GET  /resident/complaints                        # Feature 36: List
GET  /resident/complaints/<id>                   # Feature 37: Detail + timeline
POST /resident/complaints/<id>/rate              # Feature 40: 5-star rating

# Visitors
GET  /resident/visitors                          # Feature 43: History
GET  /resident/visitors/invite                   # Feature 41: Form
POST /resident/visitors/invite                   # Feature 41: Create
POST /resident/visitors/<id>/cancel              # Feature 44: Cancel pass

# Notifications
POST /resident/notifications/mark-all-read       # Feature 45: Bulk read

# Security
GET  /resident/security                          # Feature 48: Sessions
POST /resident/security/logout-all               # Feature 48: Logout others

# Household
GET  /resident/household                         # Feature 49: View all
POST /resident/household/dependent/add           # Feature 49: Add dependent
POST /resident/household/dependent/<id>/remove   # Feature 49: Remove dependent
POST /resident/household/emergency/add           # Feature 49: Add emergency
POST /resident/household/emergency/<id>/remove   # Feature 49: Remove emergency
```

---

## File Locations

### Templates Created
```
app/templates/resident/
├── yearly_summary.html      # Feature 18
├── complaints.html          # Feature 36
├── complaint_detail.html    # Features 37, 40
├── visitors.html            # Features 42, 43, 44
├── invite_visitor.html      # Feature 41
├── security.html            # Feature 48
└── household.html           # Feature 49
```

### Templates Enhanced
```
app/templates/
├── dashboard.html           # Features 1-10 (full rebuild)
├── base.html                # Sidebar expanded with 18 nav items
├── resident/
│   ├── bill_detail.html     # Features 13, 14, 17
│   ├── notifications.html   # Feature 45
│   ├── profile.html         # Feature 47
│   ├── receipts.html        # Features 34, 35
└── maintenance/
    └── refund_status.html   # Feature 30
```

### Backend Files
```
app/routes/
├── main.py                  # Dashboard data (rewritten)
└── resident.py              # +18 routes appended

app/services/
└── visitor_service.py       # Added expected_time param
```

---

## Database Models Used (No New Tables)

```python
# Existing models leveraged:
MaintenanceBill       # Bills, due dates, late fees
Payment               # Payment transactions
PaymentReceipt        # Receipts, standing instructions
Complaint             # Complaint tracking
ComplaintComment      # Timeline + ratings (RATING:N format)
Visitor               # Walk-in visitor logs
PreApprovedPass       # Visitor invitations (is_used for cancel)
Dependent             # Household dependents
EmergencyContact      # Emergency contacts
UserSession           # Active sessions
AuditLog              # Activity history, login logs
NotificationLog       # Notifications + read status
NotificationPreference # Channel preferences
RefundRequest         # Refund tracking
```

---

## Key Code Patterns

### 1. Auth Check (Every Route)
```python
def _current_resident():
    user_id = session.get('user_id')
    user = User.query.get(user_id)
    if not user or user.role != 'Resident':
        abort(403)
    resident = Resident.query.filter_by(user_id=user.id).first()
    if not resident or resident.account_status != 'ACTIVE':
        abort(403)
    return resident, user
```

### 2. IDOR Protection
```python
# Always scope queries to resident_id AND society_id
bill = MaintenanceBill.query.filter_by(
    id=bill_id,
    resident_id=resident.id,
    society_id=user.society_id
).first_or_404()
```

### 3. Complaint Rating (Duplicate Prevention)
```python
# Check existing rating before allowing new one
existing = ComplaintComment.query.filter_by(complaint_id=complaint.id) \
    .filter(ComplaintComment.comment.like('RATING:%')).first()
if existing:
    flash('You have already rated this complaint', 'warning')
    return redirect(...)
```

### 4. Visitor Pass Cancel
```python
# Mark is_used instead of creating new status field
pass_obj.is_used = True
pass_obj.actual_entry_time = datetime.utcnow()  # Mark as "processed"
db.session.commit()
```

### 5. Profile Completion (Template)
```jinja2
{% set fields_checked = [
    resident.user.phone,
    resident.alternate_phone,
    resident.aadhar_number,
    resident.user.email,
    resident.user.profile_photo,
    # ... 10 total fields
] %}
{% set completed = fields_checked | select | list | length %}
{% set percentage = (completed / 10 * 100) | int %}
```

### 6. CSV Export (Streaming)
```python
def generate():
    yield 'Date,Amount,Method,Receipt,Status\n'
    for payment in payments:
        yield f'{payment.payment_date},{payment.amount},...\n'

return Response(
    generate(),
    mimetype='text/csv',
    headers={'Content-Disposition': 'attachment; filename=payments.csv'}
)
```

---

## Security Checklist

- [x] Session-based auth with `user_id`
- [x] Role check (`user.role == 'Resident'`)
- [x] Account status check (`resident.account_status == 'ACTIVE'`)
- [x] IDOR protection (scoped queries)
- [x] Ownership validation on delete/cancel
- [x] Razorpay signature verification
- [x] CSRF tokens on all forms (Flask-WTF)
- [x] SQL injection prevention (SQLAlchemy ORM)
- [x] XSS prevention (Jinja2 auto-escaping)

---

## Testing Commands

```bash
# Start app
cd c:\Users\HP\Downloads\6
python run.py

# Verify routes
python -c "from app import create_app; app=create_app(); print(len(list(app.url_map.iter_rules())))"
# Should print: 104

# Check imports
python -c "from app import create_app; create_app()"
# Should exit clean with no errors

# Test PDF generation (requires reportlab)
curl http://localhost:5000/resident/bills/1/pdf -H "Cookie: session=..."

# Test CSV export
curl http://localhost:5000/resident/payments/export.csv -H "Cookie: session=..."

# Verify DB models
python -c "from app.models import *; print('All models OK')"
```

---

## Common Issues & Solutions

### Issue: PDF download fails
**Solution:** Install reportlab  
```bash
pip install reportlab
```

### Issue: QR codes not showing
**Solution:** Install qrcode + pillow  
```bash
pip install qrcode[pil]
```

### Issue: Razorpay payment fails
**Solution:** Check `.env` has valid keys  
```bash
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

### Issue: 403 on resident routes
**Solution:** Check user has `role='Resident'` and `account_status='ACTIVE'`

### Issue: Complaint rating not saving
**Solution:** Check `ComplaintComment` table exists and `comment` column accepts text

---

## Performance Notes

- Dashboard executes 5 queries (metrics, bills, payments, notifications, audit)
- All queries use indexed columns (resident_id, society_id, status)
- CSV export streams rows to avoid memory issues
- Yearly summary groups by year in SQL
- Profile completion calculated on template render (no DB hit)

---

## API Integration Points

### Razorpay
```python
# Order creation
client.order.create({
    'amount': amount_paise,
    'currency': 'INR',
    'receipt': receipt_num
})

# Payment verification
client.utility.verify_payment_signature({
    'razorpay_order_id': order_id,
    'razorpay_payment_id': payment_id,
    'razorpay_signature': signature
})
```

### Email (if configured)
```python
from app.services.notification_service import NotificationService
NotificationService.send_notification(
    user_id=user.id,
    channel='EMAIL',
    message='Your bill is due'
)
```

---

## Feature Flag Reference

All 50 features are ENABLED by default. No feature flags used.

To disable a feature:
1. Comment out the route in `app/routes/resident.py`
2. Remove the nav item from `app/templates/base.html`
3. Remove any dashboard widgets from `app/templates/dashboard.html`

---

## Maintenance Tasks

### Add new resident route
1. Add function to `app/routes/resident.py` with `@resident_bp.route(...)`
2. Call `_current_resident()` at start of function
3. Scope all DB queries to `resident.id` and `user.society_id`
4. Return `render_template('resident/your_page.html', ...)`
5. Add nav item to `app/templates/base.html` sidebar

### Add new dashboard widget
1. Edit `app/routes/main.py` dashboard function
2. Query data scoped to `resident.id`
3. Pass data to template: `render_template('dashboard.html', your_data=data)`
4. Edit `app/templates/dashboard.html` and add widget HTML
5. Use Jinja2 `{% if %}` to handle empty data

### Extend complaint model
1. Add column to `app/models/complaint.py`
2. Run migration: `flask db migrate -m "Add column"`
3. Run upgrade: `flask db upgrade`
4. Update `app/templates/resident/complaint_detail.html` to show new field

---

*Last updated: 2026-08-16*
