# TradeWise — API Documentation

Complete reference for all API endpoints in the TradeWise backend.

**Base URL (local):** `http://localhost:5000/api`

**Authentication:** All protected endpoints require a `Bearer` token in the `Authorization` header:

```http
Authorization: Bearer <access_token>
```

---

## Table of Contents

1. [Authentication](#1-authentication)
2. [Pro-Trader Profile](#2-pro-trader-profile)
3. [Trades (Pro-Trader)](#3-trades-pro-trader)
4. [Comments (Pro-Trader)](#4-comments-pro-trader)
5. [Analytics](#5-analytics)
6. [Earnings & Payouts](#6-earnings--payouts)
7. [Subscribers](#7-subscribers)
8. [KYC & Bank Details](#8-kyc--bank-details)
9. [Account Settings & Security](#9-account-settings--security)
10. [Notifications (Pro-Trader)](#10-notifications-pro-trader)
11. [Exports](#11-exports)
12. [Learner Feed](#12-learner-feed)
13. [Learner Credits](#13-learner-credits)
14. [Learner Subscriptions](#14-learner-subscriptions)
15. [Learner Comments](#15-learner-comments)
16. [Learner Ratings](#16-learner-ratings)
17. [Learner Flags](#17-learner-flags)
18. [Learner Notifications](#18-learner-notifications)
19. [Learner Profile](#19-learner-profile)
20. [Webhooks](#20-webhooks)

---

## 1. Authentication

**Prefix:** `/api/auth`

### POST `/register`

Register a new user (pro-trader or learner).

**Request body:**
```json
{
  "email": "trader@example.com",
  "password": "SecurePass1",
  "display_name": "Ravi Kumar",
  "role": "pro_trader"
}
```

| Field | Type | Required | Validation |
|-------|------|----------|------------|
| `email` | string | Yes | Valid email format |
| `password` | string | Yes | Min 8 chars, upper + lower + digit |
| `display_name` | string | No | — |
| `role` | string | Yes | `pro_trader` or `learner` |

**Response 201:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": {
    "id": "uuid",
    "email": "trader@example.com",
    "role": "pro_trader"
  }
}
```

**Errors:** `400` (validation), `409` (duplicate email)

---

### POST `/login`

Authenticate and receive JWT tokens.

**Request body:**
```json
{
  "email": "trader@example.com",
  "password": "SecurePass1",
  "totp_code": "123456"
}
```

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `email` | string | Yes | — |
| `password` | string | Yes | — |
| `totp_code` | string | No | Required only if 2FA is enabled |

**Response 200:**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "user": { "id": "uuid", "email": "trader@example.com", "role": "pro_trader" }
}
```

**Errors:** `400` (missing fields), `401` (invalid credentials)

---

### POST `/logout`

🔐 Requires auth.

Invalidates the current access token.

**Response 200:**
```json
{ "message": "Logged out successfully" }
```

---

### POST `/refresh-token`

Exchange a refresh token for a new access token.

**Headers:** `Authorization: Bearer <refresh_token>`

**Response 200:**
```json
{ "access_token": "eyJ..." }
```

**Errors:** `401` (invalid or expired refresh token)

---

### POST `/google-auth`

Authenticate via Google OAuth token.

**Request body:**
```json
{ "google_token": "google-id-token-here" }
```

---

### POST `/2fa-setup`

🔐 Requires auth. Generate a TOTP secret and QR code.

**Response 200:**
```json
{
  "secret": "BASE32SECRET",
  "qr_code_url": "data:image/png;base64,..."
}
```

---

### POST `/2fa-verify`

🔐 Requires auth. Enable 2FA with a TOTP code.

**Request body:**
```json
{ "totp_code": "123456" }
```

---

### POST `/2fa-disable`

🔐 Requires auth. Disable 2FA.

**Request body:**
```json
{ "totp_code": "123456" }
```

---

## 2. Pro-Trader Profile

**Prefix:** `/api/pro-trader`

### GET `/profile`

🔐 Requires pro-trader auth.

**Response 200:**
```json
{
  "id": "uuid",
  "display_name": "Ravi Kumar",
  "bio": "7 years of technical analysis experience...",
  "specializations": ["nifty50", "crypto"],
  "years_of_experience": 7,
  "trading_style": "swing",
  "accuracy_score": 78.5,
  "subscription_price": 50000,
  "avatar_url": "https://..."
}
```

---

### PUT `/profile`

🔐 Requires pro-trader auth.

**Request body:**
```json
{
  "bio": "7 years of technical analysis... (100+ chars required)",
  "specializations": ["nifty50", "crypto"],
  "years_of_experience": 7,
  "trading_style": "swing"
}
```

**Errors:** `400` if bio is shorter than 100 characters

---

### PUT `/profile/picture`

🔐 Requires pro-trader auth. Multipart form upload.

**Form fields:**
- `picture`: image file (JPEG/PNG, max 10 MB)

---

### GET `/dashboard`

🔐 Requires pro-trader auth.

**Response 200:**
```json
{
  "accuracy_score": 78.5,
  "total_trades": 20,
  "winning_trades": 16,
  "total_subscribers": 45,
  "monthly_earnings": 22500.00,
  "active_trades_count": 3
}
```

---

## 3. Trades (Pro-Trader)

**Prefix:** `/api/pro-trader`

### POST `/trades`

🔐 Requires pro-trader auth. Create a new trade signal.

**Request body:**
```json
{
  "symbol": "NIFTY50",
  "direction": "buy",
  "entry_price": 22850.0,
  "stop_loss_price": 22800.0,
  "target_price": 22950.0,
  "technical_rationale": "NIFTY50 has formed a cup-and-handle pattern... (min 50 words)",
  "chart_image_url": "https://supabase-storage-url/chart.png"
}
```

| Field | Validation |
|-------|------------|
| `symbol` | Required |
| `direction` | `buy` or `sell` |
| `entry_price` | Positive number |
| `stop_loss_price` | For BUY: must be < `entry_price`. For SELL: must be > `entry_price` |
| `target_price` | For BUY: must be > `entry_price`. For SELL: must be < `entry_price` |
| `technical_rationale` | Minimum 50 words |

**Response 201:**
```json
{
  "trade": {
    "id": "uuid",
    "symbol": "NIFTY50",
    "direction": "buy",
    "entry_price": "22850.00",
    "stop_loss_price": "22800.00",
    "target_price": "22950.00",
    "rrr": "2.00",
    "status": "active",
    "created_at": "2026-03-24T10:00:00Z"
  }
}
```

---

### GET `/trades`

🔐 Requires pro-trader auth. List all trades (paginated).

**Query parameters:**

| Param | Type | Default | Description |
|-------|------|---------|-------------|
| `page` | int | 1 | Page number |
| `per_page` | int | 20 | Results per page |
| `status` | string | all | `active`, `target_hit`, `sl_hit`, `cancelled` |

---

### GET `/trades/{id}`

🔐 Requires pro-trader auth. Get single trade details.

**Errors:** `404` if not found

---

### PUT `/trades/{id}/close`

🔐 Requires pro-trader auth. Close an active trade.

**Request body:**
```json
{ "outcome": "win" }
```

`outcome` must be `win` (target hit) or `loss` (SL hit).

**Response 200:**
```json
{
  "trade": {
    "id": "uuid",
    "status": "target_hit",
    "closed_at": "2026-03-24T15:30:00Z"
  },
  "new_accuracy_score": 80.0
}
```

---

### DELETE `/trades/{id}`

🔐 Requires pro-trader auth. Cancel an active trade.

**Response 200:**
```json
{ "message": "Trade cancelled successfully" }
```

---

## 4. Comments (Pro-Trader)

**Prefix:** `/api/pro-trader/trades/{trade_id}`

### GET `/comments`

🔐 Requires auth. Get comments on a trade (paginated).

**Query:** `page`, `per_page`

---

### POST `/comments`

🔐 Requires auth. Post a comment.

**Request body:**
```json
{ "content": "This setup looks clean. Entry on breakout above resistance." }
```

---

### PUT `/comments/{comment_id}`

🔐 Requires auth. Edit own comment.

**Errors:** `403` if trying to edit another user's comment

---

### DELETE `/comments/{comment_id}`

🔐 Requires auth. Delete own comment.

**Errors:** `403` if trying to delete another user's comment

---

## 5. Analytics

**Prefix:** `/api/pro-trader/analytics`

### GET `/accuracy`

**Response 200:**
```json
{
  "accuracy_score": 80.0,
  "total_trades": 10,
  "winning_trades": 8,
  "losing_trades": 2
}
```

---

### GET `/performance-chart`

12-month accuracy trend for line chart.

**Response 200:**
```json
{
  "months": ["Apr 2025", "May 2025", ...],
  "accuracy": [72.0, 75.5, 80.0, ...]
}
```

---

### GET `/win-loss`

Win/loss counts for doughnut chart.

**Response 200:**
```json
{ "wins": 8, "losses": 2 }
```

---

### GET `/rrr`

Average risk-reward ratio.

**Response 200:**
```json
{ "average_rrr": 2.35 }
```

---

### GET `/monthly-stats`

Monthly performance breakdown.

**Response 200:**
```json
{
  "months": ["Jan", "Feb", ...],
  "trades": [5, 8, ...],
  "wins": [4, 7, ...]
}
```

---

### GET `/trade-history`

Paginated list of closed trades with outcome and RRR.

---

## 6. Earnings & Payouts

**Prefix:** `/api/pro-trader`

### GET `/earnings`

**Response 200:**
```json
{
  "total_earnings": 45000.00,
  "monthly_earnings": 9000.00,
  "pending_payouts": 5000.00
}
```

---

### GET `/subscription-price`

**Response 200:**
```json
{ "price": 50000, "price_formatted": "₹500" }
```

---

### PUT `/subscription-price`

**Request body:**
```json
{ "price": 50000 }
```

Price is in **paise** (₹500 = 50000 paise). Minimum: ₹99.

---

### GET `/balance`

Available balance for withdrawal.

**Response 200:**
```json
{ "available_balance": 22500.00 }
```

---

### GET `/payouts`

Payout history.

---

### POST `/payouts/initiate`

Initiate a withdrawal.

**Request body:**
```json
{ "amount": 5000.00 }
```

Requires: KYC verified, bank details set, balance ≥ `MIN_WITHDRAWAL_AMOUNT` (₹500).

---

### GET `/payouts/{id}/status`

Check payout status.

**Response 200:**
```json
{
  "status": "processing",
  "amount": 5000.00,
  "initiated_at": "2026-03-24T10:00:00Z"
}
```

---

## 7. Subscribers

**Prefix:** `/api/pro-trader`

### GET `/subscribers`

🔐 Requires pro-trader auth. List active subscribers.

**Response 200:**
```json
{
  "subscribers": [
    {
      "id": "uuid",
      "display_name": "Learner Name",
      "subscribed_since": "2026-02-01T00:00:00Z",
      "status": "active"
    }
  ],
  "total": 45
}
```

---

### GET `/subscribers/stats`

**Response 200:**
```json
{
  "total_active": 45,
  "new_this_month": 8,
  "churned_this_month": 2
}
```

---

### POST `/subscribers/notify`

🔐 Requires pro-trader auth. Broadcast message to all subscribers.

**Request body:**
```json
{ "message": "New trade posted: NIFTY50 BUY setup" }
```

---

## 8. KYC & Bank Details

**Prefix:** `/api/pro-trader/kyc`

### GET `/kyc/status`

**Response 200:**
```json
{
  "kyc_status": "pending_review",
  "documents_uploaded": 2,
  "bank_details_set": true
}
```

Status values: `not_started`, `documents_uploaded`, `pending_review`, `approved`, `rejected`

---

### POST `/kyc/documents/upload`

Multipart form upload.

**Form fields:**
- `document`: File (JPEG/PNG/PDF, max 10 MB)
- `document_type`: `aadhaar`, `pan`, `passport`, `voter_id`, `driving_license`, `bank_statement`

---

### GET `/kyc/documents`

List uploaded KYC documents.

---

### DELETE `/kyc/documents/{id}`

Delete a KYC document.

---

### GET `/bank-details`

Returns masked bank details (account number partially hidden).

**Response 200:**
```json
{
  "account_holder_name": "Ravi Kumar",
  "account_number_masked": "XXXXXXXXXX3456",
  "ifsc_code": "SBIN0001234",
  "bank_name": "State Bank of India"
}
```

---

### PUT `/bank-details`

**Request body:**
```json
{
  "bank_account_number": "1234567890123456",
  "ifsc_code": "SBIN0001234",
  "account_holder_name": "Ravi Kumar"
}
```

Account number is **encrypted** at rest using Fernet encryption.

---

### POST `/kyc/submit-review`

Submit KYC documents for admin review.

---

## 9. Account Settings & Security

**Prefix:** `/api/pro-trader`

### PUT `/account-settings`

Update display name, timezone, language.

**Request body:**
```json
{
  "display_name": "Ravi Kumar",
  "timezone": "Asia/Kolkata",
  "language": "en"
}
```

---

### POST `/change-password`

**Request body:**
```json
{
  "current_password": "OldPass1",
  "new_password": "NewSecurePass1"
}
```

---

### GET `/login-activity`

Paginated list of login events.

**Response 200:**
```json
{
  "activities": [
    {
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "login_at": "2026-03-24T09:00:00Z",
      "location": "Mumbai, India"
    }
  ]
}
```

---

### GET `/notification-preferences`

---

### PUT `/notification-preferences`

**Request body:**
```json
{
  "email_new_subscriber": true,
  "email_trade_comment": true,
  "email_payout_update": true,
  "push_new_subscriber": false,
  "push_trade_comment": true
}
```

---

### POST `/logout-sessions`

Log out all other active sessions.

---

## 10. Notifications (Pro-Trader)

**Prefix:** `/api/pro-trader`

### GET `/notifications`

**Query:** `page`, `per_page`, `unread_only=true`

**Response 200:**
```json
{
  "notifications": [
    {
      "id": "uuid",
      "type": "new_subscriber",
      "title": "New subscriber",
      "message": "Learner123 subscribed to your feed.",
      "is_read": false,
      "created_at": "2026-03-24T10:00:00Z"
    }
  ],
  "unread_count": 5
}
```

---

### PUT `/notifications/{id}/read`

Mark notification as read.

---

### DELETE `/notifications/{id}`

Delete a notification.

---

### POST `/notifications/clear-all`

Clear all notifications.

---

## 11. Exports

**Prefix:** `/api/pro-trader/reports`

### GET `/reports/export-csv`

Download trade history as CSV.

**Response:** `text/csv` attachment

---

### GET `/reports/export-pdf`

Download monthly performance report as PDF.

**Response:** `application/pdf` attachment

---

## 12. Learner Feed

**Prefix:** `/api/learner`

### GET `/feed`

🔐 Requires learner auth. Paginated trade feed from all pro-traders.

**Query parameters:**

| Param | Description |
|-------|-------------|
| `page` | Page number |
| `per_page` | Results per page (default 20) |
| `market` | Filter by market (e.g. `nifty50`, `crypto`, `forex`) |
| `pro_trader_name` | Search by trader display name |
| `min_accuracy` | Minimum accuracy score (0–100) |
| `sort` | `newest` (default) or `accuracy` |

**Response 200 — before unlock:**
```json
{
  "trades": [
    {
      "id": "uuid",
      "pro_trader_name": "Ravi Kumar",
      "accuracy_score": 80.0,
      "symbol": "NIFTY50",
      "rrr": "2.00",
      "status": "active",
      "is_unlocked": false,
      "direction": null,
      "entry_price": null,
      "stop_loss": null,
      "target_price": null,
      "chart_image_url": null,
      "technical_rationale": null
    }
  ],
  "total": 150,
  "credits_remaining": 7
}
```

After unlock, `is_unlocked: true` and all fields are populated.

---

### GET `/trades/{id}`

🔐 Requires learner auth. Get trade details (full if unlocked/subscribed, blurred otherwise).

---

### POST `/trades/{id}/unlock`

🔐 Requires learner auth. Unlock a trade using 1 credit.

**Response 200:**
```json
{
  "message": "Trade unlocked",
  "credits_remaining": 6,
  "trade": { /* full trade details */ }
}
```

**Errors:** `402` if credits = 0

---

### GET `/pro-traders`

🔐 Requires learner auth. Browse all pro-traders with stats.

---

### GET `/pro-traders/{id}`

🔐 Requires learner auth. Get pro-trader public profile.

---

## 13. Learner Credits

**Prefix:** `/api/learner`

### GET `/credits`

**Response 200:**
```json
{ "credits": 6 }
```

---

### GET `/credits/log`

Full transaction log.

**Response 200:**
```json
{
  "log": [
    {
      "id": "uuid",
      "type": "deduct",
      "amount": -1,
      "description": "Unlocked trade NIFTY50 by Ravi Kumar",
      "balance_after": 6,
      "created_at": "2026-03-24T10:00:00Z"
    }
  ]
}
```

---

## 14. Learner Subscriptions

**Prefix:** `/api/learner`

### GET `/subscriptions`

List active subscriptions.

**Response 200:**
```json
{
  "subscriptions": [
    {
      "id": "uuid",
      "pro_trader_id": "uuid",
      "pro_trader_name": "Ravi Kumar",
      "status": "active",
      "start_date": "2026-03-01",
      "end_date": "2026-04-01",
      "amount_paid": 50000
    }
  ]
}
```

---

### POST `/subscriptions`

Initiate a subscription payment via Cashfree.

**Request body:**
```json
{ "pro_trader_id": "uuid" }
```

**Response 200:**
```json
{
  "order_id": "order_xyz",
  "payment_session_id": "session_abc",
  "amount": 50000,
  "cashfree_checkout_url": "https://sandbox.cashfree.com/checkout/..."
}
```

---

### DELETE `/subscriptions/{id}`

Cancel subscription.

---

## 15. Learner Comments

**Prefix:** `/api/learner/trades/{trade_id}`

### GET `/comments`

Get all comments on a trade.

---

### POST `/comments`

Post a comment (learner must have unlocked the trade or be subscribed).

**Request body:**
```json
{ "content": "What is your target rationale based on?" }
```

---

### PUT `/comments/{comment_id}`

Edit own comment.

**Errors:** `403` if editing another user's comment

---

### DELETE `/comments/{comment_id}`

Delete own comment.

---

## 16. Learner Ratings

**Prefix:** `/api/learner`

### POST `/trades/{trade_id}/rate`

Rate a trade (1–5 stars).

**Request body:**
```json
{ "rating": 5 }
```

**Errors:** `400` if rating not in 1–5 range, `409` if already rated

---

### GET `/trades/{trade_id}/rating`

Get own rating for a trade.

---

## 17. Learner Flags

**Prefix:** `/api/learner`

### POST `/trades/{trade_id}/flag`

Flag a trade as suspicious or fraudulent.

**Request body:**
```json
{ "reason": "Entry price was incorrect — market was in circuit breaker at this level." }
```

**Response 201:**
```json
{ "message": "Trade flagged for review", "flag_id": "uuid" }
```

**Errors:** `409` if already flagged this trade

---

### GET `/trades/{trade_id}/flags`

Check if you have flagged this trade.

---

## 18. Learner Notifications

**Prefix:** `/api/learner`

### GET `/notifications`

**Query:** `page`, `per_page`, `unread_only=true`

---

### PUT `/notifications/{id}/read`

---

### DELETE `/notifications/{id}`

---

### POST `/notifications/clear-all`

---

### GET `/notification-preferences`

---

### PUT `/notification-preferences`

**Request body:**
```json
{
  "email_new_trade": true,
  "email_trade_closed": true,
  "email_subscription_expiry": true,
  "push_new_trade": true,
  "push_trade_closed": true
}
```

---

## 19. Learner Profile

**Prefix:** `/api/learner`

### GET `/profile`

**Response 200:**
```json
{
  "id": "uuid",
  "display_name": "Student Trader",
  "interests": ["nifty50", "crypto"],
  "experience_level": "beginner",
  "disclaimer_accepted": true,
  "credits": 6,
  "avatar_url": null,
  "learning_goal": "Understand swing trading setups"
}
```

---

### PUT `/profile`

**Request body:**
```json
{
  "display_name": "Student Trader",
  "interests": ["nifty50", "crypto"],
  "experience_level": "intermediate",
  "learning_goal": "Master risk management",
  "bio": "Learning from the best traders."
}
```

---

### PUT `/profile/picture`

Multipart form upload.

**Form fields:**
- `picture`: Image file (JPEG/PNG, max 10 MB)

---

### GET `/history`

Learning history: all unlocked trades and subscriptions.

**Response 200:**
```json
{
  "unlocked_trades": [
    {
      "trade_id": "uuid",
      "symbol": "NIFTY50",
      "pro_trader_name": "Ravi Kumar",
      "unlocked_at": "2026-03-24T10:00:00Z",
      "outcome": "target_hit"
    }
  ],
  "total_unlocked": 3,
  "weekly_chart": { /* trades unlocked per week for last 12 weeks */ },
  "market_distribution": { "nifty50": 2, "crypto": 1 }
}
```

---

## 20. Webhooks

**Prefix:** `/api/webhooks`

### POST `/cashfree/payment`

Called by Cashfree when a payment completes.

Handles:
1. Verifies webhook signature
2. Creates subscription record
3. Calculates 90/10 revenue split
4. Credits pro-trader wallet
5. Sends notifications

---

### POST `/cashfree/payout`

Called by Cashfree when a payout completes or fails.

Handles:
1. Verifies webhook signature
2. Updates payout status
3. Sends email notification to pro-trader

---

## Error Response Format

All error responses follow this format:

```json
{
  "error": "Human-readable error message",
  "code": "MACHINE_READABLE_CODE",
  "details": {}
}
```

## Common HTTP Status Codes

| Code | Meaning |
|------|---------|
| 200 | Success |
| 201 | Created |
| 400 | Bad Request (validation error) |
| 401 | Unauthorized (missing or invalid token) |
| 402 | Payment Required (insufficient credits) |
| 403 | Forbidden (access denied) |
| 404 | Not Found |
| 409 | Conflict (duplicate resource) |
| 500 | Internal Server Error |
