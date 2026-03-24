# TradeWise — Database Schema Documentation

This document describes all tables in the TradeWise Supabase PostgreSQL database, including columns, constraints, relationships, and usage notes.

> **Production initialization:** Use [`supabase/init.sql`](../supabase/init.sql) to initialize a brand-new database.
> This single atomic script creates all 20 tables, 17 ENUM types, all indexes, and all RLS policies.
> Run it with:
> ```bash
> psql "$DATABASE_URL" -f supabase/init.sql
> ```
> or paste it into the Supabase SQL editor.

The legacy Supabase-native schema is still available in [`supabase/schema.sql`](../supabase/schema.sql) and
[`supabase/rls-policies.sql`](../supabase/rls-policies.sql) for reference.

---

## Table of Contents

1. [Entity Relationship Overview](#entity-relationship-overview)
2. [Table Definitions](#table-definitions)
   - [profiles](#1-profiles)
   - [trades](#2-trades)
   - [mentor_stats](#3-mentor_stats)
   - [unlocked_trades](#4-unlocked_trades)
   - [subscription_plans](#5-subscription_plans)
   - [subscriptions](#6-subscriptions)
   - [reports](#7-reports)
   - [comments](#8-comments)
   - [notifications](#9-notifications)
   - [wallet](#10-wallet)
   - [transactions](#11-transactions)
   - [platform_settings](#12-platform_settings)
3. [Key Relationships](#key-relationships)
4. [Row Level Security Summary](#row-level-security-summary)
5. [Database Indexes](#database-indexes)
6. [Default Platform Settings](#default-platform-settings)

---

## Entity Relationship Overview

```
auth.users (Supabase Auth)
    │
    └── profiles (1:1) ────────────────────────────────────────────┐
         │                                                           │
         ├── trades (mentor_id → profiles.id)                       │
         │     │                                                     │
         │     ├── unlocked_trades (trade_id → trades.id)           │
         │     │       └── user_id → profiles.id                    │
         │     │                                                     │
         │     ├── comments (trade_id → trades.id)                  │
         │     │       └── user_id → profiles.id                    │
         │     │                                                     │
         │     └── reports (trade_id → trades.id)                   │
         │             └── reporter_id → profiles.id                │
         │                                                           │
         ├── mentor_stats (mentor_id → profiles.id)                 │
         │                                                           │
         ├── subscription_plans (mentor_id → profiles.id)           │
         │     └── subscriptions (plan_id → subscription_plans.id)  │
         │             ├── public_trader_id → profiles.id            │
         │             └── mentor_id → profiles.id                  │
         │                                                           │
         ├── wallet (mentor_id → profiles.id)                       │
         ├── transactions (mentor_id → profiles.id)                 │
         └── notifications (user_id → profiles.id) ────────────────┘
```

---

## Table Definitions

### 1. profiles

Extends Supabase's built-in `auth.users` table. Every user — pro-trader, learner, or admin — has exactly one profile row.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | — | PK, FK → `auth.users.id` | Matches Supabase Auth user ID |
| `full_name` | TEXT | — | NOT NULL | Display name |
| `role` | TEXT | `public_trader` | NOT NULL, CHECK | `public_trader`, `pro_trader`, or `admin` |
| `avatar_url` | TEXT | NULL | — | Supabase Storage URL for profile picture |
| `interests` | TEXT[] | `{}` | — | Learner's market interests e.g. `['nifty50', 'crypto']` |
| `experience_level` | TEXT | NULL | CHECK | `beginner` or `intermediate` |
| `bio` | TEXT | NULL | — | Profile bio (pro-traders: min 100 chars) |
| `market_focus` | TEXT[] | `{}` | — | Pro-trader's market specializations |
| `external_links` | JSONB | `{}` | — | Social links (Twitter, TradingView, etc.) |
| `cashfree_account_id` | TEXT | NULL | — | Cashfree linked account for payouts |
| `is_verified` | BOOLEAN | `false` | — | KYC verification status |
| `subscription_price` | INTEGER | `0` | — | Monthly subscription price in **paise** (₹500 = 50000) |
| `credits` | INTEGER | `7` | — | Remaining unlock credits (learners only) |
| `disclaimer_accepted` | BOOLEAN | `false` | — | Financial disclaimer acceptance |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | Account creation timestamp |

**Notes:**
- `credits = 7` at signup for learners — decrements by 1 on each trade unlock
- `subscription_price = 0` means the pro-trader hasn't set a price yet
- `is_verified = true` after admin approves KYC

---

### 2. trades

Trade signals posted by pro-traders (mentors). Each row represents one trading idea.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | Trade ID |
| `mentor_id` | UUID | — | NOT NULL, FK → `profiles.id` | Pro-trader who posted |
| `symbol` | TEXT | — | NOT NULL | NSE/BSE symbol e.g. `RELIANCE`, `NIFTY50` |
| `direction` | TEXT | — | NOT NULL, CHECK | `BUY` or `SELL` |
| `entry_price` | DECIMAL | — | NOT NULL | Entry price level |
| `stop_loss` | DECIMAL | — | NOT NULL | Stop loss price |
| `target_price` | DECIMAL | — | NOT NULL | Target price |
| `risk_reward_ratio` | DECIMAL | — | NOT NULL | Auto-calculated RRR |
| `rationale` | TEXT | — | NOT NULL | Technical analysis (min 50 words) |
| `chart_image_url` | TEXT | NULL | — | Supabase Storage URL for chart |
| `trade_status` | TEXT | `ACTIVE` | NOT NULL, CHECK | `ACTIVE`, `WIN`, or `LOSS` |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | Posted timestamp |
| `closed_at` | TIMESTAMPTZ | NULL | — | Set when trade is closed |

**RRR Calculation:**
```sql
-- For BUY:
risk_reward_ratio = (target_price - entry_price) / (entry_price - stop_loss)

-- For SELL:
risk_reward_ratio = (entry_price - target_price) / (stop_loss - entry_price)
```

**Indexes:** `mentor_id`, `trade_status`, `created_at DESC`

---

### 3. mentor_stats

Aggregated performance statistics for each pro-trader. Updated whenever a trade is closed.

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `mentor_id` | UUID | — | PK, FK → `profiles.id` |
| `total_trades` | INTEGER | `0` | All closed trades |
| `winning_trades` | INTEGER | `0` | Trades where `trade_status = WIN` |
| `losing_trades` | INTEGER | `0` | Trades where `trade_status = LOSS` |
| `accuracy_pct` | DECIMAL | `0.0` | `(winning_trades / total_trades) × 100` |
| `avg_risk_reward` | DECIMAL | `0.0` | Average RRR across all closed trades |

**When is this updated?**
Every time a trade is closed (via `/api/pro-trader/trades/{id}/close`), the backend recalculates and updates this row.

---

### 4. unlocked_trades

Tracks which learners have unlocked (paid 1 credit to view) which trades.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `user_id` | UUID | — | NOT NULL, FK → `profiles.id` | Learner who unlocked |
| `trade_id` | UUID | — | NOT NULL, FK → `trades.id` | Trade that was unlocked |
| `unlocked_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | Unlock timestamp |

**Unique constraint:** `(user_id, trade_id)` — a learner can only unlock a trade once.

**Index:** `user_id`

**How unlocks work:**
1. Learner calls `POST /api/learner/trades/{id}/unlock`
2. Backend checks `profiles.credits > 0` — if not, returns 402
3. Backend deducts 1 from `profiles.credits`
4. Backend inserts a row into `unlocked_trades`
5. Subsequent reads of this trade return full (unblurred) details

---

### 5. subscription_plans

Pricing options set by each pro-trader. Supports 1, 3, or 6 month durations.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `mentor_id` | UUID | — | NOT NULL, FK → `profiles.id` | Pro-trader who owns this plan |
| `duration_months` | INTEGER | — | NOT NULL, CHECK (1, 3, 6) | Plan duration in months |
| `price` | INTEGER | — | NOT NULL, > 0 | Price in **paise** |
| `is_active` | BOOLEAN | `true` | NOT NULL | Whether this plan is currently offered |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | — |

**Unique constraint:** `(mentor_id, duration_months)` — one price per duration per trader.

**Index:** `mentor_id`

---

### 6. subscriptions

Active or expired subscription relationships between learners and pro-traders.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `public_trader_id` | UUID | — | NOT NULL, FK → `profiles.id` | Learner who subscribed |
| `mentor_id` | UUID | — | NOT NULL, FK → `profiles.id` | Pro-trader being subscribed to |
| `plan_id` | UUID | — | NOT NULL, FK → `subscription_plans.id` | Which plan was purchased |
| `cashfree_payment_id` | TEXT | NULL | — | Cashfree payment reference |
| `status` | TEXT | `active` | NOT NULL, CHECK | `active` or `expired` |
| `start_date` | TIMESTAMPTZ | `NOW()` | NOT NULL | Subscription start |
| `end_date` | TIMESTAMPTZ | — | NOT NULL | Subscription expiry |

**Indexes:** `public_trader_id`, `mentor_id`, `status`

**How subscriptions bypass credits:**
When a learner accesses a trade, the backend checks:
```sql
SELECT id FROM subscriptions
WHERE public_trader_id = <learner_id>
AND mentor_id = <trade.mentor_id>
AND status = 'active'
AND end_date > NOW()
LIMIT 1;
```
If a row exists → no credit deduction, full details returned.

---

### 7. reports

User-submitted flags for suspicious or misleading trade signals.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `reporter_id` | UUID | — | NOT NULL, FK → `profiles.id` | Learner who reported |
| `trade_id` | UUID | — | NOT NULL, FK → `trades.id` | Trade being reported |
| `reason` | TEXT | — | NOT NULL | Reporter's explanation |
| `category` | TEXT | — | NOT NULL, CHECK | `misleading_chart`, `low_effort`, `manipulated` |
| `status` | TEXT | `pending` | NOT NULL, CHECK | `pending` or `resolved` |
| `admin_action` | TEXT | NULL | CHECK | `warning`, `suspension`, or `penalty` |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | — |

**Indexes:** `status`, `trade_id`

**Flag threshold:** When a trade accumulates ≥ 10 pending reports, the platform creates an alert notification for admins. This threshold is configurable in `platform_settings.max_report_flags_before_alert`.

---

### 8. comments

Discussion threads on trade signals.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `trade_id` | UUID | — | NOT NULL, FK → `trades.id` | Trade being discussed |
| `user_id` | UUID | — | NOT NULL, FK → `profiles.id` | Comment author |
| `content` | TEXT | — | NOT NULL | Comment text |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | — |

**Indexes:** `trade_id`, `(trade_id, created_at)`

**Authorization rules:**
- Users can only edit/delete their own comments
- Any authenticated user can read comments on a trade they've unlocked or subscribed to

---

### 9. notifications

In-app notification queue for all user types.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `user_id` | UUID | — | NOT NULL, FK → `profiles.id` | Recipient |
| `type` | TEXT | — | NOT NULL, CHECK | `new_trade`, `trade_closed`, `flag_alert`, `subscription` |
| `title` | TEXT | — | NOT NULL | Short notification title |
| `message` | TEXT | — | NOT NULL | Full notification text |
| `link` | TEXT | NULL | — | Deep link to relevant page |
| `is_read` | BOOLEAN | `false` | NOT NULL | Read/unread state |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | — |

**Indexes:** `user_id`, `(user_id, is_read)` WHERE `is_read = false` (partial index for performance)

**Realtime:** Notifications are delivered via Supabase Realtime. The frontend subscribes to the `notifications` channel filtered by the current user's ID.

---

### 10. wallet

Pro-trader earnings ledger. All amounts stored in **paise** (₹1 = 100 paise).

| Column | Type | Default | Description |
|--------|------|---------|-------------|
| `mentor_id` | UUID | — | PK, FK → `profiles.id` |
| `total_earnings` | INTEGER | `0` | Lifetime earnings in paise |
| `available_balance` | INTEGER | `0` | Withdrawable balance |
| `pending_balance` | INTEGER | `0` | Balance in pending payouts |

**Revenue split:** When a subscription payment is processed:
```
trader_amount = total_payment × 0.90
platform_amount = total_payment × 0.10
wallet.available_balance += trader_amount
```

---

### 11. transactions

Pro-trader financial transaction history.

| Column | Type | Default | Constraints | Description |
|--------|------|---------|-------------|-------------|
| `id` | UUID | `gen_random_uuid()` | PK | — |
| `mentor_id` | UUID | — | NOT NULL, FK → `profiles.id` | Pro-trader |
| `amount` | INTEGER | — | NOT NULL | Amount in paise (positive = earning, negative = withdrawal) |
| `type` | TEXT | — | NOT NULL, CHECK | `earning` or `withdrawal` |
| `cashfree_transfer_id` | TEXT | NULL | — | Cashfree reference for withdrawals |
| `description` | TEXT | NULL | — | Human-readable description |
| `created_at` | TIMESTAMPTZ | `NOW()` | NOT NULL | — |

**Indexes:** `mentor_id`, `(mentor_id, created_at DESC)`

---

### 12. platform_settings

Admin-configurable key-value store for platform parameters.

| Column | Type | Description |
|--------|------|-------------|
| `key` | TEXT | PK. Setting name |
| `value` | TEXT | Setting value (stored as text) |
| `updated_by` | UUID | Admin user who last changed this |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

**Default values:**

| Key | Default Value | Description |
|-----|---------------|-------------|
| `default_credits` | `7` | Credits given to new learners |
| `platform_fee_percent` | `10` | Platform's revenue share (%) |
| `min_rationale_words` | `50` | Minimum words in trade rationale |
| `max_report_flags_before_alert` | `10` | Flags before admin alert triggers |

---

## Key Relationships

```
profiles.id
  ├── trades.mentor_id                 (1 pro-trader → many trades)
  ├── unlocked_trades.user_id          (1 learner → many unlocks)
  ├── unlocked_trades.trade_id → trades.id  (1 trade → many unlocks)
  ├── subscriptions.public_trader_id   (1 learner → many subscriptions)
  ├── subscriptions.mentor_id          (1 pro-trader → many subscribers)
  ├── comments.user_id                 (1 user → many comments)
  ├── comments.trade_id → trades.id    (1 trade → many comments)
  ├── reports.reporter_id              (1 learner → many reports)
  ├── reports.trade_id → trades.id     (1 trade → many reports)
  ├── notifications.user_id            (1 user → many notifications)
  ├── mentor_stats.mentor_id           (1 pro-trader → 1 stats row)
  └── wallet.mentor_id                 (1 pro-trader → 1 wallet)
```

---

## Row Level Security Summary

RLS ensures users can only access their own data. See full policies in `supabase/rls-policies.sql`.

| Table | Policy Summary |
|-------|---------------|
| `profiles` | Users can read/update their own row. Pro-traders' public fields readable by all. |
| `trades` | Pro-traders manage own trades. Learners read all active trades (blurred until unlocked). |
| `unlocked_trades` | Learners read/insert own rows only. |
| `subscriptions` | Learners read own subscriptions. Pro-traders read subscriptions to them. |
| `comments` | Authenticated users read comments on accessible trades. Own comments editable. |
| `reports` | Learners insert own reports. Admins read all. |
| `notifications` | Users read/update/delete own notifications only. |
| `wallet` | Pro-traders read own wallet. Admins read all. |
| `transactions` | Pro-traders read own transactions. |
| `platform_settings` | Admins read/write. Others read-only. |

---

## Database Indexes

| Index | Table | Columns | Purpose |
|-------|-------|---------|---------|
| `idx_trades_mentor_id` | `trades` | `mentor_id` | Filter trades by pro-trader |
| `idx_trades_status` | `trades` | `trade_status` | Filter by active/closed |
| `idx_trades_created_at` | `trades` | `created_at DESC` | Sort feed by newest |
| `idx_unlocked_trades_user` | `unlocked_trades` | `user_id` | Check if learner has unlocked |
| `idx_subscription_plans_mentor` | `subscription_plans` | `mentor_id` | Get plans for a trader |
| `idx_subscriptions_public_trader` | `subscriptions` | `public_trader_id` | Learner's subscriptions |
| `idx_subscriptions_mentor` | `subscriptions` | `mentor_id` | Trader's subscribers |
| `idx_subscriptions_status` | `subscriptions` | `status` | Active vs expired |
| `idx_reports_status` | `reports` | `status` | Pending reports for admin |
| `idx_reports_trade` | `reports` | `trade_id` | Reports on a specific trade |
| `idx_comments_trade` | `comments` | `trade_id` | Comments on a trade |
| `idx_comments_created_at` | `comments` | `(trade_id, created_at)` | Ordered comments |
| `idx_notifications_user` | `notifications` | `user_id` | User's notifications |
| `idx_notifications_unread` | `notifications` | `(user_id, is_read)` | Unread count (partial) |
| `idx_transactions_mentor` | `transactions` | `mentor_id` | Trader's transactions |
| `idx_transactions_created_at` | `transactions` | `(mentor_id, created_at DESC)` | Recent transactions |

---

## Default Platform Settings

Applied at database initialization:

```sql
INSERT INTO public.platform_settings (key, value) VALUES
  ('default_credits', '7'),
  ('platform_fee_percent', '10'),
  ('min_rationale_words', '50'),
  ('max_report_flags_before_alert', '10');
```

These can be updated by an admin user through the backend or directly in Supabase.
