# Getting Started — 50 New Features

This guide helps you immediately test all 50 newly implemented features.

---

## Quick Start (5 Minutes)

### 1. Install Dependencies
```powershell
cd c:\Users\HP\Downloads\6
pip install -r requirements.txt
```

### 2. Start the App
```powershell
python run.py
```

App starts at: **http://127.0.0.1:5000**

### 3. Login as Resident
- Navigate to `/auth/login`
- Use resident credentials from your database
- You'll be redirected to the new dashboard

---

## Feature Tour (20 Minutes)

### 🏠 Dashboard (Features 1-10)
**URL:** `/dashboard`

**What to See:**
- **Metrics Grid**: 4 cards showing pending bills, overdue, total paid, active complaints
- **Overdue Alert**: Red banner if any bills are overdue
- **Due Countdown**: Widget showing "Due in X days" with progress bar
- **Last Payment Card**: Shows most recent payment with receipt link
- **Pending Months Timeline**: Visual dots for unpaid months
- **Recent Transactions**: Last 3 payments
- **Activity Stream**: Last 5 audit log entries
- **Quick Actions**: 4 CTA buttons (Pay Now, View Bills, Report Complaint, Invite Visitor)
- **Notifications Summary**: Unread count with priority icons

**How to Test:**
1. Login and observe the dashboard
2. Check if overdue banner appears (depends on your data)
3. Click "Pay Now" button → redirects to payment page
4. Click receipt number in Last Payment card → opens receipt page

---

### 💰 Bills (Features 11-20)
**URL:** `/resident/bills`

**What to See:**
- Bill list with status filters
- Click any bill → detailed bill page
- "How is my bill calculated?" info panel
- Late fee explanation (if overdue)
- **NEW:** "Download PDF" button
- **NEW:** "Yearly Summary" link in sidebar

**How to Test:**
1. Click "View Bills" from dashboard
2. Select any bill from the list
3. On bill detail page, click "Download PDF" → should download PDF
4. Click "Yearly Summary" in sidebar → see year-wise tabs
5. Switch between years to see historical data

**Routes:**
- `/resident/bills/<id>` — Bill detail
- `/resident/bills/<id>/pdf` — PDF download
- `/resident/payments/yearly` — Yearly summary

---

### 💳 Payments (Features 21-30)
**URL:** `/payments/pay/<bill_id>`

**What to See:**
- Razorpay payment form (UPI, Card, Netbanking, Wallet)
- Multi-month payment option
- After payment → confirmation page
- **NEW:** CSV export on payment history
- **NEW:** Enhanced refund status tracker

**How to Test:**
1. Click "Pay Now" on any pending bill
2. Complete payment (use Razorpay test mode if configured)
3. After success → see confirmation page
4. Go to `/payments/history`
5. Click "Export CSV" → downloads payment history
6. If you have refunds, visit `/payments/refund/<id>` to see 4-step timeline

**Routes:**
- `/payments/pay/<id>` — Payment page
- `/payments/success/<id>` — Success page
- `/resident/payments/export.csv` — CSV download
- `/payments/refund/<id>` — Refund status

---

### 🧾 Receipts (Features 31-35)
**URL:** `/resident/receipts`

**What to See:**
- Receipt list with inline view
- **NEW:** QR code button
- **NEW:** Share button (uses navigator.share or clipboard)

**How to Test:**
1. Click "Receipts" in sidebar
2. Click "View" on any receipt → inline display
3. Click "QR" → opens QR code image for verification
4. Click "Share" → tries navigator.share, falls back to clipboard

**Routes:**
- `/resident/receipts` — Receipt list
- `/resident/receipts/<id>/qr` — QR image
- `/payments/receipt/<id>` — Receipt PDF

---

### 🛠️ Complaints (Features 36-40)
**URL:** `/resident/complaints`

**What to See:**
- **NEW:** Complaint list with status cards (PENDING/IN_PROGRESS/RESOLVED/REJECTED)
- Click any complaint → full timeline with status history
- If complaint is RESOLVED → 5-star rating form appears

**How to Test:**
1. Click "Complaints" in sidebar
2. See all your complaints with status badges
3. Click any complaint → see full timeline
4. If complaint is RESOLVED, scroll down to "Rate Resolution"
5. Submit 5-star rating with feedback
6. Try rating again → should show "already rated" message

