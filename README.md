# TradeWise — Pro-Trader Signal Platform

TradeWise is a full-stack platform that lets **pro traders** publish trade signals and earn subscription revenue, while **public traders** (subscribers) follow those signals and learn from verified professionals.

---

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Key Technologies](#key-technologies)
- [Architecture](#architecture)
  - [Backend](#backend)
  - [Frontend](#frontend)
  - [Database](#database)
- [Core Features](#core-features)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
- [Running Tests](#running-tests)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [Security](#security)

---

## Overview

| Role | Capabilities |
|------|-------------|
| **Pro Trader** | Post trade signals with entry/SL/target, manage subscribers, track accuracy & earnings, withdraw revenue |
| **Public Trader** | Subscribe to pro traders, view signals, comment, receive real-time notifications |
| **Admin** | Review KYC documents, approve/reject withdrawals, manage platform |

The revenue model is a **90 / 10 split**: pro traders keep 90% of subscription fees; the platform retains 10%.

---

## Project Structure

```
TradeWise/
├── backend/                        # Python Flask REST API
│   ├── app/
│   │   ├── __init__.py             # Flask app factory, blueprint registration
│   │   ├── config.py               # Dev / Test / Prod config classes
│   │   ├── middleware/             # Role-based auth decorators
│   │   ├── models/                 # SQLAlchemy ORM models (14 entities)
│   │   ├── routes/                 # API route blueprints (11 files)
│   │   ├── services/               # External service integrations
│   │   └── utils/                  # Business-logic helpers & validators
│   ├── tests/                      # Pytest test suite
│   ├── run.py                      # Server entry point (port 5000)
│   ├── requirements.txt            # Python dependencies
│   ├── README.md                   # Backend-specific documentation
│   └── .env.example                # Backend environment variable template
│
├── frontend/                       # Vanilla JS + HTML5 static frontend
│   ├── index.html                  # Splash / auth-redirect page
│   ├── css/
│   │   ├── globals.css             # CSS variables, reset, base styles
│   │   ├── components.css          # Reusable UI components
│   │   ├── pages.css               # Page-level layout styles
│   │   └── responsive.css          # Tablet (768 px) & mobile (480 px) breakpoints
│   ├── js/
│   │   ├── main.js                 # App init, sidebar, toast notifications
│   │   ├── auth.js                 # JWT login / logout / auto-refresh
│   │   ├── api.js                  # Fetch wrapper & all endpoint definitions
│   │   ├── storage.js              # localStorage with TTL cache
│   │   ├── charts.js               # Chart.js chart initialisation (4 types)
│   │   ├── utils.js                # Formatters, validators, helpers
│   │   └── realtime.js             # Supabase WebSocket subscriptions
│   ├── pages/                      # 13 HTML pages
│   ├── README.md                   # Frontend-specific documentation
│   └── .env.example                # Frontend environment variable template
│
├── supabase/                       # Database schema & security policies
│   ├── schema.sql                  # Table definitions and indexes
│   ├── rls-policies.sql            # Row-Level Security rules
│   └── email-templates/            # Supabase transactional email templates
│
└── README.md                       # ← You are here
```

---

## Key Technologies

### Backend

| Category | Technology | Purpose |
|----------|-----------|---------|
| Language | Python 3.11+ | Core runtime |
| Framework | Flask 3.0 + Flask-SQLAlchemy | REST API and ORM |
| Database | PostgreSQL via Supabase | Primary data store |
| Authentication | Flask-JWT-Extended + PyOTP | JWT access/refresh tokens, TOTP 2FA |
| Payments | Cashfree SDK (test mode) | Subscription payments & trader payouts |
| File Storage | Supabase Storage | Profile pictures, KYC documents |
| Email | Flask-Mail (SMTP) | Transactional email notifications |
| Encryption | `cryptography` (Fernet) | At-rest encryption for bank details |
| PDF Reports | ReportLab | Monthly trade report generation |
| Task Queue | Celery + Redis | Async background tasks |
| Server | Gunicorn | Production WSGI server |

### Frontend

| Category | Technology | Purpose |
|----------|-----------|---------|
| Language | Vanilla JavaScript (ES6+) | All client-side logic |
| Markup | HTML5 | Semantic page templates |
| Styling | CSS3 (custom properties, grid, flexbox) | Dark theme UI |
| Charts | Chart.js 4 | Performance analytics visualisations |
| Real-time | Supabase Realtime (WebSockets) | Live trade & notification updates |
| Build tool | None | Pure static files, no bundler required |

---

## Architecture

### Backend

The backend follows a **Flask Application Factory** pattern with Blueprint-based routing.

#### Models (14 SQLAlchemy entities)

| Model | Description |
|-------|-------------|
| `User` | Authentication credentials, TOTP secret, OAuth provider |
| `Profile` | Display name, role (`pro_trader` / `public_trader` / `admin`) |
| `ProTraderProfile` | Bio, specialisations, stats, KYC status, bank details |
| `Trade` | Signal with entry / SL / target prices, status, RRR |
| `Comment` | Community comments on individual trades |
| `Subscription` | Pro-trader ↔ subscriber relationship |
| `Payment` | Cashfree payment records |
| `RevenueSplit` | 90/10 split transaction log |
| `Payout` | Withdrawal requests and status tracking |
| `Report` | Community flags on trades |
| `Notification` | In-app alert messages |
| `NotificationPreferences` | Per-user alert channel settings |
| `LoginActivity` | Audit log of login events |

#### Routes (11 blueprints)

| Blueprint | Prefix | Responsibility |
|-----------|--------|---------------|
| `auth` | `/api/auth` | Register, login, 2FA, token refresh |
| `trades` | `/api/trades` | Trade CRUD and status updates |
| `pro_trader_profile` | `/api/profile` | Profile management, picture upload |
| `comments` | `/api/comments` | Trade comment threads |
| `analytics` | `/api/analytics` | Accuracy, win/loss, earnings charts |
| `earnings` | `/api/earnings` | Balance, subscription price, payouts |
| `subscribers` | `/api/subscribers` | Subscriber list and notifications |
| `kyc` | `/api/kyc` | Document upload and bank details |
| `account_settings` | `/api/account` | Password, 2FA, notification prefs |
| `notifications` | `/api/notifications` | In-app notification management |
| `exports` | `/api/exports` | CSV and PDF trade reports |
| `webhooks` | `/api/webhooks` | Cashfree payment/payout event handlers |

#### Middleware

Decorators in `app/middleware/` enforce role-based access:

- `@require_auth` — any authenticated user
- `@require_pro_trader` — `pro_trader` role only
- `@require_admin` — `admin` role only

#### Key Utilities

| File | Logic |
|------|-------|
| `utils/accuracy.py` | `accuracy = (wins / total) * 100 - (5% per trade with >=10 flags)` |
| `utils/validators.py` | Email, password strength, IFSC code, bio length, rationale length |
| `utils/encryption.py` | Fernet symmetric encryption / decryption for bank account numbers |

---

### Frontend

The frontend is **zero-build** — plain HTML files load ES6 module scripts directly via `<script type="module">`. No npm, no bundler.

#### Pages (13 HTML files in `frontend/pages/`)

| Page | Purpose |
|------|---------|
| `login.html` | Email/password login with forgot-password modal |
| `register.html` | Sign-up with client-side password strength meter |
| `dashboard.html` | Key metrics and mini Chart.js graphs |
| `post-trade.html` | New trade form with live RRR auto-calculator |
| `active-trades.html` | Trade list, close-trade modal, comment threads |
| `analytics.html` | 4-panel performance analytics |
| `earnings.html` | Earnings summary, payout history, withdrawal form |
| `subscribers.html` | Subscriber list with stats |
| `kyc-setup.html` | Document upload and bank detail entry |
| `profile-settings.html` | Bio, specialisations, portfolio link |
| `account-settings.html` | Password change, 2FA setup, login activity |
| `notifications.html` | Notification centre with dismiss actions |
| `settings.html` | Email/push notification preference toggles |

#### JavaScript Modules (`frontend/js/`)

| Module | Responsibility |
|--------|---------------|
| `main.js` | App initialisation, toast system, sidebar navigation, realtime listener setup |
| `auth.js` | JWT token storage, login/logout, automatic 401 → refresh → retry flow |
| `api.js` | Central `fetch` wrapper with all named endpoint functions |
| `storage.js` | localStorage with 5-minute TTL to cache API responses |
| `charts.js` | Chart.js initialisation for line, doughnut, bar, and histogram charts |
| `utils.js` | Currency/date formatters, client-side validators, misc helpers |
| `realtime.js` | Supabase channel subscriptions for live trade and notification events |

#### Token Refresh Flow

```
Request → 401 Unauthorized
        → Attempt token refresh
        → Success: retry original request
        → Failure: clear tokens, redirect to /login
```

---

### Database

Supabase-hosted PostgreSQL. Two SQL files govern the schema and security:

| File | Purpose |
|------|---------|
| `supabase/schema.sql` | Table definitions, foreign keys, indexes |
| `supabase/rls-policies.sql` | Row-Level Security (RLS) policies — users can only read/write their own data |

SQLAlchemy auto-creates tables on first run during development. For production, apply the SQL files directly to Supabase.

---

## Core Features

- **Trade Signals** — Pro traders post buy/sell signals with entry, stop-loss, target, and a minimum-50-word technical rationale. Chart images can be attached.
- **Accuracy Scoring** — Live accuracy score derived from closed trades; penalised for repeatedly flagged signals.
- **Subscriptions & Payments** — Cashfree payment gateway (test mode); automatic 90/10 revenue split on successful payment.
- **KYC & Withdrawals** — Document upload → admin review → verified. Minimum ₹500 withdrawal via Cashfree Payouts.
- **Real-time Updates** — Supabase WebSocket channels push trade status changes and new notifications without polling.
- **Analytics** — Accuracy trend (12-month line), win/loss ratio (doughnut), monthly earnings (bar), RRR distribution (histogram).
- **Export** — CSV (all trades) and PDF monthly report.
- **2FA** — TOTP via any authenticator app; QR code provisioning in account settings.
- **Responsive UI** — Dark-theme dashboard works on desktop (1280 px+), tablet (768 px), and mobile (480 px).

---

## Getting Started

### Prerequisites

- Python 3.11+
- A [Supabase](https://supabase.com) project (PostgreSQL + Storage)
- Redis (for Celery task queue)
- Cashfree account (sandbox credentials for test mode)
- SMTP credentials (e.g. Gmail app password)

### Backend Setup

```bash
cd backend

# Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your Supabase URL, JWT secret, Cashfree keys, etc.

# Initialise the database (development only)
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"

# Start the development server
python run.py
# API available at http://localhost:5000
```

For production, use Gunicorn:

```bash
gunicorn -w 4 -b 0.0.0.0:5000 "run:app"
```

### Frontend Setup

No build step is required. Serve the `frontend/` directory with any static file server:

```bash
cd frontend
cp .env.example .env
# Edit .env — set VITE_API_BASE_URL=http://localhost:5000/api

# Option 1 — Python
python3 -m http.server 3000

# Option 2 — Node.js
npx serve . -p 3000

# Option 3 — VS Code Live Server extension
# Right-click index.html → "Open with Live Server"
```

Open `http://localhost:3000` in your browser.

---

## Running Tests

```bash
cd backend
pip install pytest
pytest tests/ -v
```

Test files:

| File | Coverage |
|------|---------|
| `tests/test_auth.py` | Registration, login, 2FA, token refresh |
| `tests/test_trades.py` | Trade CRUD, accuracy recalculation |
| `tests/test_utils.py` | Validators, RRR formula |

---

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description |
|----------|-------------|
| `FLASK_ENV` | `development` / `production` |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key (admin operations) |
| `JWT_SECRET_KEY` | Secret used to sign JWT tokens |
| `JWT_ACCESS_TOKEN_EXPIRES` | Access token TTL in seconds (default `3600`) |
| `JWT_REFRESH_TOKEN_EXPIRES` | Refresh token TTL in seconds (default `2592000`) |
| `CASHFREE_APP_ID` | Cashfree application ID |
| `CASHFREE_SECRET_KEY` | Cashfree secret key |
| `CASHFREE_WEBHOOK_SECRET` | HMAC secret for Cashfree webhook verification |
| `MAIL_SERVER` | SMTP server (e.g. `smtp.gmail.com`) |
| `MAIL_USERNAME` | SMTP username |
| `MAIL_PASSWORD` | SMTP password / app password |
| `ENCRYPTION_KEY` | Base64-encoded 32-byte Fernet key for bank details |
| `REDIS_URL` | Redis connection URL (e.g. `redis://localhost:6379/0`) |
| `PLATFORM_FEE_PERCENT` | Platform's share of subscription (default `10`) |
| `PRO_TRADER_REVENUE_PERCENT` | Trader's share (default `90`) |
| `MIN_WITHDRAWAL_AMOUNT` | Minimum payout in INR (default `500`) |
| `FRONTEND_URL` | Allowed CORS origin (e.g. `http://localhost:3000`) |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API base URL (e.g. `http://localhost:5000/api`) |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous public key |

---

## API Overview

All endpoints are prefixed with `/api`.

| Group | Endpoints | Description |
|-------|-----------|-------------|
| `/auth` | `POST /register`, `POST /login`, `POST /2fa/setup`, `POST /2fa/verify`, `POST /refresh`, `POST /logout` | Authentication & 2FA |
| `/trades` | `GET /`, `POST /`, `PATCH /:id`, `DELETE /:id` | Trade signal management |
| `/analytics` | `GET /accuracy`, `GET /win-loss`, `GET /earnings-chart`, `GET /rrr-distribution` | Performance data for charts |
| `/earnings` | `GET /summary`, `GET /payouts`, `POST /withdraw`, `PATCH /subscription-price` | Earnings & withdrawals |
| `/subscribers` | `GET /`, `GET /stats` | Subscriber management |
| `/kyc` | `POST /documents`, `POST /bank-details`, `GET /status` | KYC document upload & status |
| `/account` | `PATCH /password`, `GET /login-activity`, `POST /logout-all` | Account settings |
| `/notifications` | `GET /`, `PATCH /:id/read`, `DELETE /:id` | Notification management |
| `/exports` | `GET /csv`, `GET /pdf` | Trade report downloads |
| `/webhooks` | `POST /cashfree` | Cashfree event handler |

Full API documentation is in [`backend/README.md`](backend/README.md).

---

## Security

| Mechanism | Implementation |
|-----------|---------------|
| Password hashing | bcrypt with salt rounds |
| JWT tokens | 1-hour access token + 30-day refresh token |
| Two-factor auth | TOTP (RFC 6238) via any authenticator app |
| Bank detail encryption | Fernet symmetric encryption (AES-128-CBC with 128-bit key) |
| Webhook verification | HMAC-SHA256 signature validation |
| Row-Level Security | Supabase RLS policies (see `supabase/rls-policies.sql`) |
| CORS | Restricted to `FRONTEND_URL` origin |
| Input validation | Both client-side (JS) and server-side (Python validators) |
| File upload | Type allowlist and 10 MB size limit |
| Role-based access | Decorator middleware enforcing `pro_trader` / `admin` roles |
