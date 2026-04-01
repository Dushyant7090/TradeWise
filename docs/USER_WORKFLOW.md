# TradeWise — Complete User Workflow

> **Document scope:** Role-based journeys for all three user types on TradeWise —
> **Public Trader** (Learner), **Pro Trader** (Mentor), and **Admin**.
> Covers page-by-page navigation flows, decision points, and edge cases.

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Entry Point — Landing Page](#2-entry-point--landing-page)
3. [Role Selection](#3-role-selection)
4. [Public Trader (Learner) Journey](#4-public-trader-learner-journey)
5. [Pro Trader (Mentor) Journey](#5-pro-trader-mentor-journey)
6. [Admin Journey](#6-admin-journey)
7. [Shared Flows](#7-shared-flows)
8. [Decision Points & Edge Cases](#8-decision-points--edge-cases)
9. [Navigation Reference Map](#9-navigation-reference-map)

---

## 1. Platform Overview

TradeWise is a two-sided marketplace for evidence-based trade ideas on Indian equity markets (NSE/BSE).

| Role            | Core Value                                               | Key Actions                                          |
|-----------------|----------------------------------------------------------|------------------------------------------------------|
| Public Trader   | Learn the *why* behind every trade idea                  | Browse feed, unlock trades with credits, subscribe   |
| Pro Trader      | Share expertise, build a verified track record, earn     | Post trades with charts, grow subscribers, get paid  |
| Admin           | Keep the platform trustworthy and operational            | KYC review, moderation, payouts, analytics           |

---

## 2. Entry Point — Landing Page

**File:** `frontend/landing-page.html`

The landing page is the first screen every visitor sees when the app is opened locally (`http://localhost:5500/landing-page.html`) or deployed.

### Page sections

| Section              | Description                                                     |
|----------------------|-----------------------------------------------------------------|
| Navigation bar       | Links to anchors + "Get Started" button                        |
| Hero                 | Headline, sub-headline, hero CTA                               |
| Value Props          | Three value columns for learners                               |
| How It Works (HiW)   | Side-by-side learner vs. mentor flows with separate CTAs       |
| Features             | Feature cards for both roles                                   |
| Trust & Security     | Social proof and security badges                               |
| Bottom CTA           | Final sign-up push                                             |
| Footer               | Links to legal, support, social                                |

### CTA routing table

| Button / Link                        | Location in page        | Destination                              |
|--------------------------------------|-------------------------|------------------------------------------|
| **Get Started** (nav bar)            | Top navigation          | `pages/role-selection.html`              |
| **Get Started** (hero)               | Hero section            | `pages/role-selection.html`              |
| **Get Started Free** (How It Works)  | Learner HiW column      | `learner/pages/auth.html`                |
| **Apply as Mentor** (How It Works)   | Mentor HiW column       | `pro-trader/pages/register.html`         |
| **Get Started Free** (Bottom CTA)    | Bottom CTA section      | `learner/pages/auth.html`                |

---

## 3. Role Selection

**File:** `frontend/pages/role-selection.html`

Reached via the generic "Get Started" CTAs. Visitors who already know their role can bypass this page using the direct CTAs.

### Flow

```
[Visit landing-page.html]
        │
        ▼
[Click "Get Started" (nav or hero)]
        │
        ▼
[pages/role-selection.html]
        │
   ┌────┴────┐
   │         │
   ▼         ▼
Public    Pro Trader
Trader    (Experienced
           Trader)
   │         │
   ▼         ▼
learner/  pro-trader/
pages/    pages/
auth.html register.html
```

### Decision point: role card selection

- User must click a role card to enable the "Continue" button (disabled by default).
- Selecting Public Trader highlights that card; Pro Trader highlights the other.
- Clicking Continue routes to the role-specific auth page.

---

## 4. Public Trader (Learner) Journey

### 4.1 Authentication

**File:** `frontend/learner/pages/auth.html`

The auth page contains three in-place views toggled by JS:

| View               | Trigger                                  | Fields                                        |
|--------------------|------------------------------------------|-----------------------------------------------|
| **Sign Up** (default) | First visit or "Create account" link   | Full Name, Email, Password (+ strength meter) |
| **Log In**         | "Log in" toggle link                     | Email, Password                               |
| **Forgot Password**| "Forgot your password?" link             | Email                                         |

**Registration API call:**
```
POST /api/auth/register
{ email, password, display_name, role: "public_trader" }
```
→ Returns JWT token + user object. On success, stores token in `localStorage` and redirects to **Profile Setup**.

**Login API call:**
```
POST /api/auth/login
{ email, password }
```
→ Returns JWT. On success, stores token and redirects to **Dashboard**.

**Error states:**
- Invalid email format → inline field error.
- Password < 8 chars → inline field error.
- Email already registered → API error message in banner.
- Wrong credentials on login → API error message in banner.
- Network failure → generic connection error.

### 4.2 Profile Setup (first login only)

**File:** `frontend/learner/pages/profile-setup.html`

A 4-step onboarding wizard:

| Step | Title         | Content                                            | Skip? |
|------|---------------|----------------------------------------------------|-------|
| 1    | Interests     | Multi-select chips: markets (Nifty 50, Crypto…)    | No    |
| 2    | Experience    | Single-select: Beginner / Intermediate / Advanced  | No    |
| 3    | Goal          | Single-select: Learn / Earn / Both                 | No    |
| 4    | Disclaimer    | Risk disclosure acknowledgement                    | No    |

After completing all steps → redirects to **Dashboard**.

### 4.3 Dashboard

**File:** `frontend/learner/pages/dashboard.html`

```
┌──────────────────────────────────────────────────────┐
│  Sidebar                    │  Main Content           │
│  ─────────────────────────  │  ─────────────────────  │
│  ● Dashboard (active)       │  Welcome back, <name>   │
│  ● Trade Feed               │  Credit bar + count     │
│  ── My Learning ──          │  Stats grid (4 cards)   │
│  ● My History               │  Featured Pro Traders   │
│  ● Subscriptions            │  Recent trades          │
│  ── Account ──              │                         │
│  ● Notifications            │                         │
│  ● Profile                  │                         │
│  ● Settings                 │                         │
└──────────────────────────────────────────────────────┘
```

**Key stats displayed:**
- Available Credits (starts at 7)
- Trades Unlocked
- Active Subscriptions
- Win Rate Observed
- Day Streak

**Credits system:** 1 credit unlocks full analysis of 1 trade.

### 4.4 Trade Feed

**File:** `frontend/learner/pages/feed.html`

Displays all active trade ideas from verified Pro Traders.

**Filters available:**
- Market (Nifty 50, Crypto, Forex, etc.)
- Pro Trader name
- Accuracy range (min–max %)
- Sort by: Newest / Highest Accuracy / Most Views / Most Subscribers

**Trade card actions:**

| Action                     | Condition             | Result                                              |
|----------------------------|-----------------------|-----------------------------------------------------|
| View teaser (free)         | Always                | Shows symbol, direction, brief rationale            |
| Unlock full analysis       | Has credits           | Deducts 1 credit; shows chart, targets, stop-loss  |
| Unlock full analysis       | No credits remaining  | Prompts to buy credit pack via Cashfree payment     |
| Subscribe to pro trader    | Logged in             | Opens subscription plan selector → payment flow    |

→ Clicking a trade card opens **Trade Detail**.

### 4.5 Trade Detail

**File:** `frontend/learner/pages/trade-detail.html`

Shows full trade information after unlocking:

- Symbol, market, direction (Long/Short)
- Entry price, Stop Loss, Target price(s)
- Technical rationale text
- Chart images (lightbox on click)
- Pro Trader's accuracy record
- Unlock button (if not yet unlocked)
- Flag / Report button → opens report modal
- Rate this trade → opens rating modal

**Decision point — unlocking:**
```
[View trade card on feed]
        │
   Has credits?
   ┌────┴─────┐
  Yes         No
   │          │
   ▼          ▼
Deduct 1   Show credit
credit     purchase modal
   │          │
   ▼          └──► [Payment flow] ──► [payment-callback.html]
Full trade              (Cashfree)
content shown
```

### 4.6 My History

**File:** `frontend/learner/pages/my-history.html`

Lists all trades the user has previously unlocked, with outcome tracking (if the trade has closed).

### 4.7 My Subscriptions

**File:** `frontend/learner/pages/my-subscriptions.html`

Lists active and past subscriptions to Pro Traders.

| Action               | Result                                          |
|----------------------|-------------------------------------------------|
| Subscribe (new)      | Opens plan selector → Cashfree payment flow     |
| Cancel subscription  | Marks subscription as cancelled at period end   |
| Renew subscription   | Reopens payment flow                            |

### 4.8 Notifications

**File:** `frontend/learner/pages/notifications.html`

Inbox for:
- New trade ideas from subscribed Pro Traders
- Subscription renewal reminders
- Credit low-balance alerts
- Trade outcome updates (closed trade result)

### 4.9 Profile Settings

**File:** `frontend/learner/pages/profile-settings.html`

Editable fields:
- Display name
- Avatar / profile picture
- Trading interests
- Experience level
- Notification preferences

### 4.10 Account Settings

**File:** `frontend/learner/pages/account-settings.html`

- Change email / password
- 2FA setup
- Delete account

### 4.11 Payment Callback

**File:** `frontend/learner/pages/payment-callback.html`

Landing page after Cashfree payment redirect. Displays success or failure and redirects back to the feed or subscriptions page.

---

## 5. Pro Trader (Mentor) Journey

### 5.1 Authentication

**File:** `frontend/pro-trader/pages/register.html`

Reached via "Apply as Mentor" CTA or role selection → Pro Trader path.

Three in-place views (same structure as Public Trader auth):

| View               | Default | Fields                                    |
|--------------------|---------|-------------------------------------------|
| **Sign Up**        | ✓       | Full Name, Email, Password (strength bar) |
| **Log In**         |         | Email, Password                           |
| **Forgot Password**|         | Email                                     |

**Registration API call:**
```
POST /api/auth/register
{ email, password, display_name, role: "pro_trader" }
```
→ On success, stores JWT in `localStorage` and redirects to **KYC Setup**.

**Login API call:**
```
POST /api/auth/login
{ email, password }
```
→ On success, redirects to **Pro Trader Dashboard**.

### 5.2 KYC & Bank Setup (required before withdrawals)

**File:** `frontend/pro-trader/pages/kyc-setup.html`

New Pro Traders must complete identity and bank verification before they can receive earnings.

**Documents required:**

| Document          | Format                       | Max Size |
|-------------------|------------------------------|----------|
| PAN Card          | JPG, PNG, PDF                | 5 MB     |
| Government ID     | Aadhaar / Passport / Voter   | 5 MB     |
| Bank Statement    | Last 3 months                | 5 MB     |

**KYC status flow:**
```
[not_submitted] → [pending_review] → [verified]
                                  ↘ [rejected] → (resubmit)
```

Admin reviews submitted documents and approves or rejects (see Admin section).
Earnings can only be withdrawn once status is `verified`.

### 5.3 Dashboard

**File:** `frontend/pro-trader/pages/dashboard.html`

```
┌──────────────────────────────────────────────────────┐
│  Sidebar                    │  Main Content           │
│  ─────────────────────────  │  ─────────────────────  │
│  ─ Overview ─               │  Welcome back, <name>   │
│  ● Dashboard (active)       │  Metrics grid (4 cards) │
│  ● Analytics                │  - Accuracy Score       │
│  ─ Trading ─                │  - Active Trades count  │
│  ● Post Trade               │  - Total Subscribers    │
│  ● Active Trades            │  - Monthly Earnings     │
│  ─ Monetization ─           │  Recent activity        │
│  ● Earnings                 │  Performance charts     │
│  ● Subscribers              │                         │
│  ─ Account ─                │                         │
│  ● KYC Setup                │                         │
│  ● Notifications            │                         │
│  ● Profile                  │                         │
│  ● Settings                 │                         │
└──────────────────────────────────────────────────────┘
```

### 5.4 Post a Trade

**File:** `frontend/pro-trader/pages/post-trade.html`

Allows verified Pro Traders to publish a new trade idea.

**Form fields:**

| Field              | Type                                         | Required |
|--------------------|----------------------------------------------|----------|
| Symbol             | Text (e.g., RELIANCE, NIFTY)                 | ✓        |
| Market / Segment   | Dropdown (Equity, F&O, Crypto…)              | ✓        |
| Direction          | Radio (Long / Short)                         | ✓        |
| Entry Price        | Number                                       | ✓        |
| Stop Loss          | Number                                       | ✓        |
| Target Price(s)    | Number (multiple targets supported)          | ✓        |
| Rationale          | Rich text / textarea                         | ✓        |
| Chart Images       | File upload (JPG/PNG, max 5MB each)          | ✓        |
| Time Frame         | Dropdown (Intraday / Swing / Positional)     | ✓        |
| Risk Level         | Dropdown (Low / Medium / High)               |          |

**On submit:**
```
POST /api/trades
```
→ Trade is published and immediately visible in the learner feed.
→ Subscribed learners receive a push notification.
→ Redirects to **Active Trades**.

### 5.5 Active Trades

**File:** `frontend/pro-trader/pages/active-trades.html`

Lists all open trade ideas posted by this Pro Trader.

| Action                  | Result                                                    |
|-------------------------|-----------------------------------------------------------|
| Close trade (Hit Target)| Marks trade as closed with outcome = `target_hit`        |
| Close trade (Stop Loss) | Marks trade as closed with outcome = `stop_loss_hit`     |
| Edit trade details      | Opens edit form (limited fields editable after publish)   |
| Delete trade            | Soft-deletes the trade (not visible in feed)              |

### 5.6 Analytics

**File:** `frontend/pro-trader/pages/analytics.html`

Detailed performance statistics:

- Overall Accuracy % (targets hit / total closed trades)
- Win/Loss breakdown chart
- Average risk-reward ratio
- Accuracy over time (line chart)
- Performance by market segment
- Top performing symbols

### 5.7 Earnings

**File:** `frontend/pro-trader/pages/earnings.html`

Financial overview:

| Metric                    | Description                                               |
|---------------------------|-----------------------------------------------------------|
| Monthly earnings          | 90% of subscription revenue collected this month         |
| Pending payout            | Amount due but not yet disbursed                          |
| Total earned to date      | Lifetime earnings                                         |
| Revenue split detail      | 90% Pro Trader / 10% Platform per transaction            |
| Payout history            | Table of past disbursements with dates and amounts        |

**Payout eligibility:** Requires KYC status = `verified`.

### 5.8 Subscribers

**File:** `frontend/pro-trader/pages/subscribers.html`

Lists active and past subscribers:

- Subscriber count
- Subscriber growth chart
- Plan type (monthly / quarterly / annual)
- Subscription start and renewal dates

### 5.9 Notifications

**File:** `frontend/pro-trader/pages/notifications.html`

Inbox for:
- New subscriber alerts
- Subscription renewal confirmations
- KYC approval/rejection updates
- Platform announcements

### 5.10 Profile Settings

**File:** `frontend/pro-trader/pages/profile-settings.html`

- Display name and bio
- Profile photo
- Trading style description
- Social links
- Markets specialised in

### 5.11 Settings

**File:** `frontend/pro-trader/pages/settings.html`

- Change email / password
- 2FA configuration
- Notification preferences
- Delete account

---

## 6. Admin Journey

### 6.1 Admin Login

**File:** `frontend/secure-access/admin/index.html`

A private, unlisted admin login page protected by a server-side role check. Admins authenticate with their email/password; the backend verifies `role = 'admin'` before issuing a privileged session.

→ On success, redirects to **Admin Dashboard**.

### 6.2 Admin Dashboard

**File:** `frontend/admin/dashboard.html`

Single-page application with sections toggled in the sidebar:

```
┌──────────────────────────────────────────────────────┐
│  Sidebar                    │  Main Content           │
│  ─────────────────────────  │  ─────────────────────  │
│  ─ Overview ─               │  Section content        │
│  ● Dashboard (metrics)      │  (switches based on     │
│  ● Analytics                │   nav selection)        │
│  ─ Management ─             │                         │
│  ● Users           [count]  │                         │
│  ● Trades                   │                         │
│  ● Payouts      [pending🟡] │                         │
│  ─ Moderation ─             │                         │
│  ● Reports & Flags  [🔴]   │                         │
│  ● Comments                 │                         │
│  ● KYC Verification [🟡]   │                         │
└──────────────────────────────────────────────────────┘
```

#### Section: Dashboard (Overview)

Real-time platform metrics:
- Total users (Public Traders, Pro Traders)
- Active subscriptions
- Gross revenue (MTD)
- Platform share (10% of gross)
- Pending KYC reviews
- Open reports / flags

#### Section: Analytics

Charts and breakdowns:
- User growth over time
- Revenue trend
- Top Pro Traders by subscriber count
- Trade accuracy distribution

#### Section: Users

Table of all registered users with:
- Filter by role, status, registration date
- Suspend / reactivate account
- View profile details

#### Section: Trades

Table of all posted trades:
- Filter by trader, market, status (open / closed)
- Remove / hide trade (moderation)
- View trade detail

#### Section: Payouts

Pending and processed payouts:
- Approve payout to verified Pro Trader
- Mark payout as processed
- View payout history

#### Section: Reports & Flags

Learner-submitted reports on trade ideas:

| Report Reason         | Admin Action options                         |
|-----------------------|----------------------------------------------|
| Fake / fabricated     | Dismiss report / Remove trade / Warn trader  |
| Misleading analysis   | Dismiss / Remove / Warn                      |
| Copied content        | Dismiss / Remove / Warn                      |
| Inappropriate content | Dismiss / Remove / Suspend account           |
| Spam                  | Dismiss / Remove                             |

#### Section: Comments

Moderate comment threads on trades:
- Delete individual comments
- Lock / unlock threads

#### Section: KYC Verification

Review Pro Trader document submissions:

| Action    | Effect                                                         |
|-----------|----------------------------------------------------------------|
| Approve   | Sets KYC status to `verified`; enables withdrawal for trader  |
| Reject    | Sets status to `rejected`; notifies trader to resubmit        |
| Request more info | Sends message to trader asking for additional docs   |

---

## 7. Shared Flows

### 7.1 Logout

All roles have a "Sign Out" button in the top bar or sidebar footer.

| Role          | Logout clears                        | Redirects to                      |
|---------------|--------------------------------------|-----------------------------------|
| Public Trader | JWT token + user data in localStorage| `learner/pages/auth.html`         |
| Pro Trader    | JWT token + user data in localStorage| `pro-trader/pages/register.html`  |
| Admin         | Admin session                        | `secure-access/admin/index.html`  |

### 7.2 Session Expiry / Unauthenticated Access

Protected pages call an auth guard on load. If no valid JWT is found:

| Role          | Redirects to                        |
|---------------|-------------------------------------|
| Public Trader | `/pages/auth.html`                  |
| Pro Trader    | `pro-trader/pages/register.html`    |
| Admin         | `secure-access/admin/index.html`    |

### 7.3 Password Reset

Available from both auth pages:

```
[Click "Forgot your password?"]
        │
        ▼
[Enter email in forgot-view]
        │
        ▼
POST /api/auth/forgot-password
        │
        ▼
[Email sent with reset link]
        │
        ▼
[User clicks link in email]
        │
        ▼
[Reset password page (server-side)]
```

### 7.4 Credit Purchase (Public Trader)

```
[Credits run out while trying to unlock a trade]
        │
        ▼
[Credit purchase modal shown]
        │
        ▼
[Select credit pack (e.g., 10 credits, 25 credits)]
        │
        ▼
[Cashfree payment gateway]
        │
   ┌────┴─────┐
 Success     Failure
   │           │
   ▼           ▼
Credits     Error shown;
added;      user can retry
payment-
callback.html
```

---

## 8. Decision Points & Edge Cases

### 8.1 New vs. Returning User

| Scenario                            | Behaviour                                            |
|-------------------------------------|------------------------------------------------------|
| First-time Public Trader signup     | After auth → Profile Setup wizard → Dashboard        |
| Returning Public Trader login       | After auth → Dashboard (setup already done)          |
| First-time Pro Trader signup        | After auth → KYC Setup → Dashboard (limited until KYC approved) |
| Returning Pro Trader login          | After auth → Pro Trader Dashboard                    |

### 8.2 Pro Trader Without Approved KYC

- Can post trade ideas.
- Cannot withdraw earnings.
- KYC Setup page shows pending/rejected status banner with resubmit option.
- Earnings page shows "KYC required" banner if KYC is not verified.

### 8.3 Public Trader With Zero Credits

- Can browse the feed and see trade teasers.
- Clicking "Unlock" on a trade shows a credit purchase modal.
- Can still view previously unlocked trades in **My History**.
- Subscriptions remain active and unaffected by credit balance.

### 8.4 Suspended Account

- Attempting to log in returns a `403 account suspended` error from the API.
- Auth page shows the error message in the banner.
- Admin can reactivate the account from the Users section.

### 8.5 Invalid/Expired JWT

- API returns `401 Unauthorized`.
- Frontend attempts a token refresh via `/api/auth/refresh-token`.
- If refresh fails, all stored auth data is cleared and user is redirected to login.

### 8.6 Role Mismatch on Login

- A Public Trader using the Pro Trader login page will authenticate successfully (same `/api/auth/login` endpoint).
- However, they will be redirected to the Pro Trader dashboard, which will display empty/incorrect data.
- **Best practice:** Use the correct auth page per role to ensure proper post-login routing.

### 8.7 Network / Server Errors

- All API calls include `.catch()` handlers.
- On network failure, a user-friendly error message is shown in the auth banner or toast.
- Retry is manual (re-submit the form).

---

## 9. Navigation Reference Map

```
frontend/
├── landing-page.html                  ← Entry point (all visitors)
│
├── pages/
│   └── role-selection.html            ← Role chooser (Public or Pro Trader)
│
├── learner/
│   └── pages/
│       ├── auth.html                  ← Public Trader sign up / log in
│       ├── profile-setup.html         ← Onboarding wizard (first login only)
│       ├── dashboard.html             ← Main home screen
│       ├── feed.html                  ← Browse & unlock trade ideas
│       ├── trade-detail.html          ← Full trade view + report/rate
│       ├── my-history.html            ← Previously unlocked trades
│       ├── my-subscriptions.html      ← Manage Pro Trader subscriptions
│       ├── notifications.html         ← Notification inbox
│       ├── profile-settings.html      ← Edit profile
│       ├── account-settings.html      ← Change email/password, 2FA, delete
│       ├── payment-callback.html      ← Post-Cashfree-payment landing
│       └── register.html              ← (legacy; unused — redirects to auth.html)
│
├── pro-trader/
│   └── pages/
│       ├── register.html              ← Pro Trader sign up / log in
│       ├── kyc-setup.html             ← Identity & bank document upload
│       ├── dashboard.html             ← Pro Trader home screen
│       ├── post-trade.html            ← Post a new trade idea
│       ├── active-trades.html         ← Manage open trades
│       ├── analytics.html             ← Performance statistics
│       ├── earnings.html              ← Revenue & payout overview
│       ├── subscribers.html           ← Subscriber list & growth
│       ├── notifications.html         ← Notification inbox
│       ├── profile-settings.html      ← Edit public profile
│       ├── account-settings.html      ← Change email/password, 2FA, delete
│       └── settings.html              ← Notification preferences
│
├── admin/
│   ├── index.html                     ← Admin panel landing (redirects)
│   └── dashboard.html                 ← Admin SPA dashboard
│
├── secure-access/
│   └── admin/
│       └── index.html                 ← Admin login gate
│
└── shared/
    ├── css/                           ← Global CSS (globals, auth, components, pages)
    ├── js/                            ← Shared JS utilities (api, auth, utils…)
    └── assets/
        └── logo.svg
```

---

*Last updated: 2026-04-01 — reflects the navigation implementation as of this commit.*
