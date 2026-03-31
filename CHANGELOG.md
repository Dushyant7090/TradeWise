# Changelog

All notable changes to TradeWise are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Changed — Repository Restructure
- Moved shared frontend CSS from `frontend/css/` to `frontend/shared/css/`.
- Moved shared frontend JS from `frontend/js/` to `frontend/shared/js/`.
- Moved brand logo (`logo.svg`) to `frontend/shared/assets/`.
- Moved admin styles and scripts into `frontend/admin/css/` and `frontend/admin/js/`.
- Renamed `frontend/admin/login.html` → `frontend/admin/index.html`.
- Moved legacy pro-trader pages from `frontend/pages/` into `frontend/pro-trader/pages/`.
- Added `frontend/pro-trader/css/pro-trader.css` and `frontend/pro-trader/js/pro-trader.js`.
- Moved `supabase/schema.sql` → `supabase/migrations/001_initial_schema.sql`.
- Added `backend/app/middleware/auth_middleware.py` and `backend/app/middleware/rate_limit.py`.
- Renamed `backend/app/models/learner_unlocked_trade.py` → `learner_trade_unlock.py`.
- Renamed `backend/app/models/learner_credits_log.py` → `learner_credit_transaction.py`.
- Added `backend/app/models/learner_subscription.py`.
- Added `backend/app/routes/learner_dashboard.py`.
- Added GitHub Actions CI workflows for backend and frontend.
- Removed legacy root-level assets (`index.html`, `styles.css`, `script.js`, `css/`, `js/`, `pages/`).
- Updated all HTML files to use correct relative paths after moves.

---

## [0.1.0] — 2026-03-09 — Initial Release

### Added
- Pro Trader dashboard: post trades, manage active trades, view analytics and earnings.
- Learner dashboard: browse trade signals, unlock analyses, manage subscriptions.
- Admin dashboard: user management, KYC verification, trade monitoring, payouts.
- Supabase PostgreSQL integration with Row Level Security.
- Cashfree payment gateway integration with 90/10 revenue split.
- JWT-based authentication with role-based access control.
- Real-time notifications via Supabase Realtime.
- Credit system for learners to unlock trade analyses.
- Export functionality (CSV) for trades and earnings.
