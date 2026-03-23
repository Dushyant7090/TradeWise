# TradeWise Backend - Pro-Trader Dashboard API

A complete Python Flask backend for the TradeWise Pro-Trader Dashboard, featuring JWT authentication, Cashfree Payments integration, Supabase PostgreSQL, and more.

## Tech Stack

- **Backend**: Python 3.11+ / Flask 3.0
- **Database**: Supabase PostgreSQL via SQLAlchemy ORM
- **Authentication**: JWT tokens (Flask-JWT-Extended)
- **Payment**: Cashfree Payments (TEST MODE)
- **File Storage**: Supabase Storage
- **Email**: Flask-Mail (SMTP)
- **PDF Export**: ReportLab

## Quick Start

### 1. Clone and Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables

```bash
cp .env.example .env
# Edit .env with your actual values
```

### 3. Database Setup

The SQLAlchemy models map to your Supabase PostgreSQL database. Run the app once to create tables:

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### 4. Run the Server

```bash
python run.py
# Server starts on http://0.0.0.0:5000
```

### 5. Run Tests

```bash
pip install pytest
pytest tests/ -v
```

---

## API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/register` | Register a new user |
| POST | `/login` | Login with email/password |
| POST | `/logout` | Logout (invalidate token) |
| POST | `/refresh-token` | Refresh access token |
| POST | `/google-auth` | Google OAuth login |
| POST | `/2fa-setup` | Generate TOTP secret & QR |
| POST | `/2fa-verify` | Enable 2FA |
| POST | `/2fa-disable` | Disable 2FA |

**Register Request:**
```json
{
  "email": "trader@example.com",
  "password": "SecurePass1",
  "display_name": "Ravi Kumar",
  "role": "pro_trader"
}
```

**Login Request:**
```json
{
  "email": "trader@example.com",
  "password": "SecurePass1",
  "totp_code": "123456"  // optional, required if 2FA enabled
}
```

---

### Pro-Trader Profile (`/api/pro-trader`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/profile` | Get pro trader profile |
| PUT | `/profile` | Update bio, specializations, etc. |
| PUT | `/profile/picture` | Upload profile picture (multipart) |
| GET | `/dashboard` | Dashboard stats |

---

### Trades (`/api/pro-trader/trades`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/trades` | Submit new trade signal |
| GET | `/trades` | List trades (paginated) |
| GET | `/trades/{id}` | Get trade details |
| PUT | `/trades/{id}/close` | Close trade (win/loss) |
| DELETE | `/trades/{id}` | Cancel active trade |

**Create Trade Request:**
```json
{
  "symbol": "RELIANCE",
  "direction": "buy",
  "entry_price": 2500.00,
  "stop_loss_price": 2400.00,
  "target_price": 2700.00,
  "technical_rationale": "RELIANCE has broken out of a 3-month consolidation pattern with strong volume... (min 50 words)",
  "chart_image_url": "https://..."
}
```

---

### Comments (`/api/pro-trader/trades/{id}/comments`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/trades/{id}/comments` | Get comments (paginated) |
| POST | `/trades/{id}/comments` | Post a comment |
| PUT | `/trades/{id}/comments/{cid}` | Edit comment |
| DELETE | `/trades/{id}/comments/{cid}` | Delete comment |

---

### Analytics (`/api/pro-trader/analytics`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/analytics/accuracy` | Accuracy score |
| GET | `/analytics/performance-chart` | 12-month trend data |
| GET | `/analytics/win-loss` | Win/loss counts |
| GET | `/analytics/rrr` | Average RRR |
| GET | `/analytics/monthly-stats` | Monthly performance |
| GET | `/analytics/trade-history` | Closed trades (paginated) |

---

### Subscribers (`/api/pro-trader/subscribers`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/subscribers` | Active subscribers list |
| GET | `/subscribers/stats` | Subscriber count stats |
| POST | `/subscribers/notify` | Notify all subscribers |

---