**Routes:**
- `/resident/complaints` — List
- `/resident/complaints/<id>` — Detail + timeline
- `/resident/complaints/<id>/rate` — Submit rating (POST)

---

### 👥 Visitors (Features 41-44)
**URL:** `/resident/visitors`

**What to See:**
- **NEW:** Visitor history with status filter
- **NEW:** "Invite Visitor" button
- Pass code shown in large QR modal
- **NEW:** Cancel button for pending passes

**How to Test:**
1. Click "Visitors" in sidebar
2. Click "Invite Visitor" button
3. Fill form:
   - Name: "John Doe"
   - Phone: "9876543210"
   - Purpose: "Personal visit"
   - Expected Time: Select date/time
4. Submit → redirects to visitor list with new pass
5. Click "View Pass" → modal shows large pass code (QR)
6. Click "Cancel" on any pass → marks pass as used

**Routes:**
- `/resident/visitors` — History
- `/resident/visitors/invite` — Invitation form (GET + POST)
- `/resident/visitors/<id>/cancel` — Cancel pass (POST)

---

### 🔔 Notifications (Features 45-46)
**URL:** `/resident/notifications`

**What to See:**
- Notification list with unread indicators
- **NEW:** "Mark All Read" button
- Category icons (bill, payment, complaint, visitor)

**How to Test:**
1. Click "Notifications" in sidebar
2. See unread count badge
3. Click "Mark All Read" → all notifications marked read
4. Click "Preferences" → manage notification channels (EMAIL/SMS/PUSH/IN_APP)

**Routes:**
- `/resident/notifications` — List
- `/resident/notifications/mark-all-read` — Bulk update (POST)
- `/resident/preferences` — Channel preferences

---

### 👤 Profile (Feature 47)
**URL:** `/resident/profile`

**What to See:**
- **NEW:** Profile completion percentage bar at top
- Missing fields highlighted (phone, alt_phone, profile_photo, etc.)
- Quick links to Security, Household, Yearly Summary

**How to Test:**
1. Click "Profile" in sidebar
2. Check completion percentage (calculated on 10 fields)
3. Missing fields show in red with "Add now" prompts
4. Update any field and refresh → percentage updates

**Routes:**
- `/resident/profile` — Profile page
- `/resident/change-password` — Password change

---

### 🔒 Security (Feature 48)
**URL:** `/resident/security`

**What to See:**
- **NEW:** Active sessions table (device, IP, last activity, current session marked)
- **NEW:** Login activity log (last 10 entries with timestamps)
- **NEW:** "Logout All Other Devices" button

**How to Test:**
1. Click "Security" in sidebar
2. See "Active Sessions" table
3. Current session has green "Current" badge
4. See "Login Activity" showing last 10 logins
5. Click "Logout All Other Devices" → invalidates other sessions (keeps current)

**Routes:**
- `/resident/security` — Sessions page
- `/resident/security/logout-all` — Logout others (POST)

---

### 🏠 Household (Feature 49)
**URL:** `/resident/household`

**What to See:**
- **NEW:** Dependents section with Add/Remove buttons
- **NEW:** Emergency Contacts section with Add/Remove buttons

**How to Test:**
1. Click "Household" in sidebar
2. See "Dependents" section
3. Click "Add Dependent" → fill form:
   - Name: "Jane Doe"
   - Relation: "Daughter"
   - DOB: Select date
   - Aadhar: "123456789012" (optional)
4. Submit → dependent added
5. Click "Remove" on any dependent → confirms and removes
6. Repeat for "Emergency Contacts":
   - Name: "Dr. Smith"
   - Phone: "9876543210"
   - Relation: "Family Doctor"
   - Address: "123 Main St"

**Routes:**
- `/resident/household` — View all
- `/resident/household/dependent/add` — Add dependent (POST)
- `/resident/household/dependent/<id>/remove` — Remove dependent (POST)
- `/resident/household/emergency/add` — Add emergency (POST)
- `/resident/household/emergency/<id>/remove` — Remove emergency (POST)

---

### 🔍 Search (Feature 50)
**URL:** `/resident/search`

**What to See:**
- Global search across announcements, documents, support requests

**How to Test:**
1. Click "Search" in sidebar
2. Enter search term (e.g., "maintenance")
3. See results from announcements, documents, support tickets

**Routes:**
- `/resident/search` — Search page

---

## Sidebar Navigation

