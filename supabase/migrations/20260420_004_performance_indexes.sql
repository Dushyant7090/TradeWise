-- Performance-focused composite and search indexes for high-traffic list/filter paths.
-- Safe to re-run because all statements use IF NOT EXISTS.

CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Learner feed and pro-trader trade listing patterns.
CREATE INDEX IF NOT EXISTS idx_trades_status_created_at
  ON public.trades (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_trades_status_view_count
  ON public.trades (status, view_count DESC);

CREATE INDEX IF NOT EXISTS idx_trades_trader_status_created_at
  ON public.trades (trader_id, status, created_at DESC);

-- ILIKE search support on symbols and profile names.
CREATE INDEX IF NOT EXISTS idx_trades_symbol_trgm
  ON public.trades USING gin (symbol gin_trgm_ops);

CREATE INDEX IF NOT EXISTS idx_profiles_display_name_trgm
  ON public.profiles USING gin (display_name gin_trgm_ops);

-- Subscription lookups in learner/pro dashboards and access checks.
CREATE INDEX IF NOT EXISTS idx_subscriptions_subscriber_status_ends_at
  ON public.subscriptions (subscriber_id, status, ends_at DESC);

CREATE INDEX IF NOT EXISTS idx_subscriptions_trader_status_ends_at
  ON public.subscriptions (trader_id, status, ends_at DESC);

-- Admin list and analytics filters.
CREATE INDEX IF NOT EXISTS idx_reports_status_created_at
  ON public.reports (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_learner_flags_status_created_at
  ON public.learner_flags (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_payouts_status_initiated_at
  ON public.payouts (status, initiated_at DESC);

CREATE INDEX IF NOT EXISTS idx_payments_status_created_at
  ON public.payments (status, created_at DESC);
