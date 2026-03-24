-- =============================================================================
-- TradeWise — Complete Database Initialization Script
-- Target:  Supabase / PostgreSQL 14+  (validated against PostgreSQL 16)
-- Usage:   Paste into the Supabase SQL editor or run with psql:
--            psql "$DATABASE_URL" -f supabase/init.sql
--
-- This single atomic script creates every table, type, index, constraint, and
-- RLS policy required by the TradeWise backend from scratch.
-- No demo data is included — DDL only.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 0. EXTENSIONS
-- ---------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- gen_random_uuid() / UUID helpers
CREATE EXTENSION IF NOT EXISTS "pg_trgm";    -- trigram indexes for text search

-- ---------------------------------------------------------------------------
-- 1. ENUM TYPES
--    Mirrors the VALID_* constants defined in each Python model class.
-- ---------------------------------------------------------------------------

-- User roles (profiles.role)
DO $$ BEGIN
  CREATE TYPE user_role AS ENUM ('public_trader', 'pro_trader', 'admin');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Auth providers (users.auth_provider)
DO $$ BEGIN
  CREATE TYPE auth_provider AS ENUM ('email', 'google', 'github');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Trade direction (trades.direction)
DO $$ BEGIN
  CREATE TYPE trade_direction AS ENUM ('buy', 'sell');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Trade status (trades.status)