All new pages are accessible from the expanded sidebar:

```
Resident Menu
├─ 🏠 Dashboard
├─ 📄 Bills
│   └─ Yearly Summary (NEW)
├─ 💳 Payments
│   └─ History
├─ 🧾 Receipts (ENHANCED)
├─ 🛠️ Complaints (NEW)
├─ 👥 Visitors (NEW)
├─ 🔔 Notifications (ENHANCED)
├─ 👤 Profile (ENHANCED)
├─ 🔒 Security (NEW)
├─ 🏠 Household (NEW)
├─ 📢 Announcements
├─ 📂 Documents
├─ 🆘 Support
├─ 🔍 Search
├─ 📊 Activity
└─ ⚙️ Preferences
```

---

## Testing Checklist

### Essential Tests (5 minutes)
- [ ] Dashboard loads with metrics
- [ ] Click "View Bills" → bill list appears
- [ ] Click any bill → "Download PDF" works
- [ ] Click "Yearly Summary" → year tabs appear
- [ ] Click "Complaints" → complaint list appears
- [ ] Click "Visitors" → visitor history appears
- [ ] Click "Security" → sessions table appears
- [ ] Click "Household" → dependents/emergency sections appear

### Detailed Tests (15 minutes)
- [ ] Dashboard countdown widget shows correct days
- [ ] Overdue alert appears if bills are overdue
- [ ] Bill detail shows "How calculated" panel
- [ ] PDF download generates valid PDF file
- [ ] Yearly summary groups payments by year
- [ ] CSV export downloads payment data
- [ ] Refund status shows 4-step timeline
- [ ] Receipt QR generates valid QR code
- [ ] Receipt share uses navigator.share
- [ ] Complaint detail shows full timeline
- [ ] Complaint rating saves and blocks duplicates
- [ ] Visitor invite creates new pass
- [ ] Visitor cancel marks pass as used
- [ ] Notification mark-all-read updates bulk
- [ ] Profile completion calculates percentage
- [ ] Security shows current session
- [ ] Logout-all invalidates other sessions
- [ ] Household add dependent works
- [ ] Household add emergency works
- [ ] Search returns results

### Security Tests (10 minutes)
- [ ] Try accessing another resident's bill → 403 error
- [ ] Try canceling another resident's visitor pass → 403 error
- [ ] Try removing another resident's dependent → 403 error
- [ ] Try rating another resident's complaint → 403 error
- [ ] Logout and try accessing /resident/* → redirects to login
- [ ] Verify Razorpay signature on payment (check server logs)

---

## Troubleshooting

### PDF Download Not Working
**Error:** "reportlab not installed"  
**Solution:**
```powershell
pip install reportlab
```

### QR Code Not Showing
**Error:** "qrcode not installed"  
**Solution:**
```powershell
pip install qrcode[pil]
```

### Razorpay Payment Fails
**Error:** "Invalid API key"  
**Solution:** Check `.env` file has valid keys:
```
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
```

### 403 Error on Resident Routes
**Solution:** Check user in database has:
- `role = 'Resident'`
- `account_status = 'ACTIVE'`

### Dashboard Shows No Data
**Solution:** Seed database with test data:
```powershell
python seed.py
```

---

## Next Steps

1. **Deploy to Production**
   - Set production Razorpay keys in `.env`
   - Update `SECRET_KEY` in `.env`
   - Configure email settings for notifications
   - Set up HTTPS with SSL certificate

2. **Add Test Data**
   - Run `python seed.py` if available
   - Or manually add residents, bills, payments via admin panel

3. **Configure Notifications**
   - Set up email SMTP settings
   - Configure SMS gateway (if needed)
   - Test notification delivery

4. **Monitor Performance**
   - Check dashboard load time (should be <500ms)
   - Monitor CSV export for large datasets
   - Check PDF generation performance

5. **Train Users**
   - Share this guide with residents
   - Conduct demo session showing key features
   - Create video tutorials for complex flows

---

## Support

- **Documentation:** See `IMPLEMENTATION_SUMMARY.md` for full details
- **Developer Reference:** See `DEVELOPER_QUICK_REFERENCE.md` for code patterns
- **Feature Status:** See `USER_FEATURE_IMPLEMENTATION_STATUS.md` for all 50 features

---

**Happy Testing! 🎉**

All 50 features are ready to use. Start with the dashboard tour and explore from there.
