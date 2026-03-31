-- TradeWise — Complete Database Initialization Script
-- Version: 1.0.0
-- Date:    2026-03-31
-- Description: Canonical production schema for the TradeWise trading-signal
--              marketplace.  Replaces the early-stage 001_initial_schema.sql.
--
-- Architecture:
--   Backend  : Python 3.11 / Flask REST API (port 5000)
--   Frontend : Vanilla JS (no build tools)
--   Database : Supabase PostgreSQL
--   Payments : Cashfree  — 90 % pro-trader / 10 % platform revenue split
--
-- Auth model:
--   • public.users  — server-side mirror of auth identity (populated by trusted
--                     backend code, NOT directly writable by clients).
--   • app.user_id   — PostgreSQL session variable set by trusted server-side
--                     middleware.  Clients MUST NOT be permitted to set this
--                     variable; doing so would bypass all Row-Level Security.
--   • current_user_id() — reads app.user_id; used everywhere in RLS policies.
--
-- Admin policies are kept in a separate migration:
--   supabase/migrations/20260331_002_admin_auth_hardening.sql

BEGIN;

-- ================================================================
-- EXTENSIONS
-- ================================================================

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ================================================================
-- ENUMS
-- ================================================================

-- user_role enum — includes 'admin'; guard against duplicate creation.
DO $$ BEGIN
  CREATE TYPE public.user_role AS ENUM ('public_trader', 'pro_trader', 'admin');
EXCEPTION WHEN duplicate_object THEN
  NULL;  -- already exists; no-op
END $$;

-- ================================================================
-- AUTH SUPPORT
-- ================================================================

-- public.users: server-side auth identity mirror.
-- Populated by trusted backend auth flows (Flask / Supabase Auth webhook).
-- The 'id' column maps to Supabase auth.users.id (UUID).
-- Used by promote_user_to_admin() and other controlled bootstrap functions.
CREATE TABLE IF NOT EXISTS public.users (
  id          UUID         NOT NULL DEFAULT gen_random_uuid(),
  email       TEXT         NOT NULL,
  created_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_users       PRIMARY KEY (id),
  CONSTRAINT uq_users_email UNIQUE (email)
);

COMMENT ON TABLE  public.users       IS 'Auth identity mirror. Populated by trusted server-side auth flows only.';
COMMENT ON COLUMN public.users.id    IS 'UUID — maps to Supabase auth.users.id.';
COMMENT ON COLUMN public.users.email IS 'Canonical lower-cased email address.';

-- current_user_id():
--   Reads the app.user_id session variable that the trusted Flask middleware
--   sets after verifying the bearer token.  All RLS policies call this.
--
-- SECURITY NOTE: The app.user_id variable MUST be set exclusively by
--   server-side code that has already authenticated the request.  If a client
--   can issue SET app.user_id = '…' directly (e.g. via a raw Supabase client
--   connection without row-level pooler restrictions), all RLS is bypassed.
--   Enforce this at the Supabase connection/pooler level.
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS VARCHAR(36)
LANGUAGE sql
STABLE
SET search_path = public
AS $$
  SELECT current_setting('app.user_id', true)::varchar(36);
$$;

COMMENT ON FUNCTION public.current_user_id() IS
  'Returns the current user_id from the app.user_id session variable. '
  'Set exclusively by trusted server-side middleware after token verification. '
  'Clients must never be allowed to set app.user_id directly.';

-- ================================================================
-- CORE IDENTITY TABLES
-- ================================================================

-- profiles — one row per user; the single source of truth for role.
CREATE TABLE IF NOT EXISTS public.profiles (
  user_id     VARCHAR(36)       NOT NULL,
  role        public.user_role  NOT NULL DEFAULT 'public_trader',
  full_name   TEXT,
  avatar_url  TEXT,
  is_verified BOOLEAN           NOT NULL DEFAULT FALSE,
  created_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_profiles PRIMARY KEY (user_id)
);