### Earnings & Payouts (`/api/pro-trader`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/earnings` | Total/monthly earnings |
| GET | `/subscription-price` | Current price |
| PUT | `/subscription-price` | Set price |
| GET | `/balance` | Available balance |
| GET | `/payouts` | Payout history |
| POST | `/payouts/initiate` | Initiate withdrawal |
| GET | `/payouts/{id}/status` | Payout status |

**Initiate Payout:**
```json
{
  "amount": 5000.00
}
```

---

### KYC (`/api/pro-trader/kyc`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/kyc/status` | KYC verification status |
| POST | `/kyc/documents/upload` | Upload document (multipart) |
| GET | `/kyc/documents` | List documents |
| DELETE | `/kyc/documents/{id}` | Delete document |
| GET | `/bank-details` | Masked bank details |
| PUT | `/bank-details` | Update bank details |
| POST | `/kyc/submit-review` | Submit for admin review |

**Upload Document (multipart/form-data):**
- `document`: File (JPEG/PNG/PDF, max 10MB)
- `document_type`: One of `aadhaar`, `pan`, `passport`, `voter_id`, `driving_license`, `bank_statement`

**Update Bank Details:**
```json
{
  "bank_account_number": "1234567890123",
  "ifsc_code": "SBIN0001234",
  "account_holder_name": "Ravi Kumar"
}
```

---

### Account Settings (`/api/pro-trader`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| PUT | `/account-settings` | Update account settings |
| POST | `/change-password` | Change password |
| GET | `/login-activity` | Login logs |
| GET | `/notification-preferences` | Get preferences |
| PUT | `/notification-preferences` | Update preferences |
| POST | `/logout-sessions` | Logout other devices |

---

### Notifications (`/api/pro-trader/notifications`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/notifications` | All notifications (paginated) |
| PUT | `/notifications/{id}/read` | Mark as read |
| DELETE | `/notifications/{id}` | Delete notification |
| POST | `/notifications/clear-all` | Clear all |

---

### Exports (`/api/pro-trader/reports`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/reports/export-csv` | Export trades as CSV |
| GET | `/reports/export-pdf` | Export monthly report PDF |

---

### Webhooks (`/api/webhooks`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/cashfree/payment` | Cashfree payment webhook |
| POST | `/cashfree/payout` | Cashfree payout webhook |

---

## Key Features

### Accuracy Calculation
- Recalculated on every trade close
- `accuracy_score = (winning_trades / total_trades) * 100`
- Flag penalty: 5% deducted per trade with 10+ flags
- Leaderboard ranks updated globally after each recalculation

### Revenue Split Automation
- Triggered by Cashfree payment webhook (`/api/webhooks/cashfree/payment`)
- 90% credited to pro trader wallet, 10% to admin
- Stored in `revenue_splits` table

### Cashfree Payouts (TEST MODE)
- Requires KYC verified + bank details set
- Minimum withdrawal: ₹500
- Status flow: `initiated → processing → success/failed`
- Payout webhook at `/api/webhooks/cashfree/payout`

### KYC Flow
1. Upload documents (Supabase Storage)
2. Add bank details (stored encrypted with Fernet)
3. Submit for review (`/kyc/submit-review`)
4. Admin approves/rejects → email notification sent

---

## Environment Variables

See [.env.example](.env.example) for all required variables.

---

## Deployment

### Using Gunicorn

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "run:app"
```

### Using Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "run:app"]
```

---

## Database Tables

All tables are created automatically by SQLAlchemy. The schema maps to:

- `users` - Authentication credentials
- `profiles` - User profiles with roles
- `pro_trader_profiles` - Extended pro trader data
- `trades` - Trade signals
- `subscriptions` - Subscriber relationships
- `payments` - Payment records
- `revenue_splits` - 90/10 split records
- `payouts` - Withdrawal records
- `comments_threads` - Trade comments
- `reports` - Trade reports/flags
- `notifications` - In-app notifications
- `notification_preferences` - Alert settings
- `login_activities` - Login audit log
