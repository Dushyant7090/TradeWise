# TradeWise

> **Evidence-based trade ideas from verified mentors on Indian Equity Markets (NSE/BSE).**

[![Backend Tests](https://img.shields.io/badge/tests-pytest-passing-blue)](#running-tests)
[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![Flask](https://img.shields.io/badge/flask-3.0-lightgrey)](https://flask.palletsprojects.com)
[![Supabase](https://img.shields.io/badge/database-supabase-green)](https://supabase.com)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow)](#license)

TradeWise is a full-stack trading signal marketplace where **Pro Traders** (mentors) share high-quality trade ideas with charts and technical rationale, and **Public Traders** (learners) access verified analyses using a credit-based unlock system or paid subscriptions. The platform is purpose-built for Indian equity markets (NSE/BSE).

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Architecture & Technology Stack](#architecture--technology-stack)
3. [Repository Structure](#repository-structure)
4. [User Roles & Business Model](#user-roles--business-model)
5. [Key User Flows](#key-user-flows)
6. [Local Development Setup](#local-development-setup)
7. [Environment Variables](#environment-variables)
8. [Database Initialization](#database-initialization)
9. [Running the Backend](#running-the-backend)
10. [Running the Frontend](#running-the-frontend)
11. [Running Tests](#running-tests)
12. [API Quick Reference](#api-quick-reference)
13. [Documentation Index](#documentation-index)
14. [Contributing](#contributing)
15. [License](#license)

---

## Platform Overview

TradeWise connects two types of users on a single platform:

| Role | Who They Are | Core Value |
|------|--------------|------------|
| **Public Trader** (Learner) | Retail investors learning about markets | Access verified trade ideas; understand the *why* behind every signal |
| **Pro Trader** (Mentor) | Experienced traders sharing expertise | Build a verified track record; earn subscription revenue |
| **Admin** | Platform operators | Maintain trust: KYC review, moderation, payouts, analytics |

### Credit & Subscription Model

```
New learner signup ──► 7 free credits awarded
                             │
                     ┌───────▼────────┐
                     │  Browse feed   │  (blurred preview only)
                     └───────┬────────┘
                             │ Unlock trade
                     ┌───────▼────────┐
                     │  Use 1 credit  │  ──► Full details revealed
                     └───────┬────────┘
                             │ Credits exhausted
                     ┌───────▼────────┐
                     │  Subscribe to  │  ──► Unlimited access to that
                     │  Pro Trader    │       trader's trades (no credits)
                     └────────────────┘
```

- **1 credit = 1 trade unlock** (entry price, stop loss, target, chart, rationale)
- Subscriptions are **per-Pro-Trader** (e.g. ₹500/month), not platform-wide
- Revenue split: **90% to Pro Trader, 10% to platform**
- Minimum payout withdrawal: ₹500

---

## Architecture & Technology Stack

```
┌─────────────────────────────────────────────────────────────┐
│                        Browser                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   Learner    │  │  Pro Trader  │  │      Admin       │  │
│  │  (Vanilla JS)│  │  (Vanilla JS)│  │  (Vanilla JS)    │  │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘  │
└─────────┼─────────────────┼───────────────────┼────────────┘
          │  HTTP REST       │                   │
          ▼                  ▼                   ▼
┌─────────────────────────────────────────────────────────────┐
│           Python / Flask REST API  (port 5000)              │
│  Routes: auth · trades · learner_* · pro_trader_* · admin   │
│  Services: Cashfree · Email (SMTP) · Supabase Storage        │
│  Utils: JWT auth · bcrypt · AES encryption · TOTP 2FA        │
└──────────────────────────┬──────────────────────────────────┘
                           │  supabase-py / psycopg2
                           ▼
┌─────────────────────────────────────────────────────────────┐
│         Supabase (PostgreSQL 14+)                           │
│  20 tables · RLS policies · Row-level access control        │
│  Supabase Realtime (WebSocket notifications)                │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────┐   ┌────────────────────────────┐
│  Cashfree Payments        │   │  SMTP Email (Gmail/other)  │
│  - Subscription payments  │   │  - Signup confirmation     │
│  - Pro Trader payouts     │   │  - Notification emails     │
└──────────────────────────┘   └────────────────────────────┘
```

### Stack Summary

| Layer | Technology | Notes |
|-------|-----------|-------|
| **Backend** | Python 3.8+ / Flask 3.0 | REST API, port 5000 |
| **Frontend** | Vanilla HTML / CSS / JavaScript | No build tools required |
| **Database** | Supabase (PostgreSQL 14+) | Hosted or local via Supabase CLI |
| **Auth** | JWT (Flask-JWT-Extended) + bcrypt | Optional TOTP 2FA |
| **Realtime** | Supabase Realtime | WebSocket-based notifications |
| **Payments** | Cashfree | Subscriptions + Pro Trader payouts |
| **Storage** | Supabase Storage | Trade chart images, KYC documents |
| **Task Queue** | Celery + Redis | Background jobs (optional) |
| **Email** | SMTP / Flask-Mail | Signup, notifications |

---

## Repository Structure

```
TradeWise/
├── README.md                            # This file
├── CHANGELOG.md                         # Release notes
├── CONTRIBUTING.md                      # Contributor guide
├── TESTING_GUIDE.md                     # Manual QA guide for all flows
│
├── backend/
│   ├── run.py                           # Flask entry point
│   ├── requirements.txt                 # Python dependencies
│   ├── .env.example                     # Environment variable template
│   ├── README.md                        # Backend API quick reference
│   └── app/
│       ├── __init__.py                  # Flask app factory
│       ├── config.py                    # Environment-based config classes
│       ├── middleware/
│       │   ├── auth_middleware.py       # JWT auth decorators (@require_auth, role guards)
│       │   └── rate_limit.py            # Per-endpoint rate limiting
│       ├── models/                      # SQLAlchemy model classes (one file per table)
│       │   ├── user.py                  # Core auth accounts
│       │   ├── profile.py               # Base profile (all roles)
│       │   ├── pro_trader_profile.py    # Extended pro trader profile
│       │   ├── learner_profile.py       # Extended learner profile
│       │   ├── trade.py                 # Trade signals
│       │   ├── payment.py               # Cashfree payment records
│       │   ├── subscription.py          # Learner ↔ Pro Trader subscriptions
│       │   ├── payout.py                # Pro Trader withdrawal records
│       │   ├── revenue_split.py         # 90/10 split records per payment
│       │   ├── learner_trade_unlock.py  # Unlock records (credit or subscription)
│       │   ├── learner_credit_transaction.py  # Credit audit ledger
│       │   ├── learner_trade_rating.py  # 1–5 star ratings on trades
│       │   ├── learner_flag.py          # Learner-submitted trade flags
│       │   ├── comment.py               # Trade discussion comments
│       │   ├── report.py                # General trade reports
│       │   ├── notification.py          # Pro trader notifications
│       │   ├── learner_notification.py  # Learner notifications
│       │   ├── notification_preferences.py          # Pro trader notif prefs
│       │   ├── learner_notification_preferences.py  # Learner notif prefs
│       │   └── login_activity.py        # Login audit log
│       ├── routes/                      # Flask Blueprint route files
│       │   ├── auth.py                  # POST /api/auth/* (register, login, 2FA)
│       │   ├── trades.py                # CRUD for trade signals
│       │   ├── learner_dashboard.py     # GET /api/learner/dashboard
│       │   ├── learner_feed.py          # Trade feed with blurred/unlocked state
│       │   ├── learner_credits.py       # Credit balance and unlock endpoint
│       │   ├── learner_subscriptions.py # Subscribe/cancel per Pro Trader
│       │   ├── learner_payments.py      # Cashfree order creation for subscriptions
│       │   ├── learner_profile.py       # Learner profile CRUD
│       │   ├── learner_ratings.py       # Submit/update trade ratings
│       │   ├── learner_flags.py         # Flag a trade for review
│       │   ├── learner_comments.py      # Comment threads on trades
│       │   ├── learner_notifications.py # Learner in-app notifications
│       │   ├── pro_trader_profile.py    # Pro Trader profile CRUD
│       │   ├── pro_traders_public.py    # Public leaderboard / discovery
│       │   ├── kyc.py                   # KYC document upload & status
│       │   ├── earnings.py              # Earnings dashboard & payout request
│       │   ├── subscribers.py           # Subscriber list for pro traders
│       │   ├── analytics.py             # Performance analytics (accuracy, RRR)
│       │   ├── comments.py              # Shared comment endpoints
│       │   ├── notifications.py         # Pro trader notifications
│       │   ├── account_settings.py      # Account-level settings (2FA, password)
│       │   ├── exports.py               # CSV export (trades, earnings)
│       │   ├── admin.py                 # Admin-only management endpoints
│       │   └── webhooks.py              # Cashfree webhook handler
│       ├── services/
│       │   ├── cashfree.py              # Cashfree payment & payout API wrapper
│       │   ├── email_service.py         # SMTP email sender
│       │   ├── notification_service.py  # Fan-out notification logic
│       │   └── supabase_storage.py      # File upload to Supabase Storage
│       └── utils/
│           ├── accuracy.py              # Accuracy score calculation
│           ├── encryption.py            # AES encryption for bank details
│           └── validators.py            # Email, password, input validators
│   └── tests/
│       ├── conftest.py                  # Pytest fixtures (in-memory SQLite app)
│       ├── test_auth.py                 # Auth endpoint tests
│       ├── test_admin.py                # Admin endpoint tests
│       ├── test_trades.py               # Trade CRUD tests
│       ├── test_learner.py              # Learner flow tests
│       └── test_utils.py                # Utility function tests
│
├── frontend/
│   ├── landing-page.html                # Public marketing page (entry point)
│   ├── styles.css                       # Landing page styles
│   ├── script.js                        # Landing page scripts
│   ├── 404.html                         # Custom 404 page
│   ├── README.md                        # Frontend structure guide
│   ├── .env.example                     # Frontend config template
│   │
│   ├── pages/
│   │   └── role-selection.html          # Post-landing role chooser
│   │
│   ├── shared/                          # Cross-role shared assets
│   │   ├── assets/logo.svg              # Brand logo
│   │   ├── css/
│   │   │   ├── globals.css              # CSS variables, resets
│   │   │   ├── components.css           # Buttons, cards, modals
│   │   │   ├── pages.css                # Page-level layout
│   │   │   ├── auth.css                 # Auth form styles
│   │   │   └── responsive.css           # Media queries
│   │   └── js/
│   │       ├── api.js                   # Shared API client (fetch wrapper)
│   │       ├── auth.js                  # Auth guard, token storage
│   │       ├── charts.js                # Chart rendering (Chart.js)
│   │       ├── main.js                  # Global init
│   │       ├── realtime.js              # Supabase Realtime subscriptions
│   │       ├── storage.js               # localStorage helpers
│   │       └── utils.js                 # Shared utilities
│   │
│   ├── learner/                         # Public Trader (Learner) role
│   │   ├── css/learner.css
│   │   ├── js/
│   │   │   ├── api.js · auth.js · charts.js
│   │   │   ├── realtime.js · storage.js · utils.js
│   │   └── pages/
│   │       ├── auth.html                # Login / sign-up
│   │       ├── register.html            # Registration (or redirect to auth)
│   │       ├── profile-setup.html       # First-login onboarding
│   │       ├── dashboard.html           # Learner home: credits, subscriptions
│   │       ├── feed.html                # Trade signal feed (blurred preview)
│   │       ├── trade-detail.html        # Unlocked trade full details
│   │       ├── my-history.html          # Unlocked trade history
│   │       ├── my-subscriptions.html    # Active & past subscriptions
│   │       ├── payment-callback.html    # Cashfree return URL handler
│   │       ├── profile-settings.html    # Edit display name, avatar, goals
│   │       ├── account-settings.html    # Password, 2FA, danger zone
│   │       ├── notifications.html       # In-app notification list
│   │       └── notification-preferences.html  # Email/in-app/SMS opt-in
│   │
│   ├── pro-trader/                      # Pro Trader (Mentor) role
│   │   ├── css/pro-trader.css
│   │   ├── js/
│   │   │   ├── api.js · auth.js · charts.js · main.js
│   │   │   ├── pro-trader.js · realtime.js · storage.js · utils.js
│   │   └── pages/
│   │       ├── register.html            # Registration
│   │       ├── kyc-setup.html           # KYC document upload & status
│   │       ├── dashboard.html           # Pro Trader home: stats overview
│   │       ├── post-trade.html          # Create a new trade signal
│   │       ├── active-trades.html       # Manage open positions
│   │       ├── analytics.html           # Accuracy, RRR, win-rate charts
│   │       ├── earnings.html            # Revenue, balance, payout request
│   │       ├── subscribers.html         # Subscriber list
│   │       ├── profile-settings.html    # Bio, specializations, portfolio URL
│   │       ├── account-settings.html    # Password, 2FA, bank details
│   │       ├── settings.html            # Subscription pricing, notifications
│   │       └── notifications.html       # In-app notification list
│   │
│   ├── admin/                           # Admin role
│   │   ├── css/admin.css
│   │   ├── js/admin.js
│   │   ├── index.html                   # Admin login
│   │   └── dashboard.html               # Admin control panel
│   │
│   └── secure-access/admin/
│       ├── index.html                   # Hardened admin entry page
│       └── verify.js                    # Admin session verification
│
├── supabase/
│   ├── migrations/
│   │   ├── 20260331_001_tradewise_schema.sql  # Full schema: 20 tables + RLS
│   │   └── 20260331_002_admin_system.sql      # Admin functions & audit log
│   └── email-templates/
│       └── confirm-signup.html          # Supabase auth email template
│
└── docs/
    ├── API_DOCUMENTATION.md             # Complete REST API reference
    ├── DATABASE_SCHEMA.md               # Table relationships & columns
    ├── DEPLOYMENT_GUIDE.md              # Production deployment (Render, Railway)
    ├── TROUBLESHOOTING.md               # Common issues & fixes
    ├── USER_WORKFLOW.md                 # Detailed page-by-page user journeys
    └── admin-dashboard.md               # Admin panel feature reference
```

---

## User Roles & Business Model

### Public Trader (Learner)

- Registers at `frontend/learner/pages/auth.html` and completes profile setup
- Receives **7 free credits** automatically on account creation
- Browses the trade feed (`feed.html`) — previews are shown but sensitive details (entry, SL, target, chart, rationale) are blurred
- **Spends 1 credit** to unlock full details of a single trade (recorded in `learner_unlocked_trades`)
- Once credits run out, **subscribes to a specific Pro Trader** to regain unlimited access
- Can rate unlocked trades (1–5 stars), comment, or flag suspicious signals

### Pro Trader (Mentor)

- Registers at `frontend/pro-trader/pages/register.html`
- Completes **KYC verification** (`kyc-setup.html`) — admin must approve before the account is considered verified
- Posts trade signals with: symbol, direction (BUY/SELL), entry price, stop loss, target, RRR, technical rationale (min 50 words), and optional chart image
- Sets a **monthly subscription price** (in INR) for unlimited access to their feed
- Tracks performance metrics: accuracy score, win rate, total subscribers, earnings
- Requests **payouts** of their accumulated balance (minimum ₹500) via bank transfer through Cashfree

### Admin

- Accessed via `frontend/secure-access/admin/index.html` (hardened entry) or `frontend/admin/index.html`
- Reviews and approves/rejects **KYC submissions**
- Handles **flagged trades** — can issue warnings, apply accuracy penalties, or suspend accounts
- Monitors **platform payments and payouts**
- Has full database access via service-role key (bypasses RLS)

### Trade Visibility Rules

| Learner State | What They Can See |
|--------------|------------------|
| Not authenticated | Redirect to login |
| Authenticated, has credits | Pro Trader name, accuracy %, symbol, RRR (everything else blurred) |
| Spent 1 credit | Full trade: direction, entry, SL, target, chart, rationale |
| Subscribed to trader | Full details with no credit deduction |

### Accuracy Score

```
accuracy_score = (winning_trades / total_closed_trades) × 100
```

A trade accumulating ≥ 10 flags triggers an admin review; admin can apply a **5% accuracy penalty** per flagged trade.

---

## Key User Flows

### Public Trader (Learner) Flow

```
frontend/landing-page.html
  │  "Get Started Free" CTA
  ▼
frontend/learner/pages/auth.html          (sign up / log in)
  │  New user → profile-setup.html
  │  Returning user → dashboard.html
  ▼
frontend/learner/pages/profile-setup.html (interests, experience level, goal)
  ▼
frontend/learner/pages/dashboard.html     (credits balance, subscriptions, stats)
  │  "Browse Trades" CTA
  ▼
frontend/learner/pages/feed.html          (list of trade previews, blurred details)
  │  Click any trade
  ▼
frontend/learner/pages/trade-detail.html  (unlock via credit or active subscription)
  │  Rate / comment / flag trade
  │
  │  Credits exhausted → Subscribe CTA
  ▼
  Cashfree payment flow
  └─► frontend/learner/pages/payment-callback.html
  └─► subscription activated → trade-detail.html (no credit deduction)
```

### Pro Trader (Mentor) Flow

```
frontend/landing-page.html
  │  "Apply as Mentor" CTA
  ▼
frontend/pro-trader/pages/register.html   (create account)
  ▼
frontend/pro-trader/pages/kyc-setup.html  (upload identity + bank docs)
  │  Awaiting admin KYC approval
  ▼
frontend/pro-trader/pages/dashboard.html  (stats: accuracy, earnings, subscribers)
  │
  ├─► post-trade.html       → create new signal
  ├─► active-trades.html    → manage open positions (close/update)
  ├─► analytics.html        → performance charts (win rate, RRR distribution)
  ├─► earnings.html         → balance, payout history, request withdrawal
  ├─► subscribers.html      → subscriber list with join dates
  └─► notifications.html    → new subscriber, flagged trade, payout alerts
```

### Admin Flow

```
frontend/secure-access/admin/index.html   (hardened login with session check)
  ▼
frontend/admin/dashboard.html
  │
  ├─► KYC queue       → approve / reject with reason
  ├─► Trade flags     → review flagged trades → warning / penalty / suspension
  ├─► Payout review   → verify and approve payout requests
  ├─► User management → suspend / reactivate accounts
  └─► Platform analytics (revenue, active users, trade volume)
```

---

## Local Development Setup

### Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.8+ (3.11 recommended) | [python.org](https://python.org) |
| Git | Any recent | — |
| Supabase account | Free tier | [supabase.com](https://supabase.com) |
| Cashfree TEST account | — | [cashfree.com](https://cashfree.com) |
| Node.js | 16+ (optional) | Only for `npx serve` |
| Redis | 6+ (optional) | Only for Celery background tasks |

### Step 1 — Clone

```bash
git clone https://github.com/Dushyant7090/TradeWise.git
cd TradeWise
```

### Step 2 — Python Virtual Environment

```bash
cd backend
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### Step 3 — Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure Environment

```bash
cp .env.example .env
# Edit .env with your actual credentials (see Environment Variables below)
```

Also configure the frontend:

```bash
cp ../frontend/.env.example ../frontend/.env
# Edit with your Supabase URL and anon key
```

### Step 5 — Initialize the Database

Apply the migrations to your Supabase project via **SQL Editor**:

1. Open your Supabase project → **SQL Editor**
2. Run `supabase/migrations/20260331_001_tradewise_schema.sql` (full schema + RLS)
3. Run `supabase/migrations/20260331_002_admin_system.sql` (admin helpers + audit log)

Or using `psql`:

```bash
psql "$DATABASE_URL" -f supabase/migrations/20260331_001_tradewise_schema.sql
psql "$DATABASE_URL" -f supabase/migrations/20260331_002_admin_system.sql
```

### Step 6 — Promote a User to Admin

After running the migrations and creating a user account, promote them to admin via Supabase SQL Editor (service-role only):

```sql
SELECT public.promote_to_admin('your-admin@example.com');
```

### Step 7 — Start the Backend

```bash
# From backend/ with venv active:
python run.py
```

The API will be available at `http://localhost:5000`.

**Verify it is running:**

```bash
# Expect 400 (missing fields) — server is up
curl http://localhost:5000/api/auth/login
```

### Step 8 — Start the Frontend

The entire frontend is static HTML/CSS/JS — no build step required.

**Serve from project root** (all roles accessible from one server):

```bash
# From repo root
python3 -m http.server 5500 --directory frontend
```

Then open:

| URL | Page |
|-----|------|
| `http://localhost:5500/landing-page.html` | Landing page (entry point) |
| `http://localhost:5500/pages/role-selection.html` | Role chooser |
| `http://localhost:5500/learner/pages/auth.html` | Learner login/register |
| `http://localhost:5500/pro-trader/pages/register.html` | Pro Trader registration |
| `http://localhost:5500/admin/index.html` | Admin login |

**VS Code users:** Install the **Live Server** extension, right-click `frontend/landing-page.html`, and choose **Open with Live Server**.

---

## Environment Variables

### Backend (`backend/.env`)

```env
# Flask
FLASK_ENV=development
FLASK_SECRET_KEY=your-super-secret-key-change-in-production
FLASK_DEBUG=true

# Database (Supabase PostgreSQL)
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# Supabase
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret

# JWT (Flask-JWT-Extended)
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRES=3600         # seconds (1 hour)
JWT_REFRESH_TOKEN_EXPIRES=2592000     # seconds (30 days)

# Cashfree Payments — use TEST/sandbox credentials locally
CASHFREE_APP_ID=your-cashfree-test-app-id
CASHFREE_SECRET_KEY=your-cashfree-test-secret-key
CASHFREE_BASE_URL=https://sandbox.cashfree.com/pg
CASHFREE_PAYOUT_BASE_URL=https://payout-gamma.cashfree.com
CASHFREE_WEBHOOK_SECRET=your-cashfree-webhook-secret

# Email (SMTP)
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@tradewise.com

# AES encryption key for stored bank account numbers
ENCRYPTION_KEY=your-32-byte-base64-encoded-encryption-key

# Redis (only needed for Celery background jobs)
REDIS_URL=redis://localhost:6379/0

# Platform business rules
PLATFORM_FEE_PERCENT=10
PRO_TRADER_REVENUE_PERCENT=90
MIN_WITHDRAWAL_AMOUNT=500
MAX_FLAG_PENALTY_THRESHOLD=10
FLAG_ACCURACY_PENALTY=5

# CORS allowed origin
FRONTEND_URL=http://localhost:5500

# Admin seed email
ADMIN_EMAIL=admin@tradewise.com
```

### Frontend (`frontend/.env`)

The frontend reads these at runtime. Inject them into each HTML page's `<head>` via a `<script>` tag, or set them in `frontend/.env` for reference:

```env
VITE_API_BASE_URL=http://localhost:5000/api
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
VITE_APP_NAME=TradeWise
VITE_APP_ENV=development
```

Or inline in HTML (no build tool required):

```html
<script>
  window.TW_API_BASE_URL    = 'http://localhost:5000/api';
  window.TW_SUPABASE_URL    = 'https://your-project.supabase.co';
  window.TW_SUPABASE_ANON_KEY = 'your-anon-key';
</script>
```

---

## Database Initialization

The full schema is defined in two migration files under `supabase/migrations/`.

### Core Tables (migration 001)

| Table | Purpose |
|-------|---------|
| `users` | Core auth accounts (email/password + OAuth, optional TOTP 2FA) |
| `profiles` | Base profile shared by all roles (role, display name, avatar) |
| `pro_trader_profiles` | Extended pro trader data: KYC, trading stats, earnings balance |
| `learner_profiles` | Extended learner data: credits (default 7), interests, spend tracking |
| `trades` | Trade signals: symbol, direction, entry/SL/target, RRR, rationale, chart |
| `payments` | Cashfree payment lifecycle records |
| `subscriptions` | Active/expired learner ↔ pro trader subscription relationships |
| `revenue_splits` | 90/10 split records per payment |
| `payouts` | Pro trader payout requests and Cashfree transfer records |
| `learner_unlocked_trades` | Which learner unlocked which trade (via credit or subscription) |
| `learner_credits_log` | Immutable credit change audit ledger |
| `learner_trade_ratings` | 1–5 star ratings + review text per unlocked trade |
| `learner_flags` | Learner-submitted flags on suspicious signals |
| `reports` | General trade reports for admin review |
| `comments_threads` | Trade discussion comments |
| `notifications` | In-app notifications for pro traders |
| `learner_notifications` | In-app notifications for learners |
| `notification_preferences` | Pro trader email/in-app/SMS channel preferences |
| `learner_notification_preferences` | Learner email/in-app/SMS channel preferences |
| `login_activities` | Immutable login audit log (IP, device, status) |

### Admin System (migration 002)

| Object | Purpose |
|--------|---------|
| `public.is_admin(uid)` | Lightweight role-check helper used in RLS policies |
| `public.promote_to_admin(email)` | Bootstrap function to promote a user to admin (service-role only) |
| `public.admin_audit_log` | Immutable log of every admin action (approve/reject/suspend) |

All tables have **Row Level Security (RLS)** enabled. Each user can only read/write their own data. Admins bypass RLS via the service-role key.

---

## Running the Backend

```bash
cd backend
source venv/bin/activate   # (or venv\Scripts\activate on Windows)
python run.py
```

Expected output:
```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

**Sample requests:**

```bash
# Register a new Public Trader
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "learner@example.com",
    "password": "SecurePass1!",
    "role": "public_trader",
    "display_name": "Alice"
  }'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "learner@example.com", "password": "SecurePass1!"}'

# Get trade feed (requires JWT token)
curl http://localhost:5000/api/learner/feed \
  -H "Authorization: Bearer <access_token>"
```

See [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) for the full endpoint reference.

---

## Running the Frontend

The frontend has **no build step** — serve the `frontend/` directory with any static file server.

```bash
# From repo root — serves all roles at http://localhost:5500
python3 -m http.server 5500 --directory frontend

# Or with Node.js
npx serve frontend -p 5500
```

**Entry points:**

```
http://localhost:5500/landing-page.html                   ← Start here
http://localhost:5500/pages/role-selection.html
http://localhost:5500/learner/pages/auth.html
http://localhost:5500/learner/pages/dashboard.html
http://localhost:5500/pro-trader/pages/register.html
http://localhost:5500/pro-trader/pages/dashboard.html
http://localhost:5500/admin/index.html
```

**Auth guard:** Every protected page checks for a valid JWT in `localStorage`. If absent, it redirects to the appropriate role's auth page.

---

## Running Tests

The backend test suite uses **pytest** with an in-memory SQLite database — no external services required.

```bash
cd backend
source venv/bin/activate
python -m pytest tests/ -v
```

**Run a specific file:**

```bash
python -m pytest tests/test_auth.py -v
python -m pytest tests/test_trades.py -v
python -m pytest tests/test_learner.py -v
python -m pytest tests/test_admin.py -v
python -m pytest tests/test_utils.py -v
```

**Run with coverage:**

```bash
pip install pytest-cov
python -m pytest tests/ -v --cov=app --cov-report=term-missing
```

See [`TESTING_GUIDE.md`](TESTING_GUIDE.md) for the complete manual QA checklist covering all role flows.

---

## API Quick Reference

All endpoints are prefixed with `/api`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/auth/register` | Create account (any role) |
| `POST` | `/auth/login` | Login, returns JWT access + refresh tokens |
| `POST` | `/auth/refresh-token` | Rotate access token |
| `PUT`  | `/auth/role` | Set/update role after registration |
| `POST` | `/auth/2fa-setup` | Generate TOTP QR code |
| `POST` | `/auth/2fa-verify` | Activate 2FA |
| `GET`  | `/learner/dashboard` | Learner home stats |
| `GET`  | `/learner/feed` | Paginated trade feed (blurred state aware) |
| `POST` | `/learner/credits/unlock/<trade_id>` | Unlock a trade (deducts 1 credit) |
| `POST` | `/learner/subscriptions` | Subscribe to a Pro Trader |
| `GET`  | `/learner/subscriptions` | List active subscriptions |
| `POST` | `/learner/payments/create-order` | Initiate Cashfree payment |
| `GET`  | `/learner/notifications` | In-app notification list |
| `POST` | `/learner/flags` | Flag a suspicious trade |
| `GET`  | `/pro-trader/profile` | Get own Pro Trader profile |
| `PUT`  | `/pro-trader/profile` | Update profile, bio, price |
| `POST` | `/trades` | Post a new trade signal |
| `GET`  | `/trades` | List own trades |
| `PUT`  | `/trades/<id>` | Update or close a trade |
| `GET`  | `/analytics` | Performance analytics |
| `GET`  | `/earnings` | Earnings summary and balance |
| `POST` | `/earnings/payout` | Request payout |
| `POST` | `/kyc/upload` | Upload KYC documents |
| `GET`  | `/admin/kyc` | Pending KYC queue (admin only) |
| `POST` | `/admin/kyc/<id>/approve` | Approve KYC (admin only) |
| `GET`  | `/admin/flags` | Pending flags queue (admin only) |
| `POST` | `/webhooks/cashfree` | Cashfree payment webhook |

Full endpoint documentation with request/response examples: [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md)

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [`README.md`](README.md) | This file — overview, setup, architecture |
| [`CHANGELOG.md`](CHANGELOG.md) | Release notes and restructure history |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | How to contribute (branching, conventions, PR checklist) |
| [`TESTING_GUIDE.md`](TESTING_GUIDE.md) | Manual QA checklist for all user flows |
| [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) | Full REST API reference with examples |
| [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) | Database tables, columns, RLS policies |
| [`docs/USER_WORKFLOW.md`](docs/USER_WORKFLOW.md) | Detailed page-by-page journeys for all three roles |
| [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) | Production deployment (Render, Railway, Docker) |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [`docs/admin-dashboard.md`](docs/admin-dashboard.md) | Admin panel feature reference |
| [`backend/README.md`](backend/README.md) | Backend API quick-start guide |
| [`frontend/README.md`](frontend/README.md) | Frontend structure and component guide |

---

## Contributing

We welcome contributions! Please read [`CONTRIBUTING.md`](CONTRIBUTING.md) for the full guide. In summary:

1. **Fork** the repository and clone your fork.
2. **Create a branch:** `git checkout -b feat/your-feature-name`
3. **Follow conventions:**
   - Backend: PEP 8; new routes in `backend/app/routes/`; new models in `backend/app/models/`; protected endpoints must use `@require_auth`
   - Frontend: plain HTML/CSS/JS (no build tools); shared assets in `frontend/shared/`; role assets in the respective sub-folder
   - Database: schema changes must be a new numbered file in `supabase/migrations/`
4. **Run backend tests:** `cd backend && python -m pytest tests/ -v`
5. **Open a Pull Request** against `main` with a conventional commit title (`feat:`, `fix:`, `docs:`, etc.)

**PR Checklist:**
- [ ] Backend tests pass
- [ ] No broken asset paths in HTML files
- [ ] New DB changes include a migration file
- [ ] Docs updated if applicable

---

## License

This project is released under the [MIT License](LICENSE).

---

*TradeWise — evidence-based trading education for Indian equity markets.*