COMMENT ON TABLE  public.profiles             IS 'Core user profile; one row per user. Holds role (public_trader | pro_trader | admin) and common identity fields.';
COMMENT ON COLUMN public.profiles.user_id     IS 'Maps to public.users.id (UUID stored as varchar(36)).';
COMMENT ON COLUMN public.profiles.role        IS 'user_role enum: public_trader, pro_trader, or admin.';
COMMENT ON COLUMN public.profiles.is_verified IS 'Set to TRUE after KYC / admin approval.';

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- pro_trader_profiles — extended data for pro traders.
CREATE TABLE IF NOT EXISTS public.pro_trader_profiles (
  user_id             VARCHAR(36)  NOT NULL,
  bio                 TEXT,
  market_focus        TEXT[]       NOT NULL DEFAULT '{}',
  external_links      JSONB        NOT NULL DEFAULT '{}',
  cashfree_account_id TEXT,
  subscription_price  INTEGER      NOT NULL DEFAULT 0,
  disclaimer_accepted BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_pro_trader_profiles  PRIMARY KEY (user_id),
  CONSTRAINT fk_pro_trader_prof_user FOREIGN KEY (user_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE  public.pro_trader_profiles                     IS 'Extended profile for pro traders: bio, pricing, Cashfree linkage.';
COMMENT ON COLUMN public.pro_trader_profiles.subscription_price  IS 'Base subscription price in paise (e.g. 99900 = ₹999).';
COMMENT ON COLUMN public.pro_trader_profiles.cashfree_account_id IS 'Cashfree linked account ID for payout processing.';

ALTER TABLE public.pro_trader_profiles ENABLE ROW LEVEL SECURITY;

-- learner_profiles — extended data for public-trader/learner accounts.
CREATE TABLE IF NOT EXISTS public.learner_profiles (
  user_id          VARCHAR(36)  NOT NULL,
  interests        TEXT[]       NOT NULL DEFAULT '{}',
  experience_level TEXT         CHECK (experience_level IN ('beginner', 'intermediate', 'advanced')),
  credits          INTEGER      NOT NULL DEFAULT 7,
  created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_learner_profiles  PRIMARY KEY (user_id),
  CONSTRAINT fk_learner_prof_user FOREIGN KEY (user_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE  public.learner_profiles          IS 'Extended profile for learner (public_trader) accounts.';
COMMENT ON COLUMN public.learner_profiles.credits  IS 'Free signal-unlock credits remaining (default 7 on signup).';

ALTER TABLE public.learner_profiles ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- TRADING
-- ================================================================

CREATE TABLE IF NOT EXISTS public.trades (
  id                UUID         NOT NULL DEFAULT gen_random_uuid(),
  mentor_id         VARCHAR(36)  NOT NULL,
  symbol            TEXT         NOT NULL,
  direction         TEXT         NOT NULL CHECK (direction IN ('BUY', 'SELL')),
  entry_price       DECIMAL      NOT NULL,
  stop_loss         DECIMAL      NOT NULL,
  target_price      DECIMAL      NOT NULL,
  risk_reward_ratio DECIMAL      NOT NULL,
  rationale         TEXT         NOT NULL,
  chart_image_url   TEXT,
  trade_status      TEXT         NOT NULL
    CHECK (trade_status IN ('ACTIVE', 'WIN', 'LOSS', 'CANCELLED'))
    DEFAULT 'ACTIVE',
  moderation_status TEXT         NOT NULL
    CHECK (moderation_status IN ('approved', 'flagged', 'suspended'))
    DEFAULT 'approved',
  created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  closed_at         TIMESTAMPTZ,
  CONSTRAINT pk_trades        PRIMARY KEY (id),
  CONSTRAINT fk_trades_mentor FOREIGN KEY (mentor_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE  public.trades                   IS 'Trade signals posted by pro traders.';
COMMENT ON COLUMN public.trades.risk_reward_ratio IS 'Auto-calculated: (target_price - entry_price) / (entry_price - stop_loss) for BUY.';
COMMENT ON COLUMN public.trades.trade_status      IS 'Lifecycle state: ACTIVE → WIN | LOSS | CANCELLED.';
COMMENT ON COLUMN public.trades.moderation_status IS 'Admin moderation state: approved | flagged | suspended.';

CREATE INDEX IF NOT EXISTS idx_trades_mentor_id  ON public.trades(mentor_id);
CREATE INDEX IF NOT EXISTS idx_trades_status     ON public.trades(trade_status);
CREATE INDEX IF NOT EXISTS idx_trades_created_at ON public.trades(created_at DESC);

ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- PAYMENTS & REVENUE
-- ================================================================

CREATE TABLE IF NOT EXISTS public.payments (
  id                  UUID         NOT NULL DEFAULT gen_random_uuid(),
  payer_id            VARCHAR(36)  NOT NULL,
  payee_id            VARCHAR(36),
  amount              INTEGER      NOT NULL,
  currency            TEXT         NOT NULL DEFAULT 'INR',
  cashfree_payment_id TEXT,
  status              TEXT         NOT NULL
    CHECK (status IN ('pending', 'completed', 'failed', 'refunded'))
    DEFAULT 'pending',
  payment_type        TEXT         NOT NULL
    CHECK (payment_type IN ('subscription', 'credit_pack')),
  created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_payments        PRIMARY KEY (id),
  CONSTRAINT fk_payments_payer  FOREIGN KEY (payer_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_payments_payee  FOREIGN KEY (payee_id)
    REFERENCES public.profiles(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE  public.payments        IS 'Payment records via Cashfree. All amounts in paise.';
COMMENT ON COLUMN public.payments.amount IS 'Amount in paise (e.g. 99900 = ₹999).';

CREATE INDEX IF NOT EXISTS idx_payments_payer_id ON public.payments(payer_id);
CREATE INDEX IF NOT EXISTS idx_payments_status   ON public.payments(status);

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

-- subscriptions — learner → pro trader active subscriptions.
CREATE TABLE IF NOT EXISTS public.subscriptions (
  id              UUID         NOT NULL DEFAULT gen_random_uuid(),
  learner_id      VARCHAR(36)  NOT NULL,
  mentor_id       VARCHAR(36)  NOT NULL,
  payment_id      UUID,
  status          TEXT         NOT NULL
    CHECK (status IN ('active', 'expired', 'cancelled'))
    DEFAULT 'active',
  start_date      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  end_date        TIMESTAMPTZ  NOT NULL,
  duration_months INTEGER      NOT NULL CHECK (duration_months IN (1, 3, 6)),
  created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_subscriptions         PRIMARY KEY (id),
  CONSTRAINT fk_subscriptions_learner FOREIGN KEY (learner_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_subscriptions_mentor  FOREIGN KEY (mentor_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_subscriptions_payment FOREIGN KEY (payment_id)
    REFERENCES public.payments(id) ON DELETE SET NULL
);

COMMENT ON TABLE public.subscriptions IS 'Learner → pro trader subscriptions. Revenue split applied at payment time.';

CREATE INDEX IF NOT EXISTS idx_subscriptions_learner_id ON public.subscriptions(learner_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_mentor_id  ON public.subscriptions(mentor_id);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status     ON public.subscriptions(status);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- revenue_splits — 90 % pro trader / 10 % platform records.
CREATE TABLE IF NOT EXISTS public.revenue_splits (
  id               UUID         NOT NULL DEFAULT gen_random_uuid(),
  payment_id       UUID         NOT NULL,
  mentor_id        VARCHAR(36)  NOT NULL,
  gross_amount     INTEGER      NOT NULL,
  platform_fee_pct DECIMAL      NOT NULL DEFAULT 10.0,
  platform_fee     INTEGER      NOT NULL,
  mentor_share     INTEGER      NOT NULL,
  settled          BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_revenue_splits         PRIMARY KEY (id),
  CONSTRAINT fk_revenue_splits_payment FOREIGN KEY (payment_id)
    REFERENCES public.payments(id) ON DELETE CASCADE,
  CONSTRAINT fk_revenue_splits_mentor  FOREIGN KEY (mentor_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE  public.revenue_splits              IS '90/10 revenue split records.';
COMMENT ON COLUMN public.revenue_splits.mentor_share IS 'mentor_share = gross_amount * 0.90 (paise).';
COMMENT ON COLUMN public.revenue_splits.platform_fee IS 'platform_fee = gross_amount * 0.10 (paise).';

CREATE INDEX IF NOT EXISTS idx_revenue_splits_mentor_id ON public.revenue_splits(mentor_id);
CREATE INDEX IF NOT EXISTS idx_revenue_splits_settled   ON public.revenue_splits(settled);

ALTER TABLE public.revenue_splits ENABLE ROW LEVEL SECURITY;

-- payouts — pro trader withdrawal requests and transfer records.
CREATE TABLE IF NOT EXISTS public.payouts (
  id                   UUID         NOT NULL DEFAULT gen_random_uuid(),
  mentor_id            VARCHAR(36)  NOT NULL,
  amount               INTEGER      NOT NULL,
  cashfree_transfer_id TEXT,
  status               TEXT         NOT NULL
    CHECK (status IN ('pending', 'processing', 'completed', 'failed'))
    DEFAULT 'pending',
  requested_at         TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  processed_at         TIMESTAMPTZ,
  notes                TEXT,
  CONSTRAINT pk_payouts        PRIMARY KEY (id),
  CONSTRAINT fk_payouts_mentor FOREIGN KEY (mentor_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE  public.payouts        IS 'Pro trader payout requests and Cashfree transfer records. Amounts in paise.';
COMMENT ON COLUMN public.payouts.amount IS 'Requested payout amount in paise.';

CREATE INDEX IF NOT EXISTS idx_payouts_mentor_id ON public.payouts(mentor_id);
CREATE INDEX IF NOT EXISTS idx_payouts_status    ON public.payouts(status);

ALTER TABLE public.payouts ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- MODERATION
-- ================================================================

-- learner_flags — flags raised against learner accounts.
CREATE TABLE IF NOT EXISTS public.learner_flags (
  id         UUID         NOT NULL DEFAULT gen_random_uuid(),
  learner_id VARCHAR(36)  NOT NULL,
  flagged_by VARCHAR(36),
  reason     TEXT         NOT NULL,
  status     TEXT         NOT NULL
    CHECK (status IN ('open', 'reviewed', 'dismissed'))
    DEFAULT 'open',
  verdict    TEXT,
  created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_learner_flags          PRIMARY KEY (id),
  CONSTRAINT fk_learner_flags_learner  FOREIGN KEY (learner_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_learner_flags_by       FOREIGN KEY (flagged_by)
    REFERENCES public.profiles(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.learner_flags IS 'Flags raised against learner accounts, reviewed by admins.';

CREATE INDEX IF NOT EXISTS idx_learner_flags_learner_id ON public.learner_flags(learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_flags_status     ON public.learner_flags(status);

ALTER TABLE public.learner_flags ENABLE ROW LEVEL SECURITY;

-- reports — user reports for misleading / manipulated trade signals.
CREATE TABLE IF NOT EXISTS public.reports (
  id           UUID         NOT NULL DEFAULT gen_random_uuid(),
  reporter_id  VARCHAR(36)  NOT NULL,
  trade_id     UUID         NOT NULL,
  reason       TEXT         NOT NULL,
  category     TEXT         NOT NULL
    CHECK (category IN ('misleading_chart', 'low_effort', 'manipulated', 'other')),
  status       TEXT         NOT NULL
    CHECK (status IN ('pending', 'reviewed', 'resolved', 'dismissed'))
    DEFAULT 'pending',
  verdict      TEXT,
  admin_action TEXT
    CHECK (admin_action IN ('warning', 'suspension', 'penalty', 'none')),
  created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_reports          PRIMARY KEY (id),
  CONSTRAINT fk_reports_reporter FOREIGN KEY (reporter_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_reports_trade    FOREIGN KEY (trade_id)
    REFERENCES public.trades(id) ON DELETE CASCADE
);

COMMENT ON TABLE public.reports IS 'User reports for misleading or manipulated trade signals. Reviewed and actioned by admins.';

CREATE INDEX IF NOT EXISTS idx_reports_status   ON public.reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_trade_id ON public.reports(trade_id);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- comments_threads — threaded comments on trade signals.
CREATE TABLE IF NOT EXISTS public.comments_threads (
  id         UUID         NOT NULL DEFAULT gen_random_uuid(),
  trade_id   UUID         NOT NULL,
  author_id  VARCHAR(36)  NOT NULL,
  parent_id  UUID,
  content    TEXT         NOT NULL,
  is_deleted BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_comments_threads         PRIMARY KEY (id),
  CONSTRAINT fk_comments_threads_trade   FOREIGN KEY (trade_id)
    REFERENCES public.trades(id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_threads_author  FOREIGN KEY (author_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE,
  CONSTRAINT fk_comments_threads_parent  FOREIGN KEY (parent_id)
    REFERENCES public.comments_threads(id) ON DELETE CASCADE
);

COMMENT ON TABLE public.comments_threads IS 'Threaded comments on trade signals.';

CREATE INDEX IF NOT EXISTS idx_comments_threads_trade_id  ON public.comments_threads(trade_id);
CREATE INDEX IF NOT EXISTS idx_comments_threads_author_id ON public.comments_threads(author_id);

ALTER TABLE public.comments_threads ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- NOTIFICATIONS
-- ================================================================

-- notifications — general in-app notifications (pro traders, admins).
CREATE TABLE IF NOT EXISTS public.notifications (
  id         UUID         NOT NULL DEFAULT gen_random_uuid(),
  user_id    VARCHAR(36)  NOT NULL,
  type       TEXT         NOT NULL
    CHECK (type IN ('new_trade', 'trade_closed', 'flag_alert', 'subscription', 'system', 'payout')),
  title      TEXT         NOT NULL,
  message    TEXT         NOT NULL,
  link       TEXT,
  is_read    BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_notifications      PRIMARY KEY (id),
  CONSTRAINT fk_notifications_user FOREIGN KEY (user_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.notifications IS 'In-app notifications for pro traders and admins.';

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON public.notifications(user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_unread  ON public.notifications(user_id, is_read) WHERE is_read = FALSE;

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- learner_notifications — notifications specific to learner accounts.
CREATE TABLE IF NOT EXISTS public.learner_notifications (
  id         UUID         NOT NULL DEFAULT gen_random_uuid(),
  learner_id VARCHAR(36)  NOT NULL,
  type       TEXT         NOT NULL
    CHECK (type IN ('new_signal', 'mentor_update', 'subscription_expiry', 'system')),
  title      TEXT         NOT NULL,
  message    TEXT         NOT NULL,
  link       TEXT,
  is_read    BOOLEAN      NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_learner_notifications      PRIMARY KEY (id),
  CONSTRAINT fk_learner_notifications_user FOREIGN KEY (learner_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.learner_notifications IS 'In-app notifications specific to learner (public_trader) users.';

CREATE INDEX IF NOT EXISTS idx_learner_notif_learner_id ON public.learner_notifications(learner_id);
CREATE INDEX IF NOT EXISTS idx_learner_notif_unread     ON public.learner_notifications(learner_id, is_read) WHERE is_read = FALSE;

ALTER TABLE public.learner_notifications ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- SECURITY AUDITING
-- ================================================================

CREATE TABLE IF NOT EXISTS public.login_activities (
  id             UUID         NOT NULL DEFAULT gen_random_uuid(),
  user_id        VARCHAR(36)  NOT NULL,
  ip_address     INET,
  user_agent     TEXT,
  login_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  success        BOOLEAN      NOT NULL DEFAULT TRUE,
  failure_reason TEXT,
  CONSTRAINT pk_login_activities      PRIMARY KEY (id),
  CONSTRAINT fk_login_activities_user FOREIGN KEY (user_id)
    REFERENCES public.profiles(user_id) ON DELETE CASCADE
);

COMMENT ON TABLE public.login_activities IS 'Login audit log: IP, user agent, success/failure per user.';

CREATE INDEX IF NOT EXISTS idx_login_activities_user_id  ON public.login_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_login_activities_login_at ON public.login_activities(login_at DESC);

ALTER TABLE public.login_activities ENABLE ROW LEVEL SECURITY;

-- ================================================================
-- PLATFORM ADMINISTRATION
-- ================================================================

CREATE TABLE IF NOT EXISTS public.platform_settings (
  key        TEXT         NOT NULL,
  value      TEXT         NOT NULL,
  updated_by VARCHAR(36),
  updated_at TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
  CONSTRAINT pk_platform_settings         PRIMARY KEY (key),
  CONSTRAINT fk_platform_settings_updater FOREIGN KEY (updated_by)
    REFERENCES public.profiles(user_id) ON DELETE SET NULL
);

COMMENT ON TABLE public.platform_settings IS 'Admin-configurable platform settings (credits, fee %, thresholds, etc.).';

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

INSERT INTO public.platform_settings (key, value) VALUES
  ('default_credits',               '7'),
  ('platform_fee_percent',          '10'),
  ('min_rationale_words',           '50'),
  ('max_report_flags_before_alert', '10')
ON CONFLICT (key) DO NOTHING;

-- ================================================================
-- BASE ROW-LEVEL SECURITY POLICIES
-- (owner-scoped; admin read/update policies are in the
--  20260331_002_admin_auth_hardening.sql migration)
-- ================================================================

-- Use DROP IF EXISTS + CREATE for idempotent policy management.

-- --- profiles ---
DROP POLICY IF EXISTS "profiles_select_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_update_own" ON public.profiles;
DROP POLICY IF EXISTS "profiles_insert_own" ON public.profiles;

CREATE POLICY "profiles_select_own"
  ON public.profiles FOR SELECT
  USING (current_user_id() = user_id);

CREATE POLICY "profiles_update_own"
  ON public.profiles FOR UPDATE
  USING (current_user_id() = user_id);

CREATE POLICY "profiles_insert_own"
  ON public.profiles FOR INSERT
  WITH CHECK (current_user_id() = user_id);

-- --- pro_trader_profiles ---
DROP POLICY IF EXISTS "pro_trader_profiles_select_own" ON public.pro_trader_profiles;
DROP POLICY IF EXISTS "pro_trader_profiles_update_own" ON public.pro_trader_profiles;
DROP POLICY IF EXISTS "pro_trader_profiles_insert_own" ON public.pro_trader_profiles;

CREATE POLICY "pro_trader_profiles_select_own"
  ON public.pro_trader_profiles FOR SELECT
  USING (current_user_id() = user_id);

CREATE POLICY "pro_trader_profiles_update_own"
  ON public.pro_trader_profiles FOR UPDATE
  USING (current_user_id() = user_id);

CREATE POLICY "pro_trader_profiles_insert_own"
  ON public.pro_trader_profiles FOR INSERT
  WITH CHECK (current_user_id() = user_id);

-- --- learner_profiles ---
DROP POLICY IF EXISTS "learner_profiles_select_own" ON public.learner_profiles;
DROP POLICY IF EXISTS "learner_profiles_update_own" ON public.learner_profiles;
DROP POLICY IF EXISTS "learner_profiles_insert_own" ON public.learner_profiles;

CREATE POLICY "learner_profiles_select_own"
  ON public.learner_profiles FOR SELECT
  USING (current_user_id() = user_id);

CREATE POLICY "learner_profiles_update_own"
  ON public.learner_profiles FOR UPDATE
  USING (current_user_id() = user_id);

CREATE POLICY "learner_profiles_insert_own"
  ON public.learner_profiles FOR INSERT
  WITH CHECK (current_user_id() = user_id);

-- --- trades: public read, pro-trader write ---
DROP POLICY IF EXISTS "trades_select_all"    ON public.trades;
DROP POLICY IF EXISTS "trades_insert_mentor" ON public.trades;
DROP POLICY IF EXISTS "trades_update_mentor" ON public.trades;

CREATE POLICY "trades_select_all"
  ON public.trades FOR SELECT
  USING (true);

CREATE POLICY "trades_insert_mentor"
  ON public.trades FOR INSERT
  WITH CHECK (
    current_user_id() = mentor_id
    AND EXISTS (
      SELECT 1 FROM public.profiles
      WHERE user_id = current_user_id() AND role = 'pro_trader'
    )
  );

CREATE POLICY "trades_update_mentor"
  ON public.trades FOR UPDATE
  USING (current_user_id() = mentor_id);

-- --- payments ---
DROP POLICY IF EXISTS "payments_select_own" ON public.payments;
DROP POLICY IF EXISTS "payments_insert_own" ON public.payments;

CREATE POLICY "payments_select_own"
  ON public.payments FOR SELECT
  USING (current_user_id() = payer_id OR current_user_id() = payee_id);

CREATE POLICY "payments_insert_own"
  ON public.payments FOR INSERT
  WITH CHECK (current_user_id() = payer_id);

-- --- subscriptions ---
DROP POLICY IF EXISTS "subscriptions_select_own"     ON public.subscriptions;
DROP POLICY IF EXISTS "subscriptions_insert_learner" ON public.subscriptions;

CREATE POLICY "subscriptions_select_own"
  ON public.subscriptions FOR SELECT
  USING (current_user_id() = learner_id OR current_user_id() = mentor_id);

CREATE POLICY "subscriptions_insert_learner"
  ON public.subscriptions FOR INSERT
  WITH CHECK (current_user_id() = learner_id);

-- --- revenue_splits: mentor sees their own ---
DROP POLICY IF EXISTS "revenue_splits_select_mentor" ON public.revenue_splits;

CREATE POLICY "revenue_splits_select_mentor"
  ON public.revenue_splits FOR SELECT
  USING (current_user_id() = mentor_id);

-- --- payouts ---
DROP POLICY IF EXISTS "payouts_select_own" ON public.payouts;
DROP POLICY IF EXISTS "payouts_insert_own" ON public.payouts;

CREATE POLICY "payouts_select_own"
  ON public.payouts FOR SELECT
  USING (current_user_id() = mentor_id);

CREATE POLICY "payouts_insert_own"
  ON public.payouts FOR INSERT
  WITH CHECK (current_user_id() = mentor_id);

-- --- learner_flags: learner sees own flags ---
DROP POLICY IF EXISTS "learner_flags_select_own" ON public.learner_flags;
DROP POLICY IF EXISTS "learner_flags_insert"     ON public.learner_flags;

CREATE POLICY "learner_flags_select_own"
  ON public.learner_flags FOR SELECT
  USING (current_user_id() = learner_id);

CREATE POLICY "learner_flags_insert"
  ON public.learner_flags FOR INSERT
  WITH CHECK (true);  -- any authenticated user can raise a flag; restrict in app layer

-- --- reports ---
DROP POLICY IF EXISTS "reports_select_own"  ON public.reports;
DROP POLICY IF EXISTS "reports_insert_auth" ON public.reports;

CREATE POLICY "reports_select_own"
  ON public.reports FOR SELECT
  USING (current_user_id() = reporter_id);

CREATE POLICY "reports_insert_auth"
  ON public.reports FOR INSERT
  WITH CHECK (current_user_id() = reporter_id);

-- --- comments_threads: public read, author write ---
DROP POLICY IF EXISTS "comments_threads_select_all"  ON public.comments_threads;
DROP POLICY IF EXISTS "comments_threads_insert_auth" ON public.comments_threads;
DROP POLICY IF EXISTS "comments_threads_update_own"  ON public.comments_threads;
DROP POLICY IF EXISTS "comments_threads_delete_own"  ON public.comments_threads;

CREATE POLICY "comments_threads_select_all"
  ON public.comments_threads FOR SELECT
  USING (true);

CREATE POLICY "comments_threads_insert_auth"
  ON public.comments_threads FOR INSERT
  WITH CHECK (current_user_id() = author_id);

CREATE POLICY "comments_threads_update_own"
  ON public.comments_threads FOR UPDATE
  USING (current_user_id() = author_id);

CREATE POLICY "comments_threads_delete_own"
  ON public.comments_threads FOR DELETE
  USING (current_user_id() = author_id);

-- --- notifications ---
DROP POLICY IF EXISTS "notifications_select_own" ON public.notifications;
DROP POLICY IF EXISTS "notifications_update_own" ON public.notifications;
DROP POLICY IF EXISTS "notifications_insert"     ON public.notifications;

CREATE POLICY "notifications_select_own"
  ON public.notifications FOR SELECT
  USING (current_user_id() = user_id);

CREATE POLICY "notifications_update_own"
  ON public.notifications FOR UPDATE
  USING (current_user_id() = user_id);

CREATE POLICY "notifications_insert"
  ON public.notifications FOR INSERT
  WITH CHECK (true);  -- server-side inserts; enforce via trusted app code

-- --- learner_notifications ---
DROP POLICY IF EXISTS "learner_notifications_select_own" ON public.learner_notifications;
DROP POLICY IF EXISTS "learner_notifications_update_own" ON public.learner_notifications;
DROP POLICY IF EXISTS "learner_notifications_insert"     ON public.learner_notifications;

CREATE POLICY "learner_notifications_select_own"
  ON public.learner_notifications FOR SELECT
  USING (current_user_id() = learner_id);

CREATE POLICY "learner_notifications_update_own"
  ON public.learner_notifications FOR UPDATE
  USING (current_user_id() = learner_id);

CREATE POLICY "learner_notifications_insert"
  ON public.learner_notifications FOR INSERT
  WITH CHECK (true);  -- server-side inserts only

-- --- login_activities: users see their own log ---
DROP POLICY IF EXISTS "login_activities_select_own" ON public.login_activities;
DROP POLICY IF EXISTS "login_activities_insert"     ON public.login_activities;

CREATE POLICY "login_activities_select_own"
  ON public.login_activities FOR SELECT
  USING (current_user_id() = user_id);

CREATE POLICY "login_activities_insert"
  ON public.login_activities FOR INSERT
  WITH CHECK (true);  -- server-side inserts only

-- --- platform_settings: public read, admin update (admin policy in hardening migration) ---
DROP POLICY IF EXISTS "platform_settings_select_all" ON public.platform_settings;

CREATE POLICY "platform_settings_select_all"
  ON public.platform_settings FOR SELECT
  USING (true);

COMMIT;
