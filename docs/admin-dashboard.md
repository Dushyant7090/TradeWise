# TradeWise Admin Dashboard

A fully responsive, professional admin dashboard for TradeWise platform management.

## Overview

The admin dashboard provides a centralized control panel for managing all aspects of the TradeWise platform: users, trades, payouts, moderation, KYC verification, and analytics.

---

## Access

The admin dashboard is located at `/frontend/admin/`:

| Page | Path |
|------|------|
| Login | `frontend/admin/login.html` |
| Dashboard | `frontend/admin/dashboard.html` |

### Admin Login

1. Open `frontend/admin/login.html` in your browser (or serve via the backend).
2. Enter your **admin email and password** (account must have `role = "admin"` in the `profiles` table).
3. On successful login you are redirected to `dashboard.html`.

**To create an admin user**, manually set `role = 'admin'` in the `profiles` table for the target user:
```sql
UPDATE profiles SET role = 'admin' WHERE user_id = '<your-user-uuid>';
```

---

## Features

### 1. Dashboard Overview
- Summary statistics cards: Active users (30d), Pro Traders, Learners, Monthly Revenue, Pending Payouts, Flagged Trades, Pending KYC, Open Reports.
- Quick action buttons to jump to key sections.
- Notification panel (bell icon) showing KYC, report, and payout alerts.

### 2. Analytics
Four interactive charts (Chart.js):
- **Monthly Revenue** — sum of successful payments per month (12 months).
- **User Registrations (Weekly)** — new user registrations per week (12 weeks).
- **Reports & Flags Trend (Weekly)** — weekly count of reports and learner flags.
- **Payouts History (Monthly)** — total paid-out amounts per month (12 months).

### 3. User Management
- List all users (pro traders, learners, admins) with pagination.
- Search by name or email; filter by role.
- **Suspend** a user (reversible — disables their account).
- **Reactivate** a suspended user.
- **Permanently Ban** a user (irreversible — disables account and sets `is_banned = true`).
- Export full user list as CSV.

### 4. Trade Monitoring
- List all trades with status, symbol, direction, flag count, unlock count.
- Filter by status (active/target_hit/sl_hit/cancelled) or flagged-only.
- Search by symbol.
- **Flag** / **Clear flags** on any trade.
- Export as CSV.

### 5. Pro-Trader Payouts
- List all payouts with trader name, email, amount, bank details, status.
- Filter by status (pending/processing/paid/failed); search by trader name.
- **Mark as Paid** / **Mark as Unpaid** actions.
- Export as CSV.

### 6. Reports & Flags
- View all flagged trades (from both pro traders' reports and learner flags).
- Filter by status (pending/investigating/resolved).
- **Resolve** a report with an admin verdict note.
- **Dismiss** a report with a note.
- Export as CSV.

### 7. Comment Moderation
- List all trade comments across the platform.
- Filter by trade ID.
- **Reply** to any comment (reply posted with `[Admin]` prefix).
- **Delete** any comment.

### 8. KYC Verification
- List all KYC submissions with document count and status.
- Filter by status (pending/verified/rejected).
- **Approve KYC** — sets `kyc_status = verified` and marks profile as verified.
- **Reject KYC** — sets `kyc_status = rejected`.

---

## REST API Endpoints

All admin endpoints are under `/api/admin/` and require a valid JWT token belonging to an `admin`-role user.

### Authentication
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/auth/login` | Standard login (returns JWT) |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/stats` | Summary statistics |

### User Management
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/users` | List users (`?search=&role=&page=&per_page=`) |
| GET | `/api/admin/users/<id>` | Get user detail |
| POST | `/api/admin/users/<id>/suspend` | Suspend user |
| POST | `/api/admin/users/<id>/reactivate` | Reactivate user |
| POST | `/api/admin/users/<id>/ban` | Permanently ban user |

### Trade Monitoring
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/trades` | List trades (`?search=&status=&flagged_only=&page=`) |
| GET | `/api/admin/trades/<id>` | Trade detail |
| POST | `/api/admin/trades/<id>/flag` | Flag a trade |
| POST | `/api/admin/trades/<id>/unflag` | Clear trade flags |

### Reports & Flags
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/reports` | List reports/flags (`?status=&page=`) |
| POST | `/api/admin/reports/<id>/resolve` | Resolve report (`{"verdict": "..."}`) |
| POST | `/api/admin/reports/<id>/dismiss` | Dismiss report (`{"note": "..."}`) |

### Payouts
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/payouts` | List payouts (`?status=&search=&page=`) |
| POST | `/api/admin/payouts/<id>/mark-paid` | Mark payout as paid |
| POST | `/api/admin/payouts/<id>/mark-unpaid` | Mark payout as unpaid |

### Comment Moderation
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/comments` | List comments (`?trade_id=&user_id=&page=`) |
| POST | `/api/admin/comments/<id>/reply` | Reply to comment (`{"content": "..."}`) |
| DELETE | `/api/admin/comments/<id>` | Delete comment |

### KYC
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/kyc` | List KYC requests (`?status=pending&page=`) |
| POST | `/api/admin/kyc/<user_id>/approve` | Approve KYC |
| POST | `/api/admin/kyc/<user_id>/reject` | Reject KYC |

### Analytics
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/analytics/revenue` | Monthly revenue (12 months) |
| GET | `/api/admin/analytics/users` | Weekly user registrations (12 weeks) |
| GET | `/api/admin/analytics/flags` | Weekly flags/reports trend |
| GET | `/api/admin/analytics/payouts` | Monthly payout totals |

### CSV Exports
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/admin/export/users` | Export all users as CSV |
| GET | `/api/admin/export/trades` | Export all trades as CSV |
| GET | `/api/admin/export/payouts` | Export all payouts as CSV |
| GET | `/api/admin/export/reports` | Export all reports as CSV |

---

## Setup

### Backend

1. Ensure the backend dependencies are installed:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

2. Configure your `.env` file (see `backend/.env.example`).

3. Run the backend:
   ```bash
   python run.py
   ```

### Frontend

The admin dashboard is pure HTML/CSS/JS — no build step required.

To serve locally, you can use any static server from the repository root:
```bash
# Python
python3 -m http.server 8000

# Or with npx
npx serve .
```

Then open: `http://localhost:8000/frontend/admin/login.html`

---

## Database

The `is_banned` column has been added to the `profiles` table. Run the following migration if upgrading an existing database:

```sql
ALTER TABLE profiles ADD COLUMN IF NOT EXISTS is_banned BOOLEAN NOT NULL DEFAULT FALSE;
```

---

## Security Notes

- All admin API endpoints require a valid JWT and `role = 'admin'` in the user's profile.
- Tokens are stored in `localStorage` under `tw_admin_token`.
- The "Ban User" action sets `is_active = false` and `is_banned = true` — this is **permanent** and cannot be undone via the UI.
- Suspended users can be reactivated; banned users cannot.
