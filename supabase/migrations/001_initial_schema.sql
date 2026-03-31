-- =============================================================
-- TradeWise Database Schema
-- Supabase Project: jzzazbmufhjaaivlbidk
-- Generated: 2026-03-09
-- =============================================================

-- ===========================================
-- 1. PROFILES (extends auth.users)
-- ===========================================
CREATE TABLE public.profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('public_trader', 'pro_trader', 'admin')) DEFAULT 'public_trader',
  avatar_url TEXT,
  interests TEXT[] DEFAULT '{}',
  experience_level TEXT CHECK (experience_level IN ('beginner', 'intermediate')),
  bio TEXT,
  market_focus TEXT[] DEFAULT '{}',
  external_links JSONB DEFAULT '{}',
  cashfree_account_id TEXT,
  is_verified BOOLEAN DEFAULT FALSE,
  subscription_price INTEGER DEFAULT 0,
  credits INTEGER DEFAULT 7,
  disclaimer_accepted BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.profiles IS 'User profiles extending auth.users — stores role, credits, and settings';
COMMENT ON COLUMN public.profiles.role IS 'User role: public_trader (gets tips), pro_trader (gives tips), admin';
COMMENT ON COLUMN public.profiles.credits IS 'Free trial unlocks remaining (default 7 for public traders)';
COMMENT ON COLUMN public.profiles.subscription_price IS 'Base subscription price set by pro trader, in paise (99900 = ₹999)';
COMMENT ON COLUMN public.profiles.cashfree_account_id IS 'Cashfree linked account ID for pro trader payouts';

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 2. TRADES (trade signals)
-- ===========================================
CREATE TABLE public.trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mentor_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  symbol TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('BUY', 'SELL')),
  entry_price DECIMAL NOT NULL,
  stop_loss DECIMAL NOT NULL,
  target_price DECIMAL NOT NULL,
  risk_reward_ratio DECIMAL NOT NULL,
  rationale TEXT NOT NULL,
  chart_image_url TEXT,
  trade_status TEXT NOT NULL CHECK (trade_status IN ('ACTIVE', 'WIN', 'LOSS')) DEFAULT 'ACTIVE',
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  closed_at TIMESTAMPTZ
);

COMMENT ON TABLE public.trades IS 'Trade signals posted by pro traders with entry/SL/target levels';
COMMENT ON COLUMN public.trades.symbol IS 'NSE/BSE stock symbol e.g. RELIANCE, INFY';
COMMENT ON COLUMN public.trades.risk_reward_ratio IS 'Auto-calculated (target-entry)/(entry-SL) for BUY';
COMMENT ON COLUMN public.trades.trade_status IS 'ACTIVE = open, WIN = target hit, LOSS = SL hit';

CREATE INDEX idx_trades_mentor_id ON public.trades(mentor_id);
CREATE INDEX idx_trades_status ON public.trades(trade_status);
CREATE INDEX idx_trades_created_at ON public.trades(created_at DESC);

ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 3. MENTOR STATS
-- ===========================================
CREATE TABLE public.mentor_stats (
  mentor_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  total_trades INTEGER DEFAULT 0 NOT NULL,
  winning_trades INTEGER DEFAULT 0 NOT NULL,
  losing_trades INTEGER DEFAULT 0 NOT NULL,
  accuracy_pct DECIMAL DEFAULT 0.0 NOT NULL,
  avg_risk_reward DECIMAL DEFAULT 0.0 NOT NULL
);

COMMENT ON TABLE public.mentor_stats IS 'Aggregated trade performance stats for pro traders';
COMMENT ON COLUMN public.mentor_stats.accuracy_pct IS 'Calculated as (winning_trades / total_trades) * 100';

ALTER TABLE public.mentor_stats ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 4. UNLOCKED TRADES
-- ===========================================
CREATE TABLE public.unlocked_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  trade_id UUID NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  unlocked_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  UNIQUE(user_id, trade_id)
);

COMMENT ON TABLE public.unlocked_trades IS 'Records of credit-based signal unlocks by public traders';

CREATE INDEX idx_unlocked_trades_user ON public.unlocked_trades(user_id);

ALTER TABLE public.unlocked_trades ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 5. SUBSCRIPTION PLANS
-- ===========================================
CREATE TABLE public.subscription_plans (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mentor_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  duration_months INTEGER NOT NULL CHECK (duration_months IN (1, 3, 6)),
  price INTEGER NOT NULL CHECK (price > 0),
  is_active BOOLEAN DEFAULT TRUE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  UNIQUE(mentor_id, duration_months)
);