DO $$ BEGIN
  CREATE TYPE trade_status AS ENUM ('active', 'target_hit', 'sl_hit', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Trade outcome (trades.outcome)
DO $$ BEGIN
  CREATE TYPE trade_outcome AS ENUM ('win', 'loss');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Trading style (pro_trader_profiles.trading_style)
DO $$ BEGIN
  CREATE TYPE trading_style AS ENUM ('scalping', 'intraday', 'swing', 'positional', 'long_term');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- KYC status (pro_trader_profiles.kyc_status)
DO $$ BEGIN
  CREATE TYPE kyc_status AS ENUM ('pending', 'verified', 'rejected');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Experience levels (learner_profiles.experience_level)
DO $$ BEGIN
  CREATE TYPE experience_level AS ENUM ('beginner', 'intermediate', 'advanced');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Subscription status (subscriptions.status)
DO $$ BEGIN
  CREATE TYPE subscription_status AS ENUM ('active', 'expired', 'cancelled');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Payment status (payments.status)
DO $$ BEGIN
  CREATE TYPE payment_status AS ENUM ('pending', 'success', 'failed', 'refunded');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Payout status (payouts.status)
DO $$ BEGIN
  CREATE TYPE payout_status AS ENUM ('initiated', 'processing', 'success', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Flag / report statuses
DO $$ BEGIN
  CREATE TYPE flag_status AS ENUM ('pending', 'investigating', 'resolved');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Admin actions on flags
DO $$ BEGIN
  CREATE TYPE admin_action AS ENUM ('none', 'warning', 'penalty', 'suspension');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Login activity status
DO $$ BEGIN
  CREATE TYPE login_status AS ENUM ('success', 'failed', 'locked');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Credit log actions
DO $$ BEGIN
  CREATE TYPE credit_action AS ENUM ('used', 'refunded', 'bonus');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Notification types — pro-trader side
DO $$ BEGIN
  CREATE TYPE notification_type AS ENUM (
    'new_subscriber', 'trade_flagged', 'payout_confirmation', 'payout_failed',
    'kyc_verified', 'kyc_rejected', 'new_trade', 'trade_closed', 'platform_update'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Notification types — learner side
DO $$ BEGIN
  CREATE TYPE learner_notification_type AS ENUM (
    'trade_closed', 'new_trade', 'subscriber_alert', 'flag_update', 'subscription_expiring'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =============================================================================
-- TABLE DEFINITIONS
-- Creation order respects foreign-key dependencies.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- TABLE 1: users
-- Core authentication table — stores credentials and auth metadata.
-- Every other table ultimately references this through a user_id FK.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.users (
  id               VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  email            VARCHAR(255) NOT NULL,
  password_hash    VARCHAR(255) NULL,                    -- NULL for OAuth-only accounts
  auth_provider    auth_provider NOT NULL DEFAULT 'email',
  is_active        BOOLEAN      NOT NULL DEFAULT TRUE,
  totp_secret      VARCHAR(64)  NULL,                    -- TOTP secret (base32, encrypted in app)
  totp_enabled     BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_users_email UNIQUE (email)
);

COMMENT ON TABLE  public.users IS 'Core user accounts — manages credentials, auth provider, and 2FA state';
COMMENT ON COLUMN public.users.password_hash  IS 'bcrypt hash; NULL for Google/GitHub OAuth users';
COMMENT ON COLUMN public.users.totp_secret    IS 'TOTP seed stored encrypted at application layer';

CREATE INDEX IF NOT EXISTS idx_users_email      ON public.users (email);
CREATE INDEX IF NOT EXISTS idx_users_is_active  ON public.users (is_active);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 2: profiles
-- Base public profile shared by all roles (public_trader, pro_trader, admin).
-- One-to-one with users.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.profiles (
  id           VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id      VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  role         user_role    NOT NULL DEFAULT 'public_trader',
  display_name VARCHAR(100) NULL,
  avatar_url   TEXT         NULL,
  is_verified  BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_profiles_user_id UNIQUE (user_id)
);

COMMENT ON TABLE  public.profiles IS 'Base user profile shared by all roles — role, display name, avatar, verification flag';
COMMENT ON COLUMN public.profiles.role        IS 'public_trader = learner, pro_trader = signal provider, admin = platform admin';
COMMENT ON COLUMN public.profiles.is_verified IS 'Set TRUE by admin after KYC approval for pro traders';

CREATE INDEX IF NOT EXISTS idx_profiles_user_id    ON public.profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_profiles_role       ON public.profiles (role);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 3: pro_trader_profiles
-- Extended profile for pro traders — bio, KYC, financials, trading stats.
-- One-to-one with users (only populated when role = 'pro_trader').
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.pro_trader_profiles (
  id                            VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                       VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  -- Bio & specialisation
  bio                           TEXT           NULL,
  specializations               JSONB          NOT NULL DEFAULT '[]',       -- array of market/sector strings
  external_portfolio_url        TEXT           NULL,
  years_of_experience           INTEGER        NOT NULL DEFAULT 0,
  trading_style                 trading_style  NULL,

  -- Bank details (sensitive columns; encrypt at application layer)
  bank_account_number_encrypted TEXT           NULL,
  ifsc_code                     VARCHAR(20)    NULL,
  account_holder_name           VARCHAR(100)   NULL,
  bank_account_last_4           VARCHAR(4)     NULL,

  -- KYC
  kyc_status                    kyc_status     NOT NULL DEFAULT 'pending',
  kyc_documents                 JSONB          NOT NULL DEFAULT '{}',       -- {doc_type: storage_url}

  -- Performance stats (denormalised for fast feed rendering)
  accuracy_score                NUMERIC(5, 2)  NOT NULL DEFAULT 0.00,       -- 0.00–100.00
  total_trades                  INTEGER        NOT NULL DEFAULT 0,
  winning_trades                INTEGER        NOT NULL DEFAULT 0,
  leaderboard_rank              INTEGER        NULL,
  total_subscribers             INTEGER        NOT NULL DEFAULT 0,

  -- Financials (stored in INR with two decimal places)
  monthly_subscription_price    NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
  total_earnings                NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
  available_balance             NUMERIC(12, 2) NOT NULL DEFAULT 0.00,

  -- Media
  profile_picture_url           TEXT           NULL,
  is_active                     BOOLEAN        NOT NULL DEFAULT TRUE,

  created_at                    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  updated_at                    TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_pro_trader_profiles_user_id UNIQUE (user_id)
);

COMMENT ON TABLE  public.pro_trader_profiles IS 'Extended profile for pro traders — KYC, trading stats, bank details, earnings';
COMMENT ON COLUMN public.pro_trader_profiles.bank_account_number_encrypted IS 'AES-encrypted bank account number; decrypt at app layer only';
COMMENT ON COLUMN public.pro_trader_profiles.accuracy_score                IS 'Denormalised (winning_trades/total_trades)*100; refreshed on trade close';
COMMENT ON COLUMN public.pro_trader_profiles.monthly_subscription_price    IS 'Base 1-month price in INR; used when no subscription_plan row exists';
COMMENT ON COLUMN public.pro_trader_profiles.available_balance             IS '90% revenue share from subscriptions, minus payouts';

CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_user_id        ON public.pro_trader_profiles (user_id);
CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_kyc_status     ON public.pro_trader_profiles (kyc_status);
CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_is_active      ON public.pro_trader_profiles (is_active);
CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_leaderboard    ON public.pro_trader_profiles (leaderboard_rank) WHERE leaderboard_rank IS NOT NULL;

ALTER TABLE public.pro_trader_profiles ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 4: learner_profiles
-- Extended profile for learners (public traders) — interests, credits, goals.
-- One-to-one with users (only populated when role = 'public_trader').
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_profiles (
  id                   VARCHAR(36)      PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id              VARCHAR(36)      NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  interests            JSONB            NOT NULL DEFAULT '[]',   -- e.g. ["nifty50","crypto"]
  experience_level     experience_level NOT NULL DEFAULT 'beginner',
  credits              INTEGER          NOT NULL DEFAULT 7,       -- free unlock credits remaining
  total_unlocked_trades INTEGER         NOT NULL DEFAULT 0,
  total_spent          NUMERIC(12, 2)   NOT NULL DEFAULT 0.00,   -- cumulative subscription spend
  favorite_traders     JSONB            NOT NULL DEFAULT '[]',   -- array of user_id strings
  learning_goal        TEXT             NULL,

  created_at           TIMESTAMPTZ      NOT NULL DEFAULT NOW(),
  updated_at           TIMESTAMPTZ      NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_learner_profiles_user_id UNIQUE (user_id),
  CONSTRAINT chk_learner_credits_non_negative CHECK (credits >= 0)
);

COMMENT ON TABLE  public.learner_profiles IS 'Extended profile for learners — credits, interests, spend tracking';
COMMENT ON COLUMN public.learner_profiles.credits                IS 'Decrements by 1 on each trade unlock; starts at 7 for new learners';
COMMENT ON COLUMN public.learner_profiles.total_unlocked_trades  IS 'Denormalised count of all unlocked trades (via credits or subscription)';

CREATE INDEX IF NOT EXISTS idx_learner_profiles_user_id ON public.learner_profiles (user_id);

ALTER TABLE public.learner_profiles ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 5: trades
-- Trade signals posted by pro traders.
-- Core content object — all learner activity references this table.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.trades (
  id                  VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trader_id           VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  -- Signal parameters
  symbol              VARCHAR(30)    NOT NULL,                    -- e.g. RELIANCE, NIFTY50
  direction           trade_direction NOT NULL,
  entry_price         NUMERIC(16, 4) NOT NULL,
  stop_loss_price     NUMERIC(16, 4) NOT NULL,
  target_price        NUMERIC(16, 4) NOT NULL,
  rrr                 NUMERIC(8,  4) NOT NULL,                    -- risk-reward ratio
  technical_rationale TEXT           NOT NULL,                    -- min 50 words (enforced by app)
  chart_image_url     TEXT           NULL,

  -- Lifecycle
  status              trade_status   NOT NULL DEFAULT 'active',
  outcome             trade_outcome  NULL,                        -- NULL while active
  close_reason        TEXT           NULL,

  -- Engagement counters (denormalised for performance)
  view_count          INTEGER        NOT NULL DEFAULT 0,
  unlock_count        INTEGER        NOT NULL DEFAULT 0,
  flag_count          INTEGER        NOT NULL DEFAULT 0,

  created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  closed_at           TIMESTAMPTZ    NULL,
  closed_by_trader_at TIMESTAMPTZ    NULL,

  CONSTRAINT chk_trades_rrr_positive CHECK (rrr > 0),
  CONSTRAINT chk_trades_entry_positive CHECK (entry_price > 0),
  CONSTRAINT chk_trades_sl_positive CHECK (stop_loss_price > 0),
  CONSTRAINT chk_trades_target_positive CHECK (target_price > 0)
);

COMMENT ON TABLE  public.trades IS 'Trade signals (BUY/SELL) posted by pro traders; learners unlock for credits or via subscription';
COMMENT ON COLUMN public.trades.rrr              IS '(target-entry)/(entry-SL) for BUY; calculated and stored at insert time';
COMMENT ON COLUMN public.trades.outcome          IS 'win = target hit, loss = SL hit; NULL while status=active';
COMMENT ON COLUMN public.trades.closed_by_trader_at IS 'Timestamp set when pro trader manually closes the position';

CREATE INDEX IF NOT EXISTS idx_trades_trader_id   ON public.trades (trader_id);
CREATE INDEX IF NOT EXISTS idx_trades_status      ON public.trades (status);
CREATE INDEX IF NOT EXISTS idx_trades_created_at  ON public.trades (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_trades_symbol      ON public.trades (symbol);

ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 6: payments
-- Records every payment attempt (Cashfree order lifecycle).
-- Must be created before subscriptions because subscriptions FK to payments.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.payments (
  id                  VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  subscriber_id       VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trader_id           VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  amount              NUMERIC(12, 2) NOT NULL,
  currency            VARCHAR(5)     NOT NULL DEFAULT 'INR',
  cashfree_order_id   VARCHAR(100)   NULL,
  cashfree_payment_id VARCHAR(100)   NULL,
  status              payment_status NOT NULL DEFAULT 'pending',
  payment_method      VARCHAR(30)    NULL,                        -- upi / card / netbanking

  created_at          TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
  completed_at        TIMESTAMPTZ    NULL,

  CONSTRAINT uq_payments_cashfree_order_id UNIQUE (cashfree_order_id),
  CONSTRAINT chk_payments_amount_positive CHECK (amount > 0)
);

COMMENT ON TABLE  public.payments IS 'Payment records for subscription purchases; one row per Cashfree order';
COMMENT ON COLUMN public.payments.cashfree_order_id   IS 'Unique Cashfree order ID used for webhook correlation';
COMMENT ON COLUMN public.payments.cashfree_payment_id IS 'Set by Cashfree webhook on successful payment';

CREATE INDEX IF NOT EXISTS idx_payments_subscriber_id ON public.payments (subscriber_id);
CREATE INDEX IF NOT EXISTS idx_payments_trader_id     ON public.payments (trader_id);
CREATE INDEX IF NOT EXISTS idx_payments_status        ON public.payments (status);
CREATE INDEX IF NOT EXISTS idx_payments_created_at    ON public.payments (created_at DESC);

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 7: subscriptions
-- Active or expired subscription relationships (learner ↔ pro trader).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.subscriptions (
  id            VARCHAR(36)          PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  subscriber_id VARCHAR(36)          NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trader_id     VARCHAR(36)          NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  payment_id    VARCHAR(36)          NULL REFERENCES public.payments (id) ON DELETE SET NULL,

  started_at    TIMESTAMPTZ          NOT NULL DEFAULT NOW(),
  ends_at       TIMESTAMPTZ          NOT NULL,
  status        subscription_status  NOT NULL DEFAULT 'active',
  auto_renew    BOOLEAN              NOT NULL DEFAULT FALSE,

  created_at    TIMESTAMPTZ          NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_subscriptions_ends_after_start CHECK (ends_at > started_at)
);

COMMENT ON TABLE  public.subscriptions IS 'Paid subscriptions; grants full access to all of a pro trader''s trades for the subscription period';
COMMENT ON COLUMN public.subscriptions.ends_at    IS 'Calculated from plan duration at payment time (1/3/6 months)';
COMMENT ON COLUMN public.subscriptions.auto_renew IS 'Reserved for future recurring billing integration';

CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber_id ON public.subscriptions (subscriber_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_trader_id     ON public.subscriptions (trader_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status        ON public.subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_ends_at       ON public.subscriptions (ends_at);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 8: revenue_splits
-- Per-payment 90/10 revenue split record (pro trader vs. platform).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.revenue_splits (
  id                       VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  payment_id               VARCHAR(36)    NOT NULL REFERENCES public.payments (id) ON DELETE CASCADE,
  trader_id                VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  pro_trader_amount        NUMERIC(12, 2) NOT NULL,               -- 90% of payment amount
  admin_amount             NUMERIC(12, 2) NOT NULL,               -- 10% of payment amount
  split_percentage_pro     INTEGER        NOT NULL DEFAULT 90,
  split_percentage_admin   INTEGER        NOT NULL DEFAULT 10,

  pro_trader_wallet_credited BOOLEAN      NOT NULL DEFAULT FALSE,
  admin_wallet_credited      BOOLEAN      NOT NULL DEFAULT FALSE,

  created_at               TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_revenue_splits_payment_id UNIQUE (payment_id),
  CONSTRAINT chk_split_percentages CHECK (split_percentage_pro + split_percentage_admin = 100)
);

COMMENT ON TABLE  public.revenue_splits IS '90/10 revenue split record per payment; tracks wallet credit status for both parties';
COMMENT ON COLUMN public.revenue_splits.pro_trader_amount IS 'Amount credited to pro trader wallet after split (INR, 2 dp)';
COMMENT ON COLUMN public.revenue_splits.admin_amount      IS 'Platform fee retained (INR, 2 dp)';

CREATE INDEX IF NOT EXISTS idx_revenue_splits_payment_id  ON public.revenue_splits (payment_id);
CREATE INDEX IF NOT EXISTS idx_revenue_splits_trader_id   ON public.revenue_splits (trader_id);

ALTER TABLE public.revenue_splits ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 9: payouts
-- Pro-trader withdrawal requests and Cashfree payout transfer records.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.payouts (
  id                    VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trader_id             VARCHAR(36)   NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  amount                NUMERIC(12, 2) NOT NULL,
  cashfree_payout_id    VARCHAR(100)  NULL,
  cashfree_transfer_id  VARCHAR(100)  NULL,
  status                payout_status NOT NULL DEFAULT 'initiated',
  bank_account_last_4   VARCHAR(4)    NULL,
  failure_reason        TEXT          NULL,

  initiated_at          TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  completed_at          TIMESTAMPTZ   NULL,

  CONSTRAINT chk_payouts_amount_positive CHECK (amount > 0)
);

COMMENT ON TABLE  public.payouts IS 'Pro-trader payout requests; tracks Cashfree transfer lifecycle from initiation to completion';
COMMENT ON COLUMN public.payouts.bank_account_last_4  IS 'Last 4 digits shown in UI; full account stored encrypted in pro_trader_profiles';

CREATE INDEX IF NOT EXISTS idx_payouts_trader_id      ON public.payouts (trader_id);
CREATE INDEX IF NOT EXISTS idx_payouts_status         ON public.payouts (status);
CREATE INDEX IF NOT EXISTS idx_payouts_initiated_at   ON public.payouts (initiated_at DESC);

ALTER TABLE public.payouts ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 10: learner_unlocked_trades
-- Records each trade a learner has unlocked (via credit or subscription bypass).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_unlocked_trades (
  id          VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id  VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trade_id    VARCHAR(36)  NOT NULL REFERENCES public.trades (id) ON DELETE CASCADE,

  via_credit  BOOLEAN      NOT NULL DEFAULT TRUE,   -- FALSE when unlocked via active subscription
  unlocked_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  viewed_at   TIMESTAMPTZ  NULL,                    -- first time learner viewed after unlock
  rating      SMALLINT     NULL,                    -- quick 1–5 star (detailed in learner_trade_ratings)
  notes       TEXT         NULL,                    -- private learner notes on this trade

  CONSTRAINT uq_learner_unlocked_trades UNIQUE (learner_id, trade_id),
  CONSTRAINT chk_unlocked_rating_range CHECK (rating IS NULL OR (rating BETWEEN 1 AND 5))
);

COMMENT ON TABLE  public.learner_unlocked_trades IS 'Tracks which trades each learner has unlocked; prevents double credit deduction';
COMMENT ON COLUMN public.learner_unlocked_trades.via_credit IS 'TRUE = 1 credit deducted; FALSE = unlocked via active subscription (no credit cost)';

CREATE INDEX IF NOT EXISTS idx_learner_unlocked_trades_learner_id ON public.learner_unlocked_trades (learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_unlocked_trades_trade_id   ON public.learner_unlocked_trades (trade_id);

ALTER TABLE public.learner_unlocked_trades ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 11: learner_credits_log
-- Immutable audit log of every credit change for a learner.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_credits_log (
  id               VARCHAR(36)    PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id       VARCHAR(36)    NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trade_id         VARCHAR(36)    NULL REFERENCES public.trades (id) ON DELETE SET NULL,

  action           credit_action  NOT NULL,
  amount           INTEGER        NOT NULL,         -- positive = credit gained, negative = credit used
  credits_remaining INTEGER       NOT NULL,          -- snapshot after this transaction
  reason           TEXT           NULL,

  created_at       TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.learner_credits_log IS 'Immutable ledger of credit changes (used/refunded/bonus) per learner; used for audit and dispute resolution';
COMMENT ON COLUMN public.learner_credits_log.amount           IS 'Signed integer: -1 for unlock, +N for bonus/refund';
COMMENT ON COLUMN public.learner_credits_log.credits_remaining IS 'Snapshot of learner_profiles.credits after applying this entry';

CREATE INDEX IF NOT EXISTS idx_learner_credits_log_learner_id ON public.learner_credits_log (learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_credits_log_created_at ON public.learner_credits_log (learner_id, created_at DESC);

ALTER TABLE public.learner_credits_log ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 12: learner_trade_ratings
-- Detailed 1–5 star rating + optional text review per unlocked trade.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_trade_ratings (
  id            VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id    VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trade_id      VARCHAR(36)  NOT NULL REFERENCES public.trades (id) ON DELETE CASCADE,

  rating        SMALLINT     NOT NULL,
  review        TEXT         NULL,
  helpful_count INTEGER      NOT NULL DEFAULT 0,   -- upvotes from other learners

  created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_learner_trade_rating    UNIQUE (learner_id, trade_id),
  CONSTRAINT chk_trade_rating_range     CHECK (rating BETWEEN 1 AND 5),
  CONSTRAINT chk_helpful_count_non_neg  CHECK (helpful_count >= 0)
);

COMMENT ON TABLE  public.learner_trade_ratings IS 'Detailed trade quality ratings submitted by learners after a trade is closed';
COMMENT ON COLUMN public.learner_trade_ratings.helpful_count IS 'Peer-voted helpfulness counter for the review text';

CREATE INDEX IF NOT EXISTS idx_learner_trade_ratings_learner_id ON public.learner_trade_ratings (learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_trade_ratings_trade_id   ON public.learner_trade_ratings (trade_id);

ALTER TABLE public.learner_trade_ratings ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 13: learner_flags
-- Learner-submitted flags on suspicious or low-quality trade signals.
-- Separate from the generic reports table; carries workflow status + admin action.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_flags (
  id           VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id   VARCHAR(36)   NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,
  trade_id     VARCHAR(36)   NOT NULL REFERENCES public.trades (id) ON DELETE CASCADE,

  reason       TEXT          NOT NULL,
  status       flag_status   NOT NULL DEFAULT 'pending',
  admin_action admin_action  NULL,

  created_at   TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  resolved_at  TIMESTAMPTZ   NULL
);

COMMENT ON TABLE  public.learner_flags IS 'Learner-submitted flags/complaints on specific trades; admin reviews and takes action';
COMMENT ON COLUMN public.learner_flags.admin_action IS 'warning = caution notice; penalty = credit deducted; suspension = account suspended';

CREATE INDEX IF NOT EXISTS idx_learner_flags_learner_id ON public.learner_flags (learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_flags_trade_id   ON public.learner_flags (trade_id);
CREATE INDEX IF NOT EXISTS idx_learner_flags_status     ON public.learner_flags (status);

ALTER TABLE public.learner_flags ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 14: reports
-- General trade report system (broader than learner_flags — any user can report).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.reports (
  id             VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trade_id       VARCHAR(36)  NOT NULL REFERENCES public.trades (id) ON DELETE CASCADE,
  reporter_id    VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  reason         TEXT         NOT NULL,
  status         flag_status  NOT NULL DEFAULT 'pending',
  admin_verdict  TEXT         NULL,

  created_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  resolved_at    TIMESTAMPTZ  NULL
);

COMMENT ON TABLE  public.reports IS 'General trade report queue; used by admins to investigate and resolve misconduct';
COMMENT ON COLUMN public.reports.admin_verdict IS 'Admin free-text explanation of the resolution decision';

CREATE INDEX IF NOT EXISTS idx_reports_trade_id    ON public.reports (trade_id);
CREATE INDEX IF NOT EXISTS idx_reports_reporter_id ON public.reports (reporter_id);
CREATE INDEX IF NOT EXISTS idx_reports_status      ON public.reports (status);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 15: comments_threads
-- Discussion comments on individual trade signals.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.comments_threads (
  id         VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trade_id   VARCHAR(36)  NOT NULL REFERENCES public.trades (id) ON DELETE CASCADE,
  user_id    VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  content    TEXT         NOT NULL,

  created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.comments_threads IS 'Comment threads on trade signals; visible to all users who have access to the trade';

CREATE INDEX IF NOT EXISTS idx_comments_threads_trade_id   ON public.comments_threads (trade_id);
CREATE INDEX IF NOT EXISTS idx_comments_threads_user_id    ON public.comments_threads (user_id);
CREATE INDEX IF NOT EXISTS idx_comments_threads_created_at ON public.comments_threads (trade_id, created_at DESC);

ALTER TABLE public.comments_threads ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 16: notifications
-- In-app notification queue for pro traders (and admins).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notifications (
  id         VARCHAR(36)         PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id    VARCHAR(36)         NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  type       notification_type   NOT NULL,
  title      VARCHAR(255)        NOT NULL,
  message    TEXT                NOT NULL,
  data       JSONB               NOT NULL DEFAULT '{}',   -- extra payload (trade_id, amount, etc.)
  is_read    BOOLEAN             NOT NULL DEFAULT FALSE,

  created_at TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.notifications IS 'In-app notifications for pro traders (new subscriber, payout, KYC status changes, etc.)';
COMMENT ON COLUMN public.notifications.data IS 'Arbitrary JSON payload; keys depend on notification type e.g. {"trade_id": "..."}';

CREATE INDEX IF NOT EXISTS idx_notifications_user_id    ON public.notifications (user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_is_read    ON public.notifications (user_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_notifications_created_at ON public.notifications (user_id, created_at DESC);

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 17: learner_notifications
-- In-app notification queue specifically for learners.
-- Separate table to allow learner-specific types and richer trade/trader links.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_notifications (
  id                VARCHAR(36)              PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id        VARCHAR(36)              NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  type              learner_notification_type NOT NULL,
  title             VARCHAR(255)             NOT NULL,
  message           TEXT                     NOT NULL,
  related_trade_id  VARCHAR(36)              NULL REFERENCES public.trades (id) ON DELETE SET NULL,
  related_trader_id VARCHAR(36)              NULL REFERENCES public.users (id) ON DELETE SET NULL,
  is_read           BOOLEAN                  NOT NULL DEFAULT FALSE,

  created_at        TIMESTAMPTZ              NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.learner_notifications IS 'In-app notifications for learners (new trade from subscribed trader, trade closed, etc.)';
COMMENT ON COLUMN public.learner_notifications.related_trade_id  IS 'Trade that triggered this notification (nullable on trade delete)';
COMMENT ON COLUMN public.learner_notifications.related_trader_id IS 'Pro trader who triggered this notification (nullable on account delete)';

CREATE INDEX IF NOT EXISTS idx_learner_notifications_learner_id    ON public.learner_notifications (learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_notifications_is_read       ON public.learner_notifications (learner_id, is_read) WHERE is_read = FALSE;
CREATE INDEX IF NOT EXISTS idx_learner_notifications_created_at    ON public.learner_notifications (learner_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learner_notifications_related_trade ON public.learner_notifications (related_trade_id) WHERE related_trade_id IS NOT NULL;

ALTER TABLE public.learner_notifications ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 18: notification_preferences
-- Per-user notification channel preferences for pro traders.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.notification_preferences (
  id                       VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                  VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  -- Email preferences
  email_new_subscriber      BOOLEAN      NOT NULL DEFAULT TRUE,
  email_trade_flagged       BOOLEAN      NOT NULL DEFAULT TRUE,
  email_payout_confirmation BOOLEAN      NOT NULL DEFAULT TRUE,

  -- In-app preferences
  in_app_new_subscriber     BOOLEAN      NOT NULL DEFAULT TRUE,
  in_app_trade_flagged      BOOLEAN      NOT NULL DEFAULT TRUE,
  in_app_payout_confirmation BOOLEAN     NOT NULL DEFAULT TRUE,

  -- SMS (opt-in; phone required)
  sms_enabled              BOOLEAN      NOT NULL DEFAULT FALSE,
  sms_phone                VARCHAR(20)  NULL,

  updated_at               TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_notification_preferences_user_id UNIQUE (user_id)
);

COMMENT ON TABLE  public.notification_preferences IS 'Pro-trader notification channel preferences; one row per user';
COMMENT ON COLUMN public.notification_preferences.sms_phone IS 'E.164 formatted phone number; required when sms_enabled = TRUE';

CREATE INDEX IF NOT EXISTS idx_notification_preferences_user_id ON public.notification_preferences (user_id);

ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 19: learner_notification_preferences
-- Per-user notification channel preferences for learners.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.learner_notification_preferences (
  id                           VARCHAR(36)  PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                      VARCHAR(36)  NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  -- Email preferences
  email_new_trade              BOOLEAN      NOT NULL DEFAULT TRUE,
  email_trade_closed           BOOLEAN      NOT NULL DEFAULT TRUE,
  email_subscription_expiring  BOOLEAN      NOT NULL DEFAULT TRUE,
  email_flag_update            BOOLEAN      NOT NULL DEFAULT TRUE,
  email_announcements          BOOLEAN      NOT NULL DEFAULT FALSE,

  -- In-app preferences
  in_app_new_trade             BOOLEAN      NOT NULL DEFAULT TRUE,
  in_app_trade_closed          BOOLEAN      NOT NULL DEFAULT TRUE,
  in_app_subscription_expiring BOOLEAN      NOT NULL DEFAULT TRUE,
  in_app_flag_update           BOOLEAN      NOT NULL DEFAULT TRUE,

  -- SMS (opt-in)
  sms_enabled                  BOOLEAN      NOT NULL DEFAULT FALSE,
  sms_phone                    VARCHAR(20)  NULL,

  updated_at                   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_learner_notification_preferences_user_id UNIQUE (user_id)
);

COMMENT ON TABLE  public.learner_notification_preferences IS 'Learner notification channel preferences; one row per learner user';

CREATE INDEX IF NOT EXISTS idx_learner_notif_prefs_user_id ON public.learner_notification_preferences (user_id);

ALTER TABLE public.learner_notification_preferences ENABLE ROW LEVEL SECURITY;


-- ---------------------------------------------------------------------------
-- TABLE 20: login_activities
-- Immutable audit log of every login attempt for every user.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.login_activities (
  id         VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id    VARCHAR(36)   NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  ip_address VARCHAR(45)   NULL,     -- supports IPv4 and IPv6
  user_agent TEXT          NULL,
  device     VARCHAR(100)  NULL,     -- parsed device string (e.g. "Chrome / macOS")
  location   VARCHAR(100)  NULL,     -- coarse geo-location (city, country)
  status     login_status  NOT NULL DEFAULT 'success',

  created_at TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.login_activities IS 'Immutable login audit log — used for security monitoring and suspicious activity alerts';
COMMENT ON COLUMN public.login_activities.ip_address IS 'IPv4 (max 15 chars) or IPv6 (max 45 chars) client address';

CREATE INDEX IF NOT EXISTS idx_login_activities_user_id    ON public.login_activities (user_id);
CREATE INDEX IF NOT EXISTS idx_login_activities_created_at ON public.login_activities (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_login_activities_status     ON public.login_activities (status) WHERE status = 'failed';

ALTER TABLE public.login_activities ENABLE ROW LEVEL SECURITY;


-- =============================================================================
-- ROW LEVEL SECURITY POLICIES
-- All tables have RLS enabled above. Policies below control read/write access
-- based on the current authenticated user (auth.uid() in Supabase; adapt the
-- session variable if using a custom auth layer: current_setting('app.user_id')).
-- =============================================================================

-- ---------------------------------------------------------------------------
-- HELPER: a convenience function to get the current user id as VARCHAR
-- Adapt the body if you replace Supabase Auth with a custom JWT approach.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS VARCHAR(36)
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', TRUE), '')::VARCHAR(36);
$$;

COMMENT ON FUNCTION public.current_user_id() IS
  'Returns the authenticated user id from the app.user_id session variable. '
  'Set this at connection time via: SELECT set_config(''app.user_id'', <uid>, TRUE)';


-- ===== users =====
-- Users may only read and update their own row.
CREATE POLICY "users_select_own"
  ON public.users FOR SELECT
  USING (id = public.current_user_id());

CREATE POLICY "users_update_own"
  ON public.users FOR UPDATE
  USING (id = public.current_user_id());


-- ===== profiles =====
-- All authenticated users can read all profiles (needed for discovery feeds).
-- Users can only insert/update their own profile.
CREATE POLICY "profiles_select_all"
  ON public.profiles FOR SELECT
  USING (TRUE);

CREATE POLICY "profiles_insert_own"
  ON public.profiles FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "profiles_update_own"
  ON public.profiles FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== pro_trader_profiles =====
-- Public readable (for learner discovery). Writable only by the owner.
CREATE POLICY "pro_trader_profiles_select_all"
  ON public.pro_trader_profiles FOR SELECT
  USING (TRUE);

CREATE POLICY "pro_trader_profiles_insert_own"
  ON public.pro_trader_profiles FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "pro_trader_profiles_update_own"
  ON public.pro_trader_profiles FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== learner_profiles =====
-- Only the learner themselves can read/write their own profile.
CREATE POLICY "learner_profiles_select_own"
  ON public.learner_profiles FOR SELECT
  USING (user_id = public.current_user_id());

CREATE POLICY "learner_profiles_insert_own"
  ON public.learner_profiles FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "learner_profiles_update_own"
  ON public.learner_profiles FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== trades =====
-- All authenticated users can read trades (learner feed shows blurred preview).
-- Only the owning pro trader can insert or update their own trades.
CREATE POLICY "trades_select_all"
  ON public.trades FOR SELECT
  USING (TRUE);

CREATE POLICY "trades_insert_own"
  ON public.trades FOR INSERT
  WITH CHECK (
    trader_id = public.current_user_id()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.user_id = public.current_user_id()
      AND p.role = 'pro_trader'
    )
  );

CREATE POLICY "trades_update_own"
  ON public.trades FOR UPDATE
  USING (trader_id = public.current_user_id());

CREATE POLICY "trades_delete_own"
  ON public.trades FOR DELETE
  USING (trader_id = public.current_user_id());


-- ===== payments =====
-- Subscriber sees their own payments; trader sees payments made to them.
CREATE POLICY "payments_select_own"
  ON public.payments FOR SELECT
  USING (
    subscriber_id = public.current_user_id()
    OR trader_id  = public.current_user_id()
  );

CREATE POLICY "payments_insert_subscriber"
  ON public.payments FOR INSERT
  WITH CHECK (subscriber_id = public.current_user_id());


-- ===== subscriptions =====
-- Both the subscriber and the trader can read the subscription row.
-- Only the subscriber (learner) can create a subscription.
CREATE POLICY "subscriptions_select_own"
  ON public.subscriptions FOR SELECT
  USING (
    subscriber_id = public.current_user_id()
    OR trader_id  = public.current_user_id()
  );

CREATE POLICY "subscriptions_insert_subscriber"
  ON public.subscriptions FOR INSERT
  WITH CHECK (subscriber_id = public.current_user_id());


-- ===== revenue_splits =====
-- Only the involved pro trader can read their revenue split rows.
-- Admins should use service-role key to bypass RLS for reporting.
CREATE POLICY "revenue_splits_select_trader"
  ON public.revenue_splits FOR SELECT
  USING (trader_id = public.current_user_id());


-- ===== payouts =====
-- Only the trader can read and request their own payouts.
CREATE POLICY "payouts_select_own"
  ON public.payouts FOR SELECT
  USING (trader_id = public.current_user_id());

CREATE POLICY "payouts_insert_own"
  ON public.payouts FOR INSERT
  WITH CHECK (trader_id = public.current_user_id());


-- ===== learner_unlocked_trades =====
-- Learners can only see and create their own unlock records.
CREATE POLICY "learner_unlocked_trades_select_own"
  ON public.learner_unlocked_trades FOR SELECT
  USING (learner_id = public.current_user_id());

CREATE POLICY "learner_unlocked_trades_insert_own"
  ON public.learner_unlocked_trades FOR INSERT
  WITH CHECK (learner_id = public.current_user_id());


-- ===== learner_credits_log =====
-- Read-only for the learner; only the backend service should write to this table.
CREATE POLICY "learner_credits_log_select_own"
  ON public.learner_credits_log FOR SELECT
  USING (learner_id = public.current_user_id());


-- ===== learner_trade_ratings =====
-- Learners can read all ratings (public social proof), but only write their own.
CREATE POLICY "learner_trade_ratings_select_all"
  ON public.learner_trade_ratings FOR SELECT
  USING (TRUE);

CREATE POLICY "learner_trade_ratings_insert_own"
  ON public.learner_trade_ratings FOR INSERT
  WITH CHECK (learner_id = public.current_user_id());

CREATE POLICY "learner_trade_ratings_update_own"
  ON public.learner_trade_ratings FOR UPDATE
  USING (learner_id = public.current_user_id());


-- ===== learner_flags =====
-- Learner can read and submit their own flags; admins use service-role.
CREATE POLICY "learner_flags_select_own"
  ON public.learner_flags FOR SELECT
  USING (learner_id = public.current_user_id());

CREATE POLICY "learner_flags_insert_own"
  ON public.learner_flags FOR INSERT
  WITH CHECK (learner_id = public.current_user_id());


-- ===== reports =====
-- Reporters read their own reports. Admins bypass via service-role key.
CREATE POLICY "reports_select_own"
  ON public.reports FOR SELECT
  USING (reporter_id = public.current_user_id());

CREATE POLICY "reports_insert_auth"
  ON public.reports FOR INSERT
  WITH CHECK (reporter_id = public.current_user_id());


-- ===== comments_threads =====
-- Any authenticated user can read comments on accessible trades.
-- Only the comment author can delete their own comment.
CREATE POLICY "comments_select_all"
  ON public.comments_threads FOR SELECT
  USING (TRUE);

CREATE POLICY "comments_insert_auth"
  ON public.comments_threads FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "comments_delete_own"
  ON public.comments_threads FOR DELETE
  USING (user_id = public.current_user_id());

CREATE POLICY "comments_update_own"
  ON public.comments_threads FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== notifications =====
-- Users can only see, mark-read, and delete their own notifications.
-- Backend service (service-role) inserts notifications on behalf of any user.
CREATE POLICY "notifications_select_own"
  ON public.notifications FOR SELECT
  USING (user_id = public.current_user_id());

CREATE POLICY "notifications_update_own"
  ON public.notifications FOR UPDATE
  USING (user_id = public.current_user_id());

CREATE POLICY "notifications_delete_own"
  ON public.notifications FOR DELETE
  USING (user_id = public.current_user_id());

CREATE POLICY "notifications_insert_service"
  ON public.notifications FOR INSERT
  WITH CHECK (TRUE);   -- backend service-role bypasses; adjust if using Supabase Auth


-- ===== learner_notifications =====
CREATE POLICY "learner_notifications_select_own"
  ON public.learner_notifications FOR SELECT
  USING (learner_id = public.current_user_id());

CREATE POLICY "learner_notifications_update_own"
  ON public.learner_notifications FOR UPDATE
  USING (learner_id = public.current_user_id());

CREATE POLICY "learner_notifications_delete_own"
  ON public.learner_notifications FOR DELETE
  USING (learner_id = public.current_user_id());

CREATE POLICY "learner_notifications_insert_service"
  ON public.learner_notifications FOR INSERT
  WITH CHECK (TRUE);


-- ===== notification_preferences =====
CREATE POLICY "notification_preferences_select_own"
  ON public.notification_preferences FOR SELECT
  USING (user_id = public.current_user_id());

CREATE POLICY "notification_preferences_insert_own"
  ON public.notification_preferences FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "notification_preferences_update_own"
  ON public.notification_preferences FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== learner_notification_preferences =====
CREATE POLICY "learner_notification_preferences_select_own"
  ON public.learner_notification_preferences FOR SELECT
  USING (user_id = public.current_user_id());

CREATE POLICY "learner_notification_preferences_insert_own"
  ON public.learner_notification_preferences FOR INSERT
  WITH CHECK (user_id = public.current_user_id());

CREATE POLICY "learner_notification_preferences_update_own"
  ON public.learner_notification_preferences FOR UPDATE
  USING (user_id = public.current_user_id());


-- ===== login_activities =====
-- Users can only read their own login history; writes are service-role only.
CREATE POLICY "login_activities_select_own"
  ON public.login_activities FOR SELECT
  USING (user_id = public.current_user_id());


-- =============================================================================
-- DEFAULT DATA
-- Seed platform-wide settings used by the backend.
-- (Key-value store — no separate platform_settings table in the backend models;
--  these values are read from environment variables at runtime.
--  Provided here as reference INSERT statements in case a settings table
--  is added in future, commented out to keep the script DDL-only.)
-- =============================================================================

-- NOTE: The backend reads platform settings from environment variables.
-- If you add a platform_settings table in a future migration, seed it like:
--
-- INSERT INTO public.platform_settings (key, value) VALUES
--   ('default_credits',              '7'),
--   ('platform_fee_percent',         '10'),
--   ('pro_trader_revenue_percent',   '90'),
--   ('min_rationale_words',          '50'),
--   ('max_report_flags_before_alert','10')
-- ON CONFLICT (key) DO NOTHING;

COMMIT;
