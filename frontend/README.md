# TradeWise Frontend

A role-based trading signal platform frontend built with HTML5, CSS3, and vanilla JavaScript (ES6+).

## 📁 Project Structure

```
frontend/
├── index.html                 # Landing page — role selector (Admin / Learner / Pro Trader)
├── css/                       # Shared styles
│   ├── globals.css            # CSS variables, reset, base styles
│   ├── components.css         # Reusable UI components (buttons, modals, toasts, etc.)
│   ├── pages.css              # Layout & page-specific styles
│   └── responsive.css         # Media queries (768px tablet, 480px mobile)
├── js/                        # Shared JavaScript utilities
│   ├── main.js                # App initialization, toast system, sidebar
│   ├── auth.js                # JWT authentication, login/logout
│   ├── api.js                 # Fetch wrapper, all API endpoints
│   ├── storage.js             # localStorage management with cache TTL
│   ├── realtime.js            # Supabase Realtime subscriptions
│   ├── utils.js               # Helpers, formatters, validators
│   └── charts.js              # Chart.js initialization (4 chart types)
│
├── admin/                     # Admin role
│   ├── login.html             # Admin login
│   ├── dashboard.html         # Admin dashboard (users, trades, analytics)
│   ├── admin.css              # Admin-specific styles
│   ├── admin.js               # Admin-specific JavaScript
│   ├── pages/                 # (reserved for future admin sub-pages)
│   ├── css/                   # (reserved for additional admin stylesheets)
│   ├── js/                    # (reserved for additional admin scripts)
│   └── assets/                # Admin-specific assets
│
├── learner/                   # Learner role
│   ├── pages/
│   │   ├── dashboard.html     # Learner dashboard — credits, feed, subscriptions
│   │   ├── feed.html          # Trade feed — discover signals
│   │   ├── trade-detail.html  # Unlock & view a trade analysis
│   │   ├── my-subscriptions.html
│   │   ├── my-history.html
│   │   ├── notifications.html
│   │   ├── notification-preferences.html
│   │   ├── profile-settings.html
│   │   ├── account-settings.html
│   │   ├── profile-setup.html
│   │   ├── role-selection.html
│   │   ├── register.html
│   │   └── payment-callback.html
│   ├── css/
│   │   └── learner.css        # Learner-specific styles
│   ├── js/
│   │   ├── auth.js
│   │   ├── api.js
│   │   ├── charts.js
│   │   ├── realtime.js
│   │   ├── storage.js
│   │   └── utils.js
│   └── assets/                # Learner-specific assets
│
├── pro-trader/                # Pro Trader role
│   ├── pages/
│   │   ├── dashboard.html     # Pro Trader dashboard — accuracy, earnings, recent trades
│   │   ├── portfolio.html     # All trades — open & closed, P&L table
│   │   ├── signals.html       # Post and manage trade signals
│   │   └── risk-management.html  # Drawdown, RRR, position sizing calculator
│   ├── css/
│   │   └── pro-trader.css     # Pro Trader-specific styles
│   ├── js/
│   │   └── pro-trader.js      # Auth guard, fetch helper, Toast, formatters
│   └── assets/                # Pro Trader-specific assets
│
└── pages/                     # Legacy Pro Trader pages (original location — kept for compatibility)
    ├── dashboard.html
    ├── post-trade.html
    ├── active-trades.html
    ├── analytics.html
    ├── earnings.html
    ├── subscribers.html
    ├── kyc-setup.html
    ├── notifications.html
    ├── profile-settings.html
    ├── account-settings.html
    ├── settings.html
    └── register.html
```

## 🚀 Quick Start

### 1. Configure API URL

Set `window.TW_API_BASE_URL` in any page before your scripts load (or via `.env` with a build tool):

```html
<script>
  window.TW_API_BASE_URL      = 'http://localhost:5000/api';
  window.TW_SUPABASE_URL      = 'https://your-project.supabase.co';
  window.TW_SUPABASE_ANON_KEY = 'your-anon-key';
</script>
```

### 2. Serve the Frontend

Use any static file server. For local development:

```bash
# Python (from the frontend/ directory)
cd frontend
python3 -m http.server 3000

# Node.js
npx serve frontend -p 3000

# VS Code Live Server
# Open frontend/index.html and click "Go Live"
```

Open `http://localhost:3000` in your browser.

### 3. Open Each Role Locally

| Role | Entry Page | URL |
|------|-----------|-----|
| Landing | `frontend/index.html` | `http://localhost:3000/` |
| Admin | `frontend/admin/login.html` | `http://localhost:3000/admin/login.html` |
| Learner | `frontend/learner/pages/register.html` | `http://localhost:3000/learner/pages/register.html` |
| Pro Trader | `frontend/pro-trader/pages/dashboard.html` | `http://localhost:3000/pro-trader/pages/dashboard.html` |

> **Tip:** The landing page (`index.html`) auto-redirects authenticated users to their role dashboard based on `localStorage.tw_user_role`.

## 🔗 Backend Integration

- **API Base URL:** `http://localhost:5000/api` (configurable via `window.TW_API_BASE_URL`)
- **Auth:** JWT stored in `localStorage` as `tw_jwt_token`; auto-refresh on 401
- **Role key:** `localStorage.tw_user_role` — values: `admin`, `learner`, `pro_trader`

### Pro Trader API Endpoints

| Feature | Endpoints |
|---------|-----------|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh-token` |
| Dashboard | `GET /pro-trader/dashboard` |
| Trades | `GET/POST /pro-trader/trades`, `PUT /pro-trader/trades/{id}/close` |
| Analytics | `GET /pro-trader/analytics/accuracy`, `/win-loss`, `/rrr`, `/performance-chart`, `/monthly-stats` |
| Earnings | `GET /pro-trader/earnings`, `/balance`, `/payouts` |
| Subscribers | `GET /pro-trader/subscribers` |
| KYC | `GET /pro-trader/kyc/status`, `POST /pro-trader/kyc/upload-documents` |
| Notifications | `GET/PUT/DELETE /pro-trader/notifications/*` |

## 🎨 Design System

- **Primary:** `#10B981` (Emerald)
- **Background:** `#000000`
- **Cards:** `rgba(255,255,255,0.03)`
- **Font:** Inter (Google Fonts)
- **Mono:** JetBrains Mono

## ⚡ Real-time (Supabase)

Configure `TW_SUPABASE_URL` + `TW_SUPABASE_ANON_KEY` to enable:
- Live trade status updates
- Instant notification bell
- Real-time payout tracking

## 🛠 Stack

- HTML5 · CSS3 · Vanilla JS (ES6+)
- Chart.js 4
- Supabase Realtime
- No build tools required

## 📄 License

TradeWise © 2025. All rights reserved.