COMMENT ON TABLE public.subscription_plans IS 'Subscription pricing per pro trader — 1, 3, or 6 month plans';
COMMENT ON COLUMN public.subscription_plans.price IS 'Price in paise e.g. 99900 = ₹999';

CREATE INDEX idx_subscription_plans_mentor ON public.subscription_plans(mentor_id);

ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 6. SUBSCRIPTIONS
-- ===========================================
CREATE TABLE public.subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  public_trader_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  mentor_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  plan_id UUID NOT NULL REFERENCES public.subscription_plans(id) ON DELETE CASCADE,
  cashfree_payment_id TEXT,
  status TEXT NOT NULL CHECK (status IN ('active', 'expired')) DEFAULT 'active',
  start_date TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  end_date TIMESTAMPTZ NOT NULL
);

COMMENT ON TABLE public.subscriptions IS 'Tracks paid subscriptions — public trader to pro trader';
COMMENT ON COLUMN public.subscriptions.end_date IS 'Auto-set based on plan duration at payment time';

CREATE INDEX idx_subscriptions_public_trader ON public.subscriptions(public_trader_id);
CREATE INDEX idx_subscriptions_mentor ON public.subscriptions(mentor_id);
CREATE INDEX idx_subscriptions_status ON public.subscriptions(status);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 7. REPORTS (flagging)
-- ===========================================
CREATE TABLE public.reports (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  reporter_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  trade_id UUID NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  reason TEXT NOT NULL,
  category TEXT NOT NULL CHECK (category IN ('misleading_chart', 'low_effort', 'manipulated')),
  status TEXT NOT NULL CHECK (status IN ('pending', 'resolved')) DEFAULT 'pending',
  admin_action TEXT CHECK (admin_action IN ('warning', 'suspension', 'penalty')),
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.reports IS 'User reports for misleading/manipulated trade signals';

CREATE INDEX idx_reports_status ON public.reports(status);
CREATE INDEX idx_reports_trade ON public.reports(trade_id);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 8. COMMENTS
-- ===========================================
CREATE TABLE public.comments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id UUID NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.comments IS 'Comment threads on trade signals';

CREATE INDEX idx_comments_trade ON public.comments(trade_id);
CREATE INDEX idx_comments_created_at ON public.comments(trade_id, created_at);

ALTER TABLE public.comments ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 9. NOTIFICATIONS
-- ===========================================
CREATE TABLE public.notifications (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  type TEXT NOT NULL CHECK (type IN ('new_trade', 'trade_closed', 'flag_alert', 'subscription')),
  title TEXT NOT NULL,
  message TEXT NOT NULL,
  link TEXT,
  is_read BOOLEAN DEFAULT FALSE NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.notifications IS 'In-app notification system for all user types';

CREATE INDEX idx_notifications_user ON public.notifications(user_id);
CREATE INDEX idx_notifications_unread ON public.notifications(user_id, is_read) WHERE is_read = FALSE;

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 10. WALLET
-- ===========================================
CREATE TABLE public.wallet (
  mentor_id UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE,
  total_earnings INTEGER DEFAULT 0 NOT NULL,
  available_balance INTEGER DEFAULT 0 NOT NULL,
  pending_balance INTEGER DEFAULT 0 NOT NULL
);

COMMENT ON TABLE public.wallet IS 'Pro trader earnings — all amounts in paise';
COMMENT ON COLUMN public.wallet.total_earnings IS 'Lifetime earnings in paise';
COMMENT ON COLUMN public.wallet.available_balance IS 'Withdrawable balance in paise';
COMMENT ON COLUMN public.wallet.pending_balance IS 'Pending payout balance in paise';

ALTER TABLE public.wallet ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 11. TRANSACTIONS
-- ===========================================
CREATE TABLE public.transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  mentor_id UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  amount INTEGER NOT NULL,
  type TEXT NOT NULL CHECK (type IN ('earning', 'withdrawal')),
  cashfree_transfer_id TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.transactions IS 'Pro trader earning and withdrawal history';
COMMENT ON COLUMN public.transactions.amount IS 'Amount in paise';

CREATE INDEX idx_transactions_mentor ON public.transactions(mentor_id);
CREATE INDEX idx_transactions_created_at ON public.transactions(mentor_id, created_at DESC);

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 12. PLATFORM SETTINGS
-- ===========================================
CREATE TABLE public.platform_settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_by UUID REFERENCES public.profiles(id),
  updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

COMMENT ON TABLE public.platform_settings IS 'Admin-configurable platform settings (default credits, fee %, etc.)';

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

-- Default settings
INSERT INTO public.platform_settings (key, value) VALUES
  ('default_credits', '7'),
  ('platform_fee_percent', '10'),
  ('min_rationale_words', '50'),
  ('max_report_flags_before_alert', '10');
