# TradeWise — Canonical Route Map

This document is the authoritative reference for all navigation routes in the TradeWise application.

---

## Entry Point Flow

```
index.html
  └─► pages/auth.html               (sign up / log in)
        └─► pages/role-select.html  (choose role — fast-forwarded for returning users)
              ├─► "I am a Public Trader"
              │     └─► pages/profile-setup.html
              │               └─► frontend/learner/pages/dashboard.html
              └─► "I am an Experienced Trader"
                        └─► frontend/pages/dashboard.html
```

---

## Canonical Pages

| Step | File | Description | Auth Required |
|------|------|-------------|:---:|
| ① | `index.html` | Marketing landing page | No |
| ② | `pages/auth.html` | Unified sign-up / log-in | No |
| ③ | `pages/role-select.html` | Post-auth role chooser | Yes |
| ④ | `pages/profile-setup.html` | Public-trader onboarding | Yes |
| ⑤ | `frontend/pages/dashboard.html` | Experienced-trader main view | Yes |
| ⑥ | `frontend/learner/pages/dashboard.html` | Public-trader main view | Yes |

---

## Experienced Trader Pages (`frontend/pages/`)

| Page | File | Description |
|------|------|-------------|
| Dashboard | `dashboard.html` | Overview stats, recent trades |
| Analytics | `analytics.html` | Trade performance charts |
| Post Trade | `post-trade.html` | Submit a new trade idea |
| Active Trades | `active-trades.html` | Open positions |
| Earnings | `earnings.html` | Revenue & payout history |
| Subscribers | `subscribers.html` | Subscriber list & management |
| KYC Setup | `kyc-setup.html` | KYC document submission |
| Notifications | `notifications.html` | In-app notification feed |
| Profile | `profile-settings.html` | Public profile settings |
| Settings | `settings.html` | Account settings |
| Account | `account-settings.html` | Password, email, preferences |

---

## Public Trader (Learner) Pages (`frontend/learner/pages/`)

| Page | File | Description |
|------|------|-------------|
| Dashboard | `dashboard.html` | Overview stats, recent unlocks |
| Trade Feed | `feed.html` | Browse all pro-trader signals |
| Trade Detail | `trade-detail.html` | Full analysis for one trade |
| My History | `my-history.html` | Unlocked trades history |
| Subscriptions | `my-subscriptions.html` | Active & past subscriptions |
| Notifications | `notifications.html` | In-app notification feed |
| Notif Preferences | `notification-preferences.html` | Notification settings |
| Profile | `profile-settings.html` | Public profile |
| Account | `account-settings.html` | Password, email, preferences |
| Payment Callback | `payment-callback.html` | Cashfree payment return handler |

---

## Admin Pages (`frontend/admin/`)

| Page | File | Description |
|------|------|-------------|
| Admin Login | `login.html` | Admin-only authentication |
| Admin Dashboard | `dashboard.html` | KYC review, flag management |

---

## Auth Guard

Every protected page (all pages except `index.html` and `pages/auth.html`) checks for the presence of `tw_jwt_token` in `localStorage`. If absent, the user is redirected to `pages/auth.html`.

```
Protected page loads
  └─► Check localStorage.getItem('tw_jwt_token')
        ├─► Token present → continue loading page
        └─► Token absent  → window.location.href = '/pages/auth.html'
```

---

## Returning User Fast-Forward

`pages/role-select.html` applies the following logic on load to skip the role-selection UI for users who have already onboarded:

```
role-select.html loads
  └─► profile.role === 'pro_trader'
        └─► redirect → frontend/pages/dashboard.html

  └─► profile.role === 'public_trader'
        └─► GET /api/learner/profile
              ├─► has interests → redirect → frontend/learner/pages/dashboard.html
              └─► no interests  → show role-selection UI
```

---

## Deleted / Removed Pages

The following files were **hard-deleted** during the repository restructure:

| Removed Path | Reason |
|-------------|--------|
| `frontend/learner/pages/register.html` | Duplicate auth entry |
| `frontend/learner/pages/role-selection.html` | Duplicate role-select entry |
| `frontend/pages/register.html` | Duplicate auth entry |
| `frontend/learner/pages/profile-setup.html` | Duplicate profile-setup flow |
| `pages/dashboard.html` | Legacy standalone dashboard (Supabase-based) |
| `pages/pro-trader-coming-soon.html` | Obsolete placeholder |
| `frontend/index.html` | Legacy pro-trader splash page |
| `js/config.js` | Unused Supabase config (placeholder credentials) |
| `js/supabase.js` | Unused Supabase ESM export |
