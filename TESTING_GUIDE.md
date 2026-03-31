# TradeWise — Comprehensive Testing Guide

This guide covers all testing workflows for the TradeWise platform, including manual test scenarios, API testing, database verification, and checklists for every feature.

---

## Table of Contents

1. [Test Environment Setup](#1-test-environment-setup)
2. [Authentication Flow](#2-authentication-flow)
3. [Pro-Trader Complete Flow](#3-pro-trader-complete-flow)
4. [Learner Complete Flow](#4-learner-complete-flow)
5. [Credit System Testing](#5-credit-system-testing)
6. [Subscription & Payment Testing](#6-subscription--payment-testing)
7. [Real-time Features Testing](#7-real-time-features-testing)
8. [Comments & Interaction Testing](#8-comments--interaction-testing)
9. [Flagging System Testing](#9-flagging-system-testing)
10. [Notifications Testing](#10-notifications-testing)
11. [Performance & Analytics Testing](#11-performance--analytics-testing)
12. [Profile & Settings Testing](#12-profile--settings-testing)
13. [Error Handling Testing](#13-error-handling-testing)
14. [Responsive Design Testing](#14-responsive-design-testing)
15. [Database Integrity Testing](#15-database-integrity-testing)
16. [Test Scenarios Checklists](#16-test-scenarios-checklists)
17. [Performance Checklist](#17-performance-checklist)
18. [Security Checklist](#18-security-checklist)

---

## 1. Test Environment Setup

### Prerequisites

Before running any tests, ensure the following are in place:

| Requirement | Version | Check Command |
|-------------|---------|---------------|
| Python | 3.8+ | `python3 --version` |
| pip | Any | `pip --version` |
| Git | Any | `git --version` |
| Node.js (optional) | 16+ | `node --version` |
| Supabase project | Active | Log in at supabase.com |
| Cashfree TEST account | Active | Log in at cashfree.com |

### Automated Test Suite (No External Services)

The backend test suite uses an **in-memory SQLite database** and does **not** require Supabase, Cashfree, or Redis:

```bash
cd backend
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install pytest pytest-cov

# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ -v --cov=app --cov-report=term-missing
```

Expected output:

```
tests/test_auth.py::TestRegister::test_register_success PASSED
tests/test_auth.py::TestRegister::test_register_duplicate_email PASSED
...
tests/test_learner.py::TestLearnerFeed::test_feed_requires_auth PASSED
...
```

### Manual Testing Setup

For manual end-to-end testing, you need both servers running:

**Terminal 1 — Backend:**
```bash
cd backend
source venv/bin/activate
cp .env.example .env      # then fill in real credentials
python run.py
```

**Terminal 2 — Pro-Trader Frontend:**
```bash
python3 -m http.server 3000 --directory frontend
```

**Terminal 3 — Learner Frontend:**
```bash
python3 -m http.server 8000 --directory frontend/learner
```

---

## 2. Authentication Flow

### 2.1 Pro-Trader Registration

**URL:** `http://localhost:8080/pages/auth.html`

1. Open the auth page and switch to the **Sign Up** tab
2. Enter valid email, strong password (8+ chars, upper + lower + digit), display name
3. Click **Create account**
4. Verify redirect to `pages/role-select.html`
5. Select **"I am an Experienced Trader"** and click Continue
6. Verify redirect to `frontend/pages/dashboard.html`

**Expected API call:**
```http
POST /api/auth/register
Content-Type: application/json

{
  "email": "protrader@example.com",
  "password": "SecurePass1",
  "display_name": "Ravi Kumar",
  "role": "pro_trader"
}
```

**Expected response (201):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": { "email": "protrader@example.com", "role": "pro_trader" }
}
```

### 2.2 Learner Registration

**URL:** `http://localhost:8080/pages/auth.html`

1. Open the auth page and switch to the **Sign Up** tab
2. Enter email, password, display name
3. Click **Create account**
4. Verify redirect to `pages/role-select.html`
5. Select **"I am a Public Trader"** and click Continue
6. Verify redirect to `pages/profile-setup.html`
7. Complete profile setup: select interests, experience level, accept disclaimer
8. Verify redirect to `frontend/learner/pages/dashboard.html` with **7 credits**

### 2.3 Login Tests

Test the following login scenarios:

| Test Case | Input | Expected Result |
|-----------|-------|-----------------|
| Valid credentials | Correct email + password | 200, tokens returned |
| Wrong password | Correct email, wrong password | 401 Unauthorized |
| Unknown email | Non-existent email | 401 Unauthorized |
| Missing fields | Email only | 400 Bad Request |
| Empty body | `{}` | 400 Bad Request |

### 2.4 Token Refresh

```bash
# Get tokens from login
LOGIN_RESP=$(curl -s -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass1"}')

ACCESS_TOKEN=$(echo $LOGIN_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH_TOKEN=$(echo $LOGIN_RESP | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

# Refresh access token
curl -X POST http://localhost:5000/api/auth/refresh-token \
  -H "Authorization: Bearer $REFRESH_TOKEN"
```

**Expected:** New `access_token` returned.

### 2.5 Auto-Logout on Invalid Token

1. Log in and note the `access_token`
2. Wait for token to expire (or manually modify it)
3. Make an API call with the expired token
4. Verify the frontend automatically redirects to login

### 2.6 Role-Based Access Control

```bash
# Get a learner token
LEARNER_TOKEN=<learner_access_token>

# Try to access pro-trader endpoint with learner token
curl -X POST http://localhost:5000/api/pro-trader/trades \
  -H "Authorization: Bearer $LEARNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"RELIANCE","direction":"buy","entry_price":2500,"stop_loss_price":2400,"target_price":2700,"technical_rationale":"A " * 55}'
```

**Expected:** `403 Forbidden`

---

## 3. Pro-Trader Complete Flow

### 3.1 Complete KYC

1. Log in as pro-trader
2. Navigate to **KYC Setup** (`/pages/kyc-setup.html`)
3. Upload Aadhaar/PAN document (JPEG/PNG/PDF, max 10 MB)
4. Enter bank account details (account number, IFSC, holder name)
5. Click **Submit for Review**
6. Verify status shows **Pending Review**

**API:**
```bash
# Upload document
curl -X POST http://localhost:5000/api/pro-trader/kyc/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "document=@/path/to/pan.jpg" \
  -F "document_type=pan"

# Submit for review
curl -X POST http://localhost:5000/api/pro-trader/kyc/submit-review \
  -H "Authorization: Bearer $TOKEN"
```

### 3.2 Post a Trade

1. Navigate to **Post Trade** (`/pages/post-trade.html`)
2. Fill in all fields:
   - **Symbol:** `NIFTY50`
   - **Direction:** Buy
   - **Entry Price:** `22850`
   - **Stop Loss:** `22800`
   - **Target Price:** `22950`
   - **Technical Rationale:** 50+ words describing the setup
3. Verify **RRR** auto-calculates to `(22950-22850) / (22850-22800)` = **2.00**
4. Upload chart image (optional)
5. Click **Post Trade**
6. Verify trade appears in **Active Trades** list

**Expected RRR formula:**
```
For BUY: RRR = (target_price - entry_price) / (entry_price - stop_loss)
For SELL: RRR = (entry_price - target_price) / (stop_loss - entry_price)
```

### 3.3 Close a Trade

1. Open **Active Trades** page
2. Find the open trade
3. Click **Close Trade**
4. Select outcome: **Target Hit** (WIN) or **Stop Loss Hit** (LOSS)
5. Confirm close

**Expected:** Trade status changes to `target_hit` or `sl_hit`; accuracy score recalculates.

### 3.4 Accuracy Score Verification

After closing trades, verify accuracy via API:

```bash
curl http://localhost:5000/api/pro-trader/analytics/accuracy \
  -H "Authorization: Bearer $TOKEN"
```

**Expected for 8 wins out of 10 trades:**
```json
{ "accuracy_score": 80.0, "total_trades": 10, "winning_trades": 8 }
```

### 3.5 Set Subscription Price

```bash
curl -X PUT http://localhost:5000/api/pro-trader/subscription-price \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price": 50000}'
```

Note: Price is in **paise** (₹1 = 100 paise). `50000` = ₹500.

---

## 4. Learner Complete Flow

### 4.1 Register and Profile Setup

1. Open `http://localhost:8080/pages/auth.html`
2. Sign up with email and password, then select **"I am a Public Trader"** on the role-select page
3. On profile setup page, select:
   - **Interests:** Nifty 50, Crypto
   - **Experience Level:** Beginner
   - Accept the **financial disclaimer**
4. Click **Save & Continue**
5. Verify dashboard shows **7 credits**

### 4.2 Browse the Trade Feed

1. Navigate to **Feed** (`/pages/feed.html`)
2. Verify trades from all pro-traders appear
3. Test filters:
   - **By Market:** Filter for Nifty 50
   - **By Pro-Trader:** Type a trader's name
   - **By Accuracy:** Select minimum accuracy score
   - **Newest First:** Verify sort order
4. Each trade card should show:
   - Pro-trader name and accuracy score
   - Symbol (e.g. NIFTY50)
   - RR Ratio
   - Direction, SL, Target, Chart: **BLURRED**

### 4.3 Unlock a Trade

1. Find a trade card with blurred details
2. Click **"View Analysis (1 credit)"**
3. Verify credit deducts from 7 → 6
4. Verify trade card unblurs to show:
   - Direction (BUY/SELL)
   - Entry price
   - Stop loss
   - Target
   - Chart image (if uploaded)
   - Full technical rationale

### 4.4 Post a Comment

1. On an unlocked trade detail page
2. Type a question in the comment box
3. Click **Post Comment**
4. Verify comment appears instantly
5. Pro-trader logs in and replies
6. Verify reply appears in the learner's comment thread

### 4.5 Rate a Trade

1. On an unlocked trade
2. Click the star rating (1–5 stars)
3. Click **Submit Rating**
4. Verify average rating updates on the trade card

### 4.6 Subscribe to a Pro-Trader

1. On a trade card with 0 credits remaining (or click **Subscribe** button)
2. Verify Cashfree payment form appears
3. Enter test card details:
   - **Card Number:** `4111111111111111`
   - **Expiry:** Any future date (e.g. `12/26`)
   - **CVV:** Any 3 digits (e.g. `123`)
4. Click **Pay ₹500**
5. Verify success page appears
6. Verify subscription created in database
7. Navigate to the subscribed pro-trader's other trades
8. Verify they open **without** credit deduction

### 4.7 View My History

1. Navigate to **My History** (`/pages/my-history.html`)
2. Verify all unlocked trades are listed
3. Verify all subscribed pro-traders are shown
4. Verify learning progress charts display:
   - Trades unlocked per week
   - Market distribution (which markets you've studied)

---

## 5. Credit System Testing

### 5.1 Initial Credit Verification

After learner signup, query the database:

```sql
SELECT credits FROM profiles WHERE id = '<learner_uuid>';
-- Expected: 7
```

Or via API:
```bash
curl http://localhost:5000/api/learner/credits \
  -H "Authorization: Bearer $LEARNER_TOKEN"
# Expected: { "credits": 7 }
```

### 5.2 Credit Deduction on Unlock

| Action | Credits Before | Credits After |
|--------|---------------|--------------|
| Initial signup | — | 7 |
| Unlock trade 1 | 7 | 6 |
| Unlock trade 2 | 6 | 5 |
| Unlock trade 3 | 5 | 4 |
| Unlock trade 4 | 4 | 3 |
| Unlock trade 5 | 3 | 2 |
| Unlock trade 6 | 2 | 1 |
| Unlock trade 7 | 1 | 0 |

### 5.3 Block Unlock with 0 Credits

```bash
# Attempt to unlock with 0 credits
curl -X POST http://localhost:5000/api/learner/trades/<trade_id>/unlock \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

**Expected:** `402 Payment Required`

```json
{
  "error": "Insufficient credits",
  "credits_remaining": 0
}
```

### 5.4 Subscription Bypasses Credit System

1. Subscribe to Pro-Trader A
2. Attempt to view Pro-Trader A's trades
3. Verify they open without credit deduction
4. Verify credits balance does **not** change
5. Attempt to view Pro-Trader B's trades (not subscribed)
6. Verify 1 credit is deducted as normal

### 5.5 Credit Log Verification

```bash
curl http://localhost:5000/api/learner/credits/log \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

**Expected:** List of all credit transactions with timestamps.

---

## 6. Subscription & Payment Testing

### 6.1 Initiate Subscription

1. Go to a pro-trader's profile or trade card
2. Click **Subscribe to [Pro-Trader Name]**
3. Verify Cashfree payment form loads with correct amount

### 6.2 Complete Test Payment

Use Cashfree's sandbox test credentials:

| Field | Test Value |
|-------|-----------|
| Card Number | `4111111111111111` |
| Expiry Month/Year | Any future date |
| CVV | Any 3 digits |
| Name | Any name |

### 6.3 Verify Subscription Created

After successful payment, check the database:

```sql
SELECT * FROM subscriptions
WHERE learner_id = '<learner_uuid>'
AND pro_trader_id = '<trader_uuid>'
ORDER BY created_at DESC
LIMIT 1;
```

**Expected fields:**
- `status`: `active`
- `start_date`: today
- `end_date`: ~30 days from today
- `amount`: subscription price in paise

### 6.4 Revenue Split Verification

```sql
SELECT * FROM revenue_splits
WHERE payment_id = '<payment_uuid>';
```

**Expected:**
- `platform_amount`: 10% of payment
- `trader_amount`: 90% of payment

### 6.5 Test Unsubscribe

```bash
curl -X DELETE http://localhost:5000/api/learner/subscriptions/<subscription_id> \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

**Expected:** Subscription status → `cancelled`

### 6.6 Resubscribe After Cancellation

1. After cancelling, attempt to subscribe again
2. Verify new subscription is created
3. Verify access restored

---

## 7. Real-time Features Testing

> **Note:** Real-time features require Supabase Realtime to be enabled in your Supabase project dashboard.

### 7.1 Live Trade Updates

**Setup:** Open two browser windows side by side.
- Window 1: Pro-Trader dashboard
- Window 2: Learner trade feed (must have an unlocked or subscribed trade visible)

**Test:**
1. Pro-Trader closes a trade in Window 1 (marks as Target Hit)
2. Verify Window 2 updates the trade status **without page refresh**
3. Verify a notification bell appears in Window 2

### 7.2 Live Comment Updates

1. Window 1: Learner posts a comment on a trade
2. Window 2: Pro-Trader viewing the same trade
3. Verify comment appears in Window 2 instantly

### 7.3 New Trade Broadcast

1. Window 1: Pro-Trader posts a new trade
2. Window 2: Learner feed page
3. Verify new trade card appears at the top of the feed

### 7.4 Verifying Supabase Realtime

Check browser console for connection logs:

```javascript
// Open browser DevTools → Console
// Should see:
// "Supabase Realtime connected"
// "Subscribed to trades channel"
// "Subscribed to notifications channel"
```

---

## 8. Comments & Interaction Testing

### 8.1 Learner Posts Comment

```bash
curl -X POST http://localhost:5000/api/learner/trades/<trade_id>/comments \
  -H "Authorization: Bearer $LEARNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "What is your stop loss rationale?"}'
```

**Expected:** `201 Created`

### 8.2 Pro-Trader Replies

```bash
curl -X POST http://localhost:5000/api/pro-trader/trades/<trade_id>/comments \
  -H "Authorization: Bearer $TRADER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Stop loss placed just below the support zone."}'
```

### 8.3 Edit and Delete Own Comment

```bash
# Edit
curl -X PUT http://localhost:5000/api/learner/trades/<trade_id>/comments/<comment_id> \
  -H "Authorization: Bearer $LEARNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Edited: What is the support level here?"}'

# Delete
curl -X DELETE http://localhost:5000/api/learner/trades/<trade_id>/comments/<comment_id> \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

### 8.4 Authorization: Cannot Edit Others' Comments

```bash
# Pro-trader tries to edit learner's comment — should fail
curl -X PUT http://localhost:5000/api/pro-trader/trades/<trade_id>/comments/<learner_comment_id> \
  -H "Authorization: Bearer $TRADER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"content": "Edited by trader"}'
```

**Expected:** `403 Forbidden`

---

## 9. Flagging System Testing

### 9.1 Learner Flags a Trade

```bash
curl -X POST http://localhost:5000/api/learner/trades/<trade_id>/flag \
  -H "Authorization: Bearer $LEARNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Suspicious entry price — market was halted at this time."}'
```

**Expected:** `201 Created`

### 9.2 Verify Flag Count in Database

```sql
SELECT COUNT(*) as flag_count FROM flags WHERE trade_id = '<trade_uuid>';
```

### 9.3 Multiple Learners Flag Same Trade

Repeat Step 9.1 with 9 different learner accounts. After the 10th flag:

- Admin receives an alert notification
- Trade is marked for review on the admin panel
- Pro-trader receives accuracy penalty (5% deduction, admin-configurable)

### 9.4 Admin Action

When admin investigates and takes action, the learner who flagged receives a notification about the resolution.

---

## 10. Notifications Testing

### 10.1 Event-Triggered Notifications

| Event | Who Gets Notified |
|-------|------------------|
| New trade posted | All subscribers of that pro-trader |
| Trade closed | All learners who unlocked that trade |
| Subscription expiring in 3 days | The learner with the expiring subscription |
| Flag report resolved | The learner who submitted the flag |

### 10.2 Get Notifications

```bash
curl http://localhost:5000/api/learner/notifications \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

### 10.3 Mark as Read

```bash
curl -X PUT http://localhost:5000/api/learner/notifications/<notification_id>/read \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

### 10.4 Delete Notification

```bash
curl -X DELETE http://localhost:5000/api/learner/notifications/<notification_id> \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

### 10.5 Clear All Notifications

```bash
curl -X POST http://localhost:5000/api/learner/notifications/clear-all \
  -H "Authorization: Bearer $LEARNER_TOKEN"
```

### 10.6 Verify Unread Count Updates

1. Check unread count before marking as read
2. Mark one notification as read
3. Verify unread count decreases by 1 in the notification bell icon

---

## 11. Performance & Analytics Testing

### 11.1 Accuracy Score Calculation

Create exactly 10 trades and close them with 8 wins and 2 losses:

```bash
# Close as WIN (target hit)
curl -X PUT http://localhost:5000/api/pro-trader/trades/<id>/close \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"outcome":"win"}' -H "Content-Type: application/json"

# Close as LOSS (SL hit)
curl -X PUT http://localhost:5000/api/pro-trader/trades/<id>/close \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"outcome":"loss"}' -H "Content-Type: application/json"
```

Verify accuracy:
```bash
curl http://localhost:5000/api/pro-trader/analytics/accuracy \
  -H "Authorization: Bearer $TOKEN"
# Expected: { "accuracy_score": 80.0 }
```

### 11.2 Performance Charts

Navigate to **Analytics** page (`/pages/analytics.html`) and verify:

- [ ] 12-month accuracy trend line chart renders
- [ ] Win/Loss doughnut chart shows correct counts
- [ ] Monthly earnings bar chart displays
- [ ] RRR distribution histogram appears

### 11.3 Learner Progress Charts

Navigate to **My History** (`/pages/my-history.html`) and verify:

- [ ] Trades unlocked per week chart
- [ ] Market distribution pie chart (Nifty, Crypto, Forex etc.)

### 11.4 Leaderboard Rankings

After closing trades, verify the pro-trader's leaderboard position updates based on their accuracy score.

---

## 12. Profile & Settings Testing

### 12.1 Edit Profile

```bash
curl -X PUT http://localhost:5000/api/pro-trader/profile \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "bio": "Experienced NIFTY and crypto trader with 7 years in technical analysis. Focus on swing trading and breakout strategies using price action.",
    "specializations": ["nifty50", "crypto"],
    "years_of_experience": 7,
    "trading_style": "swing"
  }'
```

**Note:** Bio must be at least 100 characters.

### 12.2 Upload Avatar

```bash
curl -X PUT http://localhost:5000/api/pro-trader/profile/picture \
  -H "Authorization: Bearer $TOKEN" \
  -F "picture=@/path/to/avatar.jpg"
```

### 12.3 Change Password

```bash
curl -X POST http://localhost:5000/api/pro-trader/change-password \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"current_password": "OldPass1", "new_password": "NewSecurePass1"}'
```

### 12.4 Notification Preferences

```bash
# Get preferences
curl http://localhost:5000/api/pro-trader/notification-preferences \
  -H "Authorization: Bearer $TOKEN"

# Update preferences
curl -X PUT http://localhost:5000/api/pro-trader/notification-preferences \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email_new_subscriber": true,
    "email_trade_comment": true,
    "push_new_subscriber": false,
    "push_trade_comment": true
  }'
```

### 12.5 View Login Activity

```bash
curl http://localhost:5000/api/pro-trader/login-activity \
  -H "Authorization: Bearer $TOKEN"
```

---

## 13. Error Handling Testing

Test each error scenario and verify the correct HTTP status code and user-friendly error message:

### HTTP Status Code Reference

| Error Scenario | Expected Status | Expected Body |
|---------------|----------------|---------------|
| Invalid email format | 400 | `{"error": "Invalid email format"}` |
| Duplicate email on signup | 409 | `{"error": "Email already registered"}` |
| Missing required field | 400 | `{"error": "Field X is required"}` |
| No JWT token | 401 | `{"error": "Missing authorization token"}` |
| Expired JWT token | 401 | `{"error": "Token has expired"}` |
| Access another user's data | 403 | `{"error": "Forbidden"}` |
| Trade not found | 404 | `{"error": "Trade not found"}` |
| Unlock with 0 credits | 402 | `{"error": "Insufficient credits"}` |
| Short bio (< 100 chars) | 400 | `{"error": "Bio must be at least 100 characters"}` |
| Short rationale (< 50 words) | 400 | `{"error": "Rationale must be at least 50 words"}` |
| Invalid trade direction | 400 | `{"error": "Direction must be buy or sell"}` |
| SL above entry for BUY | 400 | `{"error": "Stop loss must be below entry for BUY trades"}` |

### Testing Error Scenarios

```bash
# Test 1: Invalid email
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"notanemail","password":"TestPass1","role":"pro_trader"}'
# Expected: 400

# Test 2: Duplicate email
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dup@example.com","password":"TestPass1","role":"pro_trader"}'
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"dup@example.com","password":"TestPass1","role":"pro_trader"}'
# Second call: Expected 409

# Test 3: No token
curl http://localhost:5000/api/pro-trader/profile
# Expected: 401

# Test 4: 0 credits unlock
curl -X POST http://localhost:5000/api/learner/trades/<id>/unlock \
  -H "Authorization: Bearer $ZERO_CREDIT_LEARNER_TOKEN"
# Expected: 402
```

---

## 14. Responsive Design Testing

### 14.1 Viewport Test Sizes

| Device | Width × Height | Test via Chrome DevTools |
|--------|---------------|--------------------------|
| Desktop | 1920 × 1080 | Default |
| Laptop | 1280 × 800 | Responsive mode |
| Tablet | 768 × 1024 | DevTools iPad |
| Mobile | 375 × 667 | DevTools iPhone SE |

### 14.2 Mobile Testing Checklist

Open Chrome DevTools (F12) → Toggle Device Toolbar:

- [ ] Hamburger menu appears on mobile (≤ 480px)
- [ ] Sidebar collapses to a drawer
- [ ] Touch targets are at least 44 × 44px
- [ ] No horizontal scroll on any page
- [ ] Trade cards stack vertically (not side by side)
- [ ] Images resize correctly
- [ ] Text remains readable (min 14px)
- [ ] Buttons and forms are accessible on small screens
- [ ] Charts resize without overflowing containers

### 14.3 Cross-Browser Testing

Test on:
- [ ] Chrome (latest)
- [ ] Firefox (latest)
- [ ] Safari (macOS/iOS)
- [ ] Edge (latest)

---

## 15. Database Integrity Testing

After running through the full scenario, verify the database state in Supabase:

### 15.1 Verify Learner Profile

```sql
SELECT id, full_name, role, credits, disclaimer_accepted
FROM profiles
WHERE id = '<learner_uuid>';
-- Expected: credits started at 7, decremented for each unlock
```

### 15.2 Verify Trade Records

```sql
SELECT * FROM trades WHERE mentor_id = '<trader_uuid>';
-- All required fields should be populated
-- trade_status: ACTIVE, WIN, or LOSS
```

### 15.3 Verify Unlock Records

```sql
SELECT * FROM unlocked_trades
WHERE user_id = '<learner_uuid>'
ORDER BY unlocked_at DESC;
-- One row per unlocked trade
```

### 15.4 Verify Subscription Records

```sql
SELECT * FROM subscriptions
WHERE learner_id = '<learner_uuid>';
-- status: active/cancelled
-- start_date and end_date populated
```

### 15.5 Verify Revenue Split

```sql
SELECT * FROM revenue_splits
WHERE payment_id = '<payment_uuid>';
-- platform_amount = total * 0.10
-- trader_amount = total * 0.90
```

### 15.6 Verify Notifications

```sql
SELECT * FROM notifications
WHERE user_id = '<learner_uuid>'
ORDER BY created_at DESC;
-- Check that all expected events created notifications
```

### 15.7 Verify Flag Records

```sql
SELECT trade_id, COUNT(*) as flag_count
FROM flags
GROUP BY trade_id
HAVING COUNT(*) >= 5;
-- Trades with high flag counts should be under review
```

### 15.8 Verify Mentor Stats

```sql
SELECT * FROM mentor_stats WHERE mentor_id = '<trader_uuid>';
-- accuracy_pct should match (winning_trades / total_trades) * 100
```

---

## 16. Test Scenarios Checklists

### Pro-Trader Scenario

- [ ] Sign up as pro-trader with email
- [ ] Complete KYC (upload Aadhaar / PAN document)
- [ ] Add bank details for payouts (account number + IFSC)
- [ ] Post trading idea: Symbol=`NIFTY50`, Direction=Buy, Entry=`22850`, SL=`22800`, Target=`22950`
- [ ] Verify RRR auto-calculates correctly: `(22950-22850)/(22850-22800)` = `2.00`
- [ ] Upload chart image (optional)
- [ ] Write technical rationale (50+ words)
- [ ] Verify trade appears on learner feed within 5 seconds
- [ ] View subscriber notifications
- [ ] Close trade as **Target Hit**
- [ ] Verify accuracy updated: `1/1 = 100%`
- [ ] View performance dashboard with charts
- [ ] Set subscription price: ₹500/month (`50000` paise)
- [ ] Verify earnings dashboard shows revenue after a learner subscribes

### Learner Scenario

- [ ] Sign up as learner with email
- [ ] Select interests: Nifty 50, Crypto
- [ ] Select experience level: Beginner
- [ ] Accept financial disclaimer
- [ ] View dashboard showing **7 credits**
- [ ] Navigate to trade feed
- [ ] Filter feed by Nifty 50
- [ ] See pro-trader's trade card with blurred details
- [ ] Click **"View Analysis (1 credit)"**
- [ ] Verify content unblurs (direction, SL, target, chart, rationale visible)
- [ ] Verify credits show **6**
- [ ] Post a comment asking a question on the trade
- [ ] See pro-trader's reply appear
- [ ] Rate trade with **5 stars**
- [ ] Click **Subscribe** button
- [ ] Enter test payment info (card: `4111111111111111`)
- [ ] Verify subscription shows as **active**
- [ ] View another trade from the subscribed pro-trader (no credit deduction)
- [ ] Verify credits remain at **6** (not deducted)
- [ ] View **My History** page with progress charts
- [ ] Check **My Subscriptions** page shows active subscription

### Payment Scenario

- [ ] Learner has 0 credits remaining
- [ ] Click **"View Analysis"** → receives **402 error** with clear message
- [ ] Click **"Subscribe to [Pro-Trader]"** instead
- [ ] Cashfree payment form loads with correct price
- [ ] Enter test card: `4111111111111111`, any future expiry, any CVV
- [ ] Click **Pay**
- [ ] Success message/page shown
- [ ] Subscription created in database with `status=active`
- [ ] All trades from this pro-trader now unlock without credit
- [ ] Verify ₹500 split: ₹450 credited to trader wallet, ₹50 platform fee

---

## 17. Performance Checklist

- [ ] Feed page loads in < 2 seconds (with 50+ trades)
- [ ] Trade detail page loads in < 1 second
- [ ] Analytics charts render within 2 seconds
- [ ] Charts animate smoothly (no visible jank)
- [ ] API responses return in < 500ms (local)
- [ ] No console errors in browser DevTools
- [ ] No memory leaks — check Memory tab in DevTools after 10 minutes of use
- [ ] Images are lazy-loaded (check Network tab)
- [ ] Pagination works correctly for feeds with many trades
- [ ] Realtime updates don't cause layout shifts

---

## 18. Security Checklist

- [ ] Passwords hashed with **bcrypt** (never stored in plaintext)
- [ ] JWT tokens use **HS256** algorithm with a secure secret key
- [ ] HTTPS enforced in production (not needed for localhost)
- [ ] CORS is restricted to the configured `FRONTEND_URL`
- [ ] SQL injection prevented — using SQLAlchemy ORM (prepared statements)
- [ ] XSS prevented — frontend sanitizes user input before rendering
- [ ] File uploads validated: type (JPEG/PNG/PDF only) and size (max 10 MB)
- [ ] Bank account numbers encrypted with Fernet encryption at rest
- [ ] API rate limiting implemented for auth endpoints
- [ ] JWT tokens are short-lived (1 hour default) with refresh rotation
- [ ] Webhook signatures verified (Cashfree webhook secret)
- [ ] Row Level Security (RLS) policies applied in Supabase (see `supabase/rls-policies.sql`)
- [ ] No secrets committed to source code (using `.env` files)
- [ ] `.env` is listed in `.gitignore`

---

## Quick Reference: Test Credentials

For manual testing, create the following accounts:

| Account | Email | Password | Notes |
|---------|-------|----------|-------|
| Pro-Trader 1 | `trader1@test.com` | `TestPass1` | Post trades, set ₹500/month |
| Pro-Trader 2 | `trader2@test.com` | `TestPass1` | For subscription comparison |
| Learner 1 | `learner1@test.com` | `TestPass1` | Fresh account, 7 credits |
| Learner 2 | `learner2@test.com` | `TestPass1` | Exhaust credits, test 402 |

**Cashfree Test Card:**

| Field | Value |
|-------|-------|
| Card Number | `4111 1111 1111 1111` |
| Expiry | Any future date |
| CVV | Any 3 digits |
| Name | Any name |

---

## Automated Test Execution Summary

```bash
cd backend
source venv/bin/activate
pytest tests/ -v --tb=short 2>&1 | tee /tmp/test_results.txt

# Review results
grep -E "PASSED|FAILED|ERROR" /tmp/test_results.txt
```

All tests should pass. Any `FAILED` or `ERROR` indicates a configuration or code issue — check the traceback for details.
