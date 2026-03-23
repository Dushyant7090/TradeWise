# TradeWise Pro-Trader Dashboard — Frontend

A professional trading dashboard frontend built with HTML5, CSS3, and vanilla JavaScript (ES6+), designed to integrate seamlessly with the TradeWise Pro-Trader Backend.

## 📁 Project Structure

```
frontend/
├── index.html                 # Entry point — redirects to login or dashboard
├── css/
│   ├── globals.css            # CSS variables, reset, base styles
│   ├── components.css         # Reusable UI components (buttons, modals, etc.)
│   ├── pages.css              # Layout & page-specific styles
│   └── responsive.css         # Media queries (768px tablet, 480px mobile)
├── js/
│   ├── main.js                # App initialization, toast system, sidebar
│   ├── auth.js                # JWT authentication, login/logout
│   ├── api.js                 # Fetch wrapper, all API endpoints
│   ├── storage.js             # localStorage management with cache TTL
│   ├── realtime.js            # Supabase Realtime subscriptions
│   ├── utils.js               # Helpers, formatters, validators
│   └── charts.js              # Chart.js initialization (4 chart types)
├── pages/
│   ├── login.html             # Login page with forgot password modal
│   ├── register.html          # Registration with password strength
│   ├── dashboard.html         # Main dashboard with metrics & charts
│   ├── post-trade.html        # Post new trade form with RRR calculator
│   ├── active-trades.html     # Trade list with close modal & comments
│   ├── analytics.html         # Performance analytics with 4 charts
│   ├── earnings.html          # Earnings, payouts, withdrawal
│   ├── subscribers.html       # Subscriber list
│   ├── kyc-setup.html         # KYC documents & bank details
│   ├── profile-settings.html  # Profile editing
│   ├── account-settings.html  # Password, 2FA, login activity
│   ├── notifications.html     # Notification center
│   └── settings.html          # Notification preferences
├── assets/
│   ├── images/
│   ├── icons/
│   └── logos/
├── .env.example               # Environment variable template
└── README.md
```

## 🚀 Quick Start

### 1. Configure Environment

Copy `.env.example` and update values:

```bash
cp .env.example .env
```

Edit `.env`:
```env
VITE_API_BASE_URL=http://localhost:5000/api
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### 2. Configure API URL

The frontend reads API config from `window.TW_API_BASE_URL`. You can inject this in your HTML before the scripts, or set it via a build tool:

```html
<script>
  window.TW_API_BASE_URL = 'http://localhost:5000/api';
  window.TW_SUPABASE_URL = 'https://your-project.supabase.co';
  window.TW_SUPABASE_ANON_KEY = 'your-anon-key';
</script>
```

### 3. Serve the Frontend

Use any static file server. For development:

```bash
# Using Python
cd frontend
python3 -m http.server 3000

# Using Node.js serve
npx serve frontend -p 3000

# Using VS Code Live Server
# Open index.html and click "Go Live"
```

Open `http://localhost:3000` in your browser.

## 🔗 Backend Integration

### API Base URL
- Default: `http://localhost:5000/api`
- Configurable via `window.TW_API_BASE_URL`

### Authentication
- JWT stored in `localStorage` as `tw_jwt_token`
- Refresh token stored as `tw_refresh_token`
- Auto-refresh on 401 response
- Auto-logout if refresh fails

### API Endpoints Used

| Module | Endpoints |
|--------|-----------|
| Auth | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/refresh-token` |
| Profile | `GET/PUT /pro-trader/profile`, `GET /pro-trader/dashboard` |
| Trades | `GET/POST /pro-trader/trades`, `PUT /pro-trader/trades/{id}/close` |
| Comments | `GET/POST /pro-trader/trades/{id}/comments` |
| Analytics | `GET /pro-trader/analytics/accuracy`, `/performance-chart`, `/win-loss`, `/rrr`, `/monthly-stats` |
| Earnings | `GET /pro-trader/earnings`, `/balance`, `/payouts` |
| Payouts | `POST /pro-trader/payouts/initiate` |
| Subscribers | `GET /pro-trader/subscribers` |
| KYC | `GET /pro-trader/kyc/status`, `POST /pro-trader/kyc/upload-documents` |
| Notifications | `GET/PUT/DELETE /pro-trader/notifications/*` |
| Preferences | `GET/PUT /pro-trader/notification-preferences` |

## ⚡ Real-time Features (Supabase)

Configure Supabase credentials to enable real-time:
- **Trade updates** — live status changes
- **Notifications** — instant bell updates + toast
- **Payout status** — live payout tracking

## 📊 Charts (Chart.js)

Four Chart.js visualizations:
1. **Accuracy Trend** — line chart, 12 months
2. **Win/Loss Ratio** — doughnut chart
3. **Monthly Earnings** — bar chart
4. **RRR Distribution** — histogram

## 🎨 Design System

### Colors
- Primary: `#10B981` (Emerald)
- Background: `#000000`
- Cards: `rgba(255,255,255,0.03)`
- Text: `#FFFFFF` / `#A3A3A3`

### Typography
- Font: Inter (Google Fonts)
- Mono: JetBrains Mono (for prices/code)

### Breakpoints
- Desktop: 1280px+
- Tablet: ≤ 768px (sidebar becomes drawer)
- Mobile: ≤ 480px (single column)

## ✅ Features

- [x] JWT authentication with auto-refresh
- [x] Responsive sidebar navigation (mobile hamburger)
- [x] Post trade with RRR auto-calculator
- [x] Trade management (view, filter, close)
- [x] Comments system with real-time updates
- [x] Analytics with 4 Chart.js charts
- [x] Earnings & payout management
- [x] KYC document upload
- [x] Notification center with real-time
- [x] Notification preferences
- [x] Profile & account settings
- [x] 2FA setup
- [x] Password strength meter
- [x] Form validation (client-side + backend error display)
- [x] Toast notifications
- [x] Loading states & spinners
- [x] localStorage caching (5 min TTL)
- [x] WCAG accessibility (ARIA labels, keyboard navigation)
- [x] Dark theme throughout

## 🔒 Security

- JWT tokens stored in localStorage
- Bearer token sent with all API requests
- Auto-logout on invalid token
- Input validation on all forms
- File upload type/size validation
- No secrets in frontend code

## 🛠 Technology Stack

- **HTML5** — Semantic markup
- **CSS3** — Custom properties, Flexbox, CSS Grid
- **JavaScript (ES6+)** — Modules, async/await, destructuring
- **Chart.js 4** — Data visualization
- **Supabase Realtime** — WebSocket subscriptions
- **No build tools required** — Pure static files

## 📄 License

TradeWise © 2025. All rights reserved.
