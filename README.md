# TradeWise — Complete Platform Setup Guide

TradeWise is a full-stack trading signal marketplace where **Pro-Traders** share trade ideas and **Learners** (Public Traders) learn from them using a credit-based unlock system with optional subscriptions.

---

## Table of Contents

1. [Platform Overview](#platform-overview)
2. [Manual QA Checklist](#manual-qa-checklist)
3. [Navigation & Routing Flow](#navigation--routing-flow)
4. [Prerequisites](#prerequisites)
5. [Repository Structure](#repository-structure)
6. [Local Development Setup](#local-development-setup)
7. [Environment Variables](#environment-variables)
8. [Database Initialization](#database-initialization)
9. [Running the Backend](#running-the-backend)
10. [Running the Frontend](#running-the-frontend)
11. [Running Tests](#running-tests)
12. [Key Concepts](#key-concepts)
13. [Documentation Index](#documentation-index)

---

## Platform Overview

| Component | Description | Port |
|-----------|-------------|------|
| **Backend** | Python 3.11 / Flask REST API | 5000 |
| **Pro-Trader Frontend** | Trading dashboard for signal providers | 3000 |
| **Learner Frontend** | Learning dashboard for signal consumers | 8000 |
| **Database** | Supabase PostgreSQL | Supabase Cloud |
| **Realtime** | Supabase Realtime (WebSocket) | Supabase Cloud |
| **Payments** | Cashfree (TEST mode) | Cashfree Cloud |

### User Roles

| Role | Description |
|------|-------------|
| **Pro-Trader** | Posts trading ideas with entry/SL/target. Earns subscription revenue (90% share). |
| **Learner** | Starts with 7 free credits. Each credit unlocks one trade analysis. Can subscribe to individual pro-traders for unlimited access. |
| **Admin** | Reviews KYC, handles flagged trades, manages platform. |

### Credit & Subscription Model

- Learners receive **7 free credits** on signup
- 1 credit = unlock 1 trade analysis (blurred details become visible)
- After credits run out, learner must **subscribe to a specific Pro-Trader** (e.g. ₹500/month)
- Subscribed learners get unlimited trade access from that trader — no credit deduction
- Revenue split: **90% to Pro-Trader, 10% to platform**

---

## Manual QA Checklist

Use this checklist to verify the canonical user flow works end-to-end after any significant change.

### Pre-flight

- [ ] Backend running on `http://localhost:5000`
- [ ] Frontend served from project root (e.g. `python3 -m http.server 8080`)
- [ ] No console errors on any page (open DevTools → Console)
- [ ] No 404 errors in the Network tab for assets/scripts/styles

### Landing → Auth

- [ ] Open `index.html` — landing page loads correctly, no broken images
- [ ] Click **Get Started** — navigates to `pages/auth.html`
- [ ] Sign-up form: password strength meter appears, validation works
- [ ] Login form: error shown for wrong credentials
- [ ] Forgot password form: sends reset email or shows success message
- [ ] Back-to-home arrow navigates back to `index.html`

### Auth → Role Selection

- [ ] Successful sign-up redirects to `pages/role-select.html`
- [ ] Successful login redirects to `pages/role-select.html`
- [ ] Visiting `pages/role-select.html` without JWT token redirects to `pages/auth.html`

### Public Trader Path

- [ ] Select **"I am a Public Trader"** and click Continue
- [ ] Redirects to `pages/profile-setup.html`
- [ ] Completing profile setup redirects to `frontend/learner/pages/dashboard.html`
- [ ] Learner dashboard loads fully (sidebar, stats, trade feed)
- [ ] Returning user (already has role + interests) is fast-forwarded from `role-select.html` directly to `frontend/learner/pages/dashboard.html`

### Experienced Trader Path

- [ ] Select **"I am an Experienced Trader"** and click Continue
- [ ] Redirects to `frontend/pages/dashboard.html`
- [ ] Pro-trader dashboard loads fully (sidebar, stats, trade list)
- [ ] Returning user (already has pro_trader role) is fast-forwarded from `role-select.html` directly to `frontend/pages/dashboard.html`

### Auth Guard

- [ ] Visiting any protected page without JWT token redirects to `pages/auth.html`
- [ ] Logging out clears `tw_jwt_token` from localStorage and redirects to `pages/auth.html`

### No Obsolete References

- [ ] No link to any deleted page (`register.html`, `role-selection.html`, `pro-trader-coming-soon.html`, etc.)
- [ ] No 404 for `js/config.js` or `js/supabase.js`
- [ ] No 404 for `frontend/index.html`

---

## Navigation & Routing Flow

### Canonical Entry Pages

| Page | Path | Description |
|------|------|-------------|
| Landing | `tradewise/index.html` | Public marketing page |
| Auth | `tradewise/pages/auth.html` | Unified login / sign-up |
| Role Select | `tradewise/pages/role-select.html` | Post-auth role chooser |
| Profile Setup | `tradewise/pages/profile-setup.html` | Public-trader onboarding |
| Learner Dashboard | `tradewise/frontend/learner/pages/dashboard.html` | Public-trader main view |
| Pro-Trader Dashboard | `tradewise/frontend/pages/dashboard.html` | Experienced-trader main view |

### User Flow

```
index.html
  └─► pages/auth.html          (sign up / log in)
        └─► pages/role-select.html   (choose role — skipped for returning users)
              ├─► "I am a Public Trader"
              │     └─► pages/profile-setup.html
              │               └─► frontend/learner/pages/dashboard.html
              └─► "I am an Experienced Trader"
                        └─► frontend/pages/dashboard.html
```

**Returning users** (already have a role and completed profile setup) are fast-forwarded by `role-select.html` directly to the appropriate dashboard without seeing the role-selection UI.

**Auth guard:** Every protected page checks for `tw_jwt_token` in `localStorage` and redirects to `pages/auth.html` if absent.

### Removed Files

The following files were hard-deleted during the repository restructure (they were duplicates, redirect stubs, or obsolete pages):

| Removed Path | Reason |
|-------------|--------|
| `frontend/learner/pages/register.html` | Duplicate auth — redirected to `pages/auth.html` |
| `frontend/learner/pages/role-selection.html` | Duplicate role select — redirected to `pages/role-select.html` |
| `frontend/pages/register.html` | Duplicate auth — redirected to `pages/auth.html` |
| `frontend/learner/pages/profile-setup.html` | Duplicate profile setup — replaced by `pages/profile-setup.html` |
| `pages/dashboard.html` | Legacy standalone dashboard — replaced by role-specific dashboards |
| `pages/pro-trader-coming-soon.html` | Obsolete placeholder page |
| `frontend/index.html` | Legacy splash entry — replaced by root `index.html` |
| `js/config.js` | Unused Supabase config module (placeholder credentials) |
| `js/supabase.js` | Unused Supabase ESM export (auth now handled via Flask JWT) |

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.8+ (3.11 recommended) | [python.org](https://python.org) |
| Git | Any recent | [git-scm.com](https://git-scm.com) |
| Supabase account | Free tier OK | [supabase.com](https://supabase.com) |
| Cashfree TEST account | — | [cashfree.com](https://cashfree.com) |
| Node.js (optional) | 16+ | Only needed for `npx serve` |

---

## Repository Structure

```
TradeWise/
├── README.md                          # This file
├── ROUTE_MAP.md                       # Canonical navigation route map
├── TESTING_GUIDE.md                   # Complete testing guide
├── index.html                         # ① Landing page (entry point)
├── styles.css                         # Landing page styles
├── script.js                          # Landing page scripts
├── logo.svg                           # Brand logo
├── css/
│   └── pages/
│       └── auth.css                   # Auth/role-select/profile-setup page styles
├── pages/
│   ├── auth.html                      # ② Unified sign-up / log-in page
│   ├── role-select.html               # ③ Role chooser (post-auth)
│   └── profile-setup.html            # ④ Public-trader onboarding
├── js/
│   └── auth.js                        # Auth page logic (JWT-based)
├── docs/
│   ├── API_DOCUMENTATION.md           # Full API reference
│   ├── DATABASE_SCHEMA.md             # Database tables & relationships
│   ├── DEPLOYMENT_GUIDE.md            # Production deployment
│   └── TROUBLESHOOTING.md             # Common issues & fixes
├── frontend/
│   ├── README.md                      # Frontend-specific docs
│   ├── .env.example                   # Frontend environment template
│   ├── css/                           # Pro-trader styles
│   ├── js/                            # Pro-trader scripts
│   ├── pages/                         # ⑤ Experienced-trader pages
│   │   ├── dashboard.html             # Experienced-trader main view
│   │   ├── analytics.html
│   │   ├── active-trades.html
│   │   ├── post-trade.html
│   │   ├── earnings.html
│   │   ├── subscribers.html
│   │   ├── kyc-setup.html
│   │   ├── notifications.html
│   │   ├── profile-settings.html
│   │   ├── settings.html
│   │   └── account-settings.html
│   └── learner/
│       ├── css/                       # Learner styles
│       ├── js/                        # Learner scripts
│       └── pages/                     # ⑥ Public-trader pages
│           ├── dashboard.html         # Public-trader main view
│           ├── feed.html
│           ├── my-history.html
│           ├── my-subscriptions.html
│           ├── trade-detail.html
│           ├── notifications.html
│           ├── notification-preferences.html
│           ├── profile-settings.html
│           ├── account-settings.html
│           └── payment-callback.html
├── backend/
│   ├── run.py                         # Flask entry point
│   ├── requirements.txt               # Python dependencies
│   ├── .env.example                   # Environment variable template
│   ├── README.md                      # Backend-specific docs
│   ├── app/
│   │   ├── __init__.py                # App factory
│   │   ├── config.py                  # Configuration classes
│   │   ├── models/                    # SQLAlchemy models
│   │   ├── routes/                    # Flask route blueprints
│   │   ├── services/                  # Business logic (Cashfree, email, etc.)
│   │   └── utils/                     # Helpers (accuracy, validators, encryption)
│   └── tests/
│       ├── conftest.py                # Pytest fixtures
│       ├── test_auth.py               # Authentication tests
│       ├── test_trades.py             # Trade & profile tests
│       ├── test_learner.py            # Learner flow tests
│       └── test_utils.py              # Utility function tests
└── supabase/
    ├── schema.sql                     # Full database schema
    └── rls-policies.sql               # Row Level Security policies
```

---

## Local Development Setup

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Dushyant7090/TradeWise.git
cd TradeWise
```

### Step 2 — Create Python Virtual Environment

```bash
cd backend
python3 -m venv venv

# Activate:
source venv/bin/activate        # macOS / Linux
# OR
venv\Scripts\activate           # Windows
```

### Step 3 — Install Backend Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` with your actual credentials. See [Environment Variables](#environment-variables) below for all required fields.

### Step 5 — Initialize the Database

Apply the schema to your Supabase project using the Supabase SQL Editor:

1. Open your Supabase project → **SQL Editor**
2. Paste and run the contents of `supabase/schema.sql`
3. Paste and run the contents of `supabase/rls-policies.sql`

Alternatively, let SQLAlchemy create the tables automatically on first run:

```bash
python -c "from app import create_app, db; app = create_app(); app.app_context().push(); db.create_all()"
```

### Step 6 — Start the Backend Server

```bash
# From the backend/ directory with venv active:
python run.py
```

The API will be available at `http://localhost:5000`.

### Step 7 — Start the Frontend Servers

**Pro-Trader Dashboard (port 3000):**

```bash
cd frontend
python3 -m http.server 3000
# OR
npx serve . -p 3000
```

**Learner Dashboard (port 8000):**

```bash
# From within frontend/learner/
cd frontend/learner
python3 -m http.server 8000
# OR (from project root)
python3 -m http.server 8000 --directory frontend/learner
```

### Step 8 — Verify Everything is Running

```bash
# Check backend health
curl http://localhost:5000/api/auth/login

# Expected: 400 (missing fields) — means the server is up

# Open Pro-Trader Dashboard
open http://localhost:3000

# Open Learner Dashboard
open http://localhost:8000
```

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` and fill in all values.

### Required Variables

```env
# ──────────────────────────────────────────────
# Flask
# ──────────────────────────────────────────────
FLASK_ENV=development
FLASK_SECRET_KEY=your-super-secret-key-change-in-production
FLASK_DEBUG=true

# ──────────────────────────────────────────────
# Supabase (required)
# ──────────────────────────────────────────────
SUPABASE_URL=https://[project-ref].supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
SUPABASE_JWT_SECRET=your-supabase-jwt-secret
DATABASE_URL=postgresql://postgres:[password]@db.[project-ref].supabase.co:5432/postgres

# ──────────────────────────────────────────────
# JWT
# ──────────────────────────────────────────────
JWT_SECRET_KEY=your-jwt-secret-key-change-in-production
JWT_ACCESS_TOKEN_EXPIRES=3600
JWT_REFRESH_TOKEN_EXPIRES=2592000

# ──────────────────────────────────────────────
# Cashfree Payments — TEST credentials
# ──────────────────────────────────────────────
CASHFREE_APP_ID=your-cashfree-test-app-id
CASHFREE_SECRET_KEY=your-cashfree-test-secret-key
CASHFREE_BASE_URL=https://sandbox.cashfree.com/pg
CASHFREE_PAYOUT_BASE_URL=https://payout-gamma.cashfree.com
CASHFREE_WEBHOOK_SECRET=your-cashfree-webhook-secret

# ──────────────────────────────────────────────
# Email (SMTP)
# ──────────────────────────────────────────────
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password
MAIL_DEFAULT_SENDER=noreply@tradewise.com

# ──────────────────────────────────────────────
# Bank details encryption key
# ──────────────────────────────────────────────
ENCRYPTION_KEY=your-32-byte-base64-encoded-encryption-key

# ──────────────────────────────────────────────
# Redis (optional — only needed for background tasks)
# ──────────────────────────────────────────────
REDIS_URL=redis://localhost:6379/0

# ──────────────────────────────────────────────
# Platform settings
# ──────────────────────────────────────────────
PLATFORM_FEE_PERCENT=10
PRO_TRADER_REVENUE_PERCENT=90
MIN_WITHDRAWAL_AMOUNT=500
MAX_FLAG_PENALTY_THRESHOLD=10
FLAG_ACCURACY_PENALTY=5

# ──────────────────────────────────────────────
# URLs
# ──────────────────────────────────────────────
FRONTEND_URL=http://localhost:3000
ADMIN_EMAIL=admin@tradewise.com
```

### Frontend Configuration

The frontend reads API config from global JavaScript variables. Edit the `<script>` block in each HTML page's `<head>`, or set them in `frontend/.env`:

```env
VITE_API_BASE_URL=http://localhost:5000/api
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

Or inject via script tag (no build tool required):

```html
<script>
  window.TW_API_BASE_URL = 'http://localhost:5000/api';
  window.TW_SUPABASE_URL = 'https://your-project.supabase.co';
  window.TW_SUPABASE_ANON_KEY = 'your-anon-key';
</script>
```

---

## Database Initialization

The full schema is in `supabase/schema.sql`. The key tables are:

| Table | Purpose |
|-------|---------|
| `profiles` | All users (roles: `pro_trader`, `public_trader`, `admin`) |
| `trades` | Trade signals posted by pro-traders |
| `unlocked_trades` | Tracks which learners have unlocked which trades |
| `subscriptions` | Active/expired subscriptions between learners and pro-traders |
| `payments` | Cashfree payment records |
| `comments` | Trade discussion threads |
| `flags` | Trade flagging for review |
| `notifications` | In-app notification queue |
| `mentor_stats` | Aggregated accuracy & performance per pro-trader |

See [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) for the complete schema reference.

---

## Running the Backend

```bash
cd backend
source venv/bin/activate
python run.py
```

**Development server output:**

```
 * Running on http://0.0.0.0:5000
 * Debug mode: on
```

**Verify endpoints:**

```bash
# Registration
curl -X POST http://localhost:5000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass1","role":"pro_trader","display_name":"Test"}'

# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"TestPass1"}'
```

---

## Running the Frontend

### Pro-Trader Dashboard

```bash
cd frontend
python3 -m http.server 3000
```

Open `http://localhost:3000` → redirects to login page.

### Learner Dashboard

```bash
python3 -m http.server 8000 --directory frontend/learner
```

Open `http://localhost:8000` → redirects to learner login/registration.

---

## Running Tests

The backend has a full pytest test suite that runs against an **in-memory SQLite** database (no external services needed).

```bash
cd backend
source venv/bin/activate
pip install pytest
pytest tests/ -v
```

**Run a specific test file:**

```bash
pytest tests/test_auth.py -v
pytest tests/test_trades.py -v
pytest tests/test_learner.py -v
pytest tests/test_utils.py -v
```

**Run with coverage:**

```bash
pip install pytest-cov
pytest tests/ -v --cov=app --cov-report=term-missing
```

---

## Key Concepts

### Trade Visibility Rules

| User State | What They See |
|-----------|---------------|
| Not logged in | Nothing (redirect to login) |
| Learner (has credits) | Pro-trader name, accuracy score, symbol, RR ratio — everything else blurred |
| Learner (used 1 credit) | Full trade details: direction, entry, SL, target, chart, rationale |
| Learner (subscribed to trader) | Full details with no credit deduction |
| Pro-trader | Their own trades in full |

### Accuracy Score

```
accuracy_score = (winning_trades / total_closed_trades) × 100
```

Penalty: If a trade receives ≥ 10 flags, the pro-trader's accuracy receives a **5% deduction** per flagged trade (admin-controlled threshold).

### Revenue Split

When a learner subscribes:
- **90%** → Pro-Trader wallet (available for withdrawal)
- **10%** → Platform admin

Minimum withdrawal: ₹500

---

## Documentation Index

| Document | Description |
|----------|-------------|
| [`README.md`](README.md) | This file — platform overview and setup |
| [`ROUTE_MAP.md`](ROUTE_MAP.md) | Canonical navigation route map |
| [`TESTING_GUIDE.md`](TESTING_GUIDE.md) | Step-by-step testing guide for all workflows |
| [`docs/API_DOCUMENTATION.md`](docs/API_DOCUMENTATION.md) | Complete API reference with examples |
| [`docs/DATABASE_SCHEMA.md`](docs/DATABASE_SCHEMA.md) | Database tables, columns, and relationships |
| [`docs/DEPLOYMENT_GUIDE.md`](docs/DEPLOYMENT_GUIDE.md) | Production deployment (Render, Railway, Docker) |
| [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md) | Common issues and solutions |
| [`backend/README.md`](backend/README.md) | Backend API quick reference |
| [`frontend/README.md`](frontend/README.md) | Frontend structure and component guide |
