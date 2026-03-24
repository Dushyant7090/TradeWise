-- =============================================================
-- TradeWise Database Schema (Corrected & Complete)
-- Supabase/PostgreSQL
-- Updated: 2026-03-24
--
-- CHANGELOG vs previous schema.sql:
--  [NEW]     Added: users table (backend uses its own JWT auth, not Supabase auth)
--  [CHANGED] profiles: now references users.id via user_id FK (not auth.users.id),
--             removed fields moved to pro_trader_profiles/learner_profiles
--  [NEW]     Added: pro_trader_profiles table (bio, KYC, bank, stats, financials)
--  [NEW]     Added: learner_profiles table (interests, experience, credits, spending)
--  [CHANGED] trades: renamed mentor_id→trader_id, stop_loss→stop_loss_price,
--             risk_reward_ratio→rrr, rationale→technical_rationale; updated
--             status values (active/target_hit/sl_hit/cancelled, not ACTIVE/WIN/LOSS);
--             added outcome, view_count, unlock_count, flag_count,
--             closed_by_trader_at, close_reason
--  [REMOVED] mentor_stats: stats now stored directly in pro_trader_profiles
--  [RENAMED] unlocked_trades → learner_unlocked_trades; added via_credit,
--             viewed_at, rating, notes columns; unique constraint name updated
--  [REMOVED] subscription_plans: backend creates subscriptions directly from
--             pro_trader_profile.monthly_subscription_price (no plan model)
--  [CHANGED] subscriptions: renamed public_trader_id→subscriber_id,
--             mentor_id→trader_id, start_date→started_at, end_date→ends_at;
--             removed plan_id FK; added auto_renew, payment_id FK;
--             status now allows 'cancelled' in addition to 'active'/'expired'
--  [NEW]     Added: payments table (Cashfree order/payment tracking)
--  [NEW]     Added: payouts table (pro-trader withdrawal tracking)
--  [NEW]     Added: revenue_splits table (90/10 split records per payment)
--  [CHANGED] reports: removed category column; updated status values to include
--             'investigating'; replaced admin_action with admin_verdict TEXT;
--             added resolved_at
--  [RENAMED] comments → comments_threads; added updated_at column
--  [CHANGED] notifications: replaced link TEXT with data JSONB; relaxed type
--             CHECK to allow all backend notification types
--  [NEW]     Added: learner_notifications table
--  [NEW]     Added: notification_preferences table (pro-trader preferences)
--  [NEW]     Added: learner_notification_preferences table
--  [NEW]     Added: learner_trade_ratings table
--  [NEW]     Added: learner_credits_log table
--  [NEW]     Added: learner_flags table
--  [NEW]     Added: login_activities table
--  [REMOVED] wallet (balance tracked in pro_trader_profiles)
--  [REMOVED] transactions (superseded by payouts + revenue_splits)
--  [KEPT]    platform_settings (admin-configurable; updated_by now refs users.id)
-- =============================================================

-- ===========================================
-- 1. USERS (backend custom auth — not Supabase auth.users)
-- ===========================================
-- [NEW] The Flask backend manages its own user table with password hashing,
--       TOTP 2FA, and JWT authentication independent of Supabase Auth.
CREATE TABLE public.users (
  id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  email        TEXT NOT NULL UNIQUE,
  password_hash TEXT,
  auth_provider TEXT NOT NULL DEFAULT 'email',
  is_active    BOOLEAN NOT NULL DEFAULT TRUE,
  totp_secret  TEXT,
  totp_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.users IS 'Core user accounts managed by the Flask backend (own JWT auth, not Supabase Auth)';
COMMENT ON COLUMN public.users.auth_provider IS 'Authentication method: email, google, etc.';
COMMENT ON COLUMN public.users.totp_secret IS 'Encrypted TOTP secret for 2FA (null if disabled)';

CREATE INDEX idx_users_email ON public.users(email);

ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 2. PROFILES (basic profile — 1:1 with users)
-- ===========================================
-- [CHANGED] Now references public.users.id via user_id column (was auth.users.id via id PK).
--           Heavy-weight fields split into pro_trader_profiles and learner_profiles.
CREATE TABLE public.profiles (
  id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id      TEXT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  role         TEXT NOT NULL DEFAULT 'public_trader'
                 CHECK (role IN ('public_trader', 'pro_trader', 'admin')),
  display_name TEXT,
  avatar_url   TEXT,
  is_verified  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.profiles IS 'Basic user profile (role, display name, avatar). Extended by pro_trader_profiles or learner_profiles.';
COMMENT ON COLUMN public.profiles.role IS 'User role: public_trader (learner), pro_trader, or admin';

CREATE INDEX idx_profiles_user_id ON public.profiles(user_id);
CREATE INDEX idx_profiles_role ON public.profiles(role);

ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 3. PRO TRADER PROFILES
-- ===========================================
-- [NEW] Extended profile for pro traders: KYC, bank details, stats, financials.
CREATE TABLE public.pro_trader_profiles (
  id                             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                        TEXT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  bio                            TEXT,
  specializations                JSONB DEFAULT '[]'::JSONB,
  external_portfolio_url         TEXT,
  years_of_experience            INTEGER NOT NULL DEFAULT 0,
  trading_style                  TEXT CHECK (trading_style IN ('scalping','intraday','swing','positional','long_term')),
  -- Bank details (account number stored encrypted in application layer)
  bank_account_number_encrypted  TEXT,
  ifsc_code                      TEXT,
  account_holder_name            TEXT,
  bank_account_last_4            TEXT,
  -- KYC
  kyc_status                     TEXT NOT NULL DEFAULT 'pending'
                                   CHECK (kyc_status IN ('pending','verified','rejected')),
  kyc_documents                  JSONB DEFAULT '{}'::JSONB,
  -- Performance stats (updated by backend on trade close)
  accuracy_score                 NUMERIC(5,2) NOT NULL DEFAULT 0.0,
  total_trades                   INTEGER NOT NULL DEFAULT 0,
  winning_trades                 INTEGER NOT NULL DEFAULT 0,
  leaderboard_rank               INTEGER,
  total_subscribers              INTEGER NOT NULL DEFAULT 0,
  -- Financials (in rupees with 2 decimal places)
  monthly_subscription_price     NUMERIC(12,2) NOT NULL DEFAULT 0.0,
  total_earnings                 NUMERIC(12,2) NOT NULL DEFAULT 0.0,
  available_balance              NUMERIC(12,2) NOT NULL DEFAULT 0.0,
  -- Media
  profile_picture_url            TEXT,
  is_active                      BOOLEAN NOT NULL DEFAULT TRUE,
  created_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at                     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.pro_trader_profiles IS 'Extended profile for pro traders: KYC, bank, performance stats, and financials';
COMMENT ON COLUMN public.pro_trader_profiles.bank_account_number_encrypted IS 'AES-encrypted bank account number; decrypted in application layer only';
COMMENT ON COLUMN public.pro_trader_profiles.accuracy_score IS 'Win rate percentage: (winning_trades / total_trades) * 100';
COMMENT ON COLUMN public.pro_trader_profiles.monthly_subscription_price IS 'Subscription price in INR (e.g. 999.00)';
COMMENT ON COLUMN public.pro_trader_profiles.available_balance IS 'Withdrawable balance in INR';

CREATE INDEX idx_pro_trader_profiles_user_id ON public.pro_trader_profiles(user_id);
CREATE INDEX idx_pro_trader_profiles_kyc_status ON public.pro_trader_profiles(kyc_status);
CREATE INDEX idx_pro_trader_profiles_leaderboard ON public.pro_trader_profiles(leaderboard_rank) WHERE leaderboard_rank IS NOT NULL;

ALTER TABLE public.pro_trader_profiles ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 4. LEARNER PROFILES
-- ===========================================
-- [NEW] Extended profile for learners (public_traders): interests, credits, spending.
CREATE TABLE public.learner_profiles (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id               TEXT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  interests             JSONB DEFAULT '[]'::JSONB,
  experience_level      TEXT NOT NULL DEFAULT 'beginner'
                          CHECK (experience_level IN ('beginner','intermediate','advanced')),
  credits               INTEGER NOT NULL DEFAULT 7,
  total_unlocked_trades INTEGER NOT NULL DEFAULT 0,
  total_spent           NUMERIC(12,2) NOT NULL DEFAULT 0.0,
  favorite_traders      JSONB DEFAULT '[]'::JSONB,
  learning_goal         TEXT,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.learner_profiles IS 'Extended profile for learners: credits, interests, unlock history';
COMMENT ON COLUMN public.learner_profiles.credits IS 'Remaining free-trial unlock credits (default 7 on signup)';
COMMENT ON COLUMN public.learner_profiles.total_spent IS 'Total amount spent on subscriptions/credits in INR';

CREATE INDEX idx_learner_profiles_user_id ON public.learner_profiles(user_id);

ALTER TABLE public.learner_profiles ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 5. TRADES (trade signals)
-- ===========================================
-- [CHANGED] mentor_id → trader_id; stop_loss → stop_loss_price;
--           risk_reward_ratio → rrr; rationale → technical_rationale;
--           status values changed to lowercase (active/target_hit/sl_hit/cancelled);
--           added outcome, view_count, unlock_count, flag_count,
--           closed_by_trader_at, close_reason.
CREATE TABLE public.trades (
  id                    TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trader_id             TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  symbol                TEXT NOT NULL,
  direction             TEXT NOT NULL CHECK (direction IN ('buy','sell')),
  entry_price           NUMERIC(16,4) NOT NULL,
  stop_loss_price       NUMERIC(16,4) NOT NULL,
  target_price          NUMERIC(16,4) NOT NULL,
  rrr                   NUMERIC(8,4) NOT NULL,
  technical_rationale   TEXT NOT NULL,
  chart_image_url       TEXT,
  status                TEXT NOT NULL DEFAULT 'active'
                          CHECK (status IN ('active','target_hit','sl_hit','cancelled')),
  outcome               TEXT CHECK (outcome IN ('win','loss')),
  view_count            INTEGER NOT NULL DEFAULT 0,
  unlock_count          INTEGER NOT NULL DEFAULT 0,
  flag_count            INTEGER NOT NULL DEFAULT 0,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  closed_at             TIMESTAMPTZ,
  closed_by_trader_at   TIMESTAMPTZ,
  close_reason          TEXT
);

COMMENT ON TABLE public.trades IS 'Trade signals posted by pro traders (mentors)';
COMMENT ON COLUMN public.trades.direction IS 'Trade direction: buy or sell (lowercase)';
COMMENT ON COLUMN public.trades.rrr IS 'Risk-reward ratio: auto-calculated by backend on create';
COMMENT ON COLUMN public.trades.status IS 'active = open; target_hit / sl_hit = auto-closed; cancelled = trader-closed';
COMMENT ON COLUMN public.trades.outcome IS 'win (target hit) or loss (SL hit); null while active or cancelled';

CREATE INDEX idx_trades_trader_id ON public.trades(trader_id);
CREATE INDEX idx_trades_status ON public.trades(status);
CREATE INDEX idx_trades_created_at ON public.trades(created_at DESC);
CREATE INDEX idx_trades_symbol ON public.trades(symbol);

ALTER TABLE public.trades ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 6. LEARNER UNLOCKED TRADES
-- ===========================================
-- [RENAMED & CHANGED] Was unlocked_trades. Added via_credit, viewed_at, rating, notes.
CREATE TABLE public.learner_unlocked_trades (
  id          TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id  TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trade_id    TEXT NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  unlocked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  via_credit  BOOLEAN NOT NULL DEFAULT TRUE,
  viewed_at   TIMESTAMPTZ,
  rating      SMALLINT CHECK (rating BETWEEN 1 AND 5),
  notes       TEXT,
  CONSTRAINT uq_learner_unlocked_trade UNIQUE (learner_id, trade_id)
);

COMMENT ON TABLE public.learner_unlocked_trades IS 'Tracks which learners have unlocked (paid for or credit-redeemed) each trade signal';
COMMENT ON COLUMN public.learner_unlocked_trades.via_credit IS 'TRUE = used a free credit; FALSE = via active subscription';

CREATE INDEX idx_learner_unlocked_learner ON public.learner_unlocked_trades(learner_id);
CREATE INDEX idx_learner_unlocked_trade ON public.learner_unlocked_trades(trade_id);

ALTER TABLE public.learner_unlocked_trades ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 7. PAYMENTS
-- ===========================================
-- [NEW] Cashfree payment records for subscription purchases.
CREATE TABLE public.payments (
  id                   TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  subscriber_id        TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trader_id            TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  amount               NUMERIC(12,2) NOT NULL,
  currency             TEXT NOT NULL DEFAULT 'INR',
  cashfree_order_id    TEXT UNIQUE,
  cashfree_payment_id  TEXT,
  status               TEXT NOT NULL DEFAULT 'pending'
                         CHECK (status IN ('pending','success','failed','refunded')),
  payment_method       TEXT,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at         TIMESTAMPTZ
);

COMMENT ON TABLE public.payments IS 'Cashfree payment records for subscription purchases';
COMMENT ON COLUMN public.payments.amount IS 'Payment amount in INR';
COMMENT ON COLUMN public.payments.cashfree_order_id IS 'Unique Cashfree order ID (for idempotency)';

CREATE INDEX idx_payments_subscriber ON public.payments(subscriber_id);
CREATE INDEX idx_payments_trader ON public.payments(trader_id);
CREATE INDEX idx_payments_status ON public.payments(status);
CREATE INDEX idx_payments_cashfree_order ON public.payments(cashfree_order_id) WHERE cashfree_order_id IS NOT NULL;

ALTER TABLE public.payments ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 8. SUBSCRIPTIONS
-- ===========================================
-- [CHANGED] public_trader_id → subscriber_id; mentor_id → trader_id;
--           start_date → started_at; end_date → ends_at; removed plan_id FK;
--           added auto_renew, payment_id FK; status now includes 'cancelled'.
CREATE TABLE public.subscriptions (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  subscriber_id TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trader_id     TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ends_at       TIMESTAMPTZ NOT NULL,
  status        TEXT NOT NULL DEFAULT 'active'
                  CHECK (status IN ('active','expired','cancelled')),
  auto_renew    BOOLEAN NOT NULL DEFAULT FALSE,
  payment_id    TEXT REFERENCES public.payments(id) ON DELETE SET NULL,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.subscriptions IS 'Learner → Pro-trader paid subscriptions';
COMMENT ON COLUMN public.subscriptions.ends_at IS 'Subscription expiry; backend extends this on renewal';
COMMENT ON COLUMN public.subscriptions.auto_renew IS 'Whether to auto-renew on expiry (handled by backend job)';

CREATE INDEX idx_subscriptions_subscriber ON public.subscriptions(subscriber_id);
CREATE INDEX idx_subscriptions_trader ON public.subscriptions(trader_id);
CREATE INDEX idx_subscriptions_status ON public.subscriptions(status);
CREATE INDEX idx_subscriptions_ends_at ON public.subscriptions(ends_at) WHERE status = 'active';

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 9. PAYOUTS
-- ===========================================
-- [NEW] Pro-trader withdrawal records via Cashfree Payouts.
CREATE TABLE public.payouts (
  id                   TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trader_id            TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  amount               NUMERIC(12,2) NOT NULL,
  cashfree_payout_id   TEXT,
  cashfree_transfer_id TEXT,
  status               TEXT NOT NULL DEFAULT 'initiated'
                         CHECK (status IN ('initiated','processing','success','failed')),
  bank_account_last_4  TEXT,
  initiated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  completed_at         TIMESTAMPTZ,
  failure_reason       TEXT
);

COMMENT ON TABLE public.payouts IS 'Pro-trader payout (withdrawal) requests via Cashfree';
COMMENT ON COLUMN public.payouts.amount IS 'Withdrawal amount in INR';
COMMENT ON COLUMN public.payouts.cashfree_transfer_id IS 'Unique transfer ID sent to Cashfree Payouts API';

CREATE INDEX idx_payouts_trader ON public.payouts(trader_id);
CREATE INDEX idx_payouts_status ON public.payouts(status);

ALTER TABLE public.payouts ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 10. REVENUE SPLITS
-- ===========================================
-- [NEW] Records the 90/10 revenue split per successful payment.
CREATE TABLE public.revenue_splits (
  id                        TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  payment_id                TEXT NOT NULL UNIQUE REFERENCES public.payments(id) ON DELETE CASCADE,
  trader_id                 TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  pro_trader_amount         NUMERIC(12,2) NOT NULL,
  admin_amount              NUMERIC(12,2) NOT NULL,
  split_percentage_pro      INTEGER NOT NULL DEFAULT 90
                              CHECK (split_percentage_pro BETWEEN 0 AND 100),
  split_percentage_admin    INTEGER NOT NULL DEFAULT 10
                              CHECK (split_percentage_admin BETWEEN 0 AND 100),
  pro_trader_wallet_credited BOOLEAN NOT NULL DEFAULT FALSE,
  admin_wallet_credited     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.revenue_splits IS '90/10 revenue split record created for each successful payment';
COMMENT ON COLUMN public.revenue_splits.pro_trader_amount IS 'Amount credited to pro trader (90%) in INR';
COMMENT ON COLUMN public.revenue_splits.admin_amount IS 'Platform fee (10%) in INR';

CREATE INDEX idx_revenue_splits_trader ON public.revenue_splits(trader_id);
CREATE INDEX idx_revenue_splits_payment ON public.revenue_splits(payment_id);

ALTER TABLE public.revenue_splits ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 11. REPORTS (trade signal flagging)
-- ===========================================
-- [CHANGED] Removed category column; status now includes 'investigating';
--           replaced admin_action (enum) with admin_verdict (free text); added resolved_at.
CREATE TABLE public.reports (
  id             TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trade_id       TEXT NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  reporter_id    TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  reason         TEXT NOT NULL,
  status         TEXT NOT NULL DEFAULT 'pending'
                   CHECK (status IN ('pending','investigating','resolved')),
  admin_verdict  TEXT,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at    TIMESTAMPTZ
);

COMMENT ON TABLE public.reports IS 'Learner reports on misleading or manipulated trade signals';
COMMENT ON COLUMN public.reports.status IS 'pending → investigating → resolved';
COMMENT ON COLUMN public.reports.admin_verdict IS 'Free-text admin decision (e.g. warning, no action, suspension)';

CREATE INDEX idx_reports_trade ON public.reports(trade_id);
CREATE INDEX idx_reports_reporter ON public.reports(reporter_id);
CREATE INDEX idx_reports_status ON public.reports(status);

ALTER TABLE public.reports ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 12. COMMENTS THREADS
-- ===========================================
-- [RENAMED & CHANGED] Was 'comments'. Table renamed to comments_threads to match
--                     backend Comment model. Added updated_at column.
CREATE TABLE public.comments_threads (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trade_id   TEXT NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  user_id    TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  content    TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.comments_threads IS 'Comment threads on trade signals (one row per comment)';

CREATE INDEX idx_comments_threads_trade ON public.comments_threads(trade_id);
CREATE INDEX idx_comments_threads_user ON public.comments_threads(user_id);
CREATE INDEX idx_comments_threads_trade_created ON public.comments_threads(trade_id, created_at);

ALTER TABLE public.comments_threads ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 13. NOTIFICATIONS (pro-trader notifications)
-- ===========================================
-- [CHANGED] Replaced 'link TEXT' with 'data JSONB'; relaxed type CHECK to allow
--           all backend notification types without a hard enum list.
CREATE TABLE public.notifications (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id    TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  type       TEXT NOT NULL,
  title      TEXT NOT NULL,
  message    TEXT NOT NULL,
  data       JSONB DEFAULT '{}'::JSONB,
  is_read    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.notifications IS 'In-app notifications for pro traders (new subscriber, payout, KYC, etc.)';
COMMENT ON COLUMN public.notifications.type IS 'Notification type, e.g. new_subscriber, payout_confirmation, kyc_verified';
COMMENT ON COLUMN public.notifications.data IS 'Arbitrary JSON payload (trade_id, amount, etc.)';

CREATE INDEX idx_notifications_user ON public.notifications(user_id);
CREATE INDEX idx_notifications_unread ON public.notifications(user_id, is_read) WHERE is_read = FALSE;

ALTER TABLE public.notifications ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 14. LEARNER NOTIFICATIONS
-- ===========================================
-- [NEW] Separate notification table for learners to avoid type conflicts.
CREATE TABLE public.learner_notifications (
  id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id        TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  type              TEXT NOT NULL,
  title             TEXT NOT NULL,
  message           TEXT NOT NULL,
  related_trade_id  TEXT REFERENCES public.trades(id) ON DELETE SET NULL,
  related_trader_id TEXT REFERENCES public.users(id) ON DELETE SET NULL,
  is_read           BOOLEAN NOT NULL DEFAULT FALSE,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.learner_notifications IS 'In-app notifications for learners (new trade, trade closed, subscription expiring, etc.)';
COMMENT ON COLUMN public.learner_notifications.type IS 'e.g. trade_closed, new_trade, subscriber_alert, flag_update, subscription_expiring';

CREATE INDEX idx_learner_notif_learner ON public.learner_notifications(learner_id);
CREATE INDEX idx_learner_notif_unread ON public.learner_notifications(learner_id, is_read) WHERE is_read = FALSE;

ALTER TABLE public.learner_notifications ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 15. NOTIFICATION PREFERENCES (pro traders)
-- ===========================================
-- [NEW] Per-user notification opt-in settings for pro traders.
CREATE TABLE public.notification_preferences (
  id                         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                    TEXT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  email_new_subscriber       BOOLEAN NOT NULL DEFAULT TRUE,
  email_trade_flagged        BOOLEAN NOT NULL DEFAULT TRUE,
  email_payout_confirmation  BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_new_subscriber      BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_trade_flagged       BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_payout_confirmation BOOLEAN NOT NULL DEFAULT TRUE,
  sms_enabled                BOOLEAN NOT NULL DEFAULT FALSE,
  sms_phone                  TEXT,
  updated_at                 TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.notification_preferences IS 'Pro trader notification preferences (email, in-app, SMS opt-ins)';

CREATE INDEX idx_notif_prefs_user ON public.notification_preferences(user_id);

ALTER TABLE public.notification_preferences ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 16. LEARNER NOTIFICATION PREFERENCES
-- ===========================================
-- [NEW] Per-user notification opt-in settings for learners.
CREATE TABLE public.learner_notification_preferences (
  id                            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id                       TEXT NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  email_new_trade               BOOLEAN NOT NULL DEFAULT TRUE,
  email_trade_closed            BOOLEAN NOT NULL DEFAULT TRUE,
  email_subscription_expiring   BOOLEAN NOT NULL DEFAULT TRUE,
  email_flag_update             BOOLEAN NOT NULL DEFAULT TRUE,
  email_announcements           BOOLEAN NOT NULL DEFAULT FALSE,
  in_app_new_trade              BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_trade_closed           BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_subscription_expiring  BOOLEAN NOT NULL DEFAULT TRUE,
  in_app_flag_update            BOOLEAN NOT NULL DEFAULT TRUE,
  sms_enabled                   BOOLEAN NOT NULL DEFAULT FALSE,
  sms_phone                     TEXT,
  updated_at                    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.learner_notification_preferences IS 'Learner notification preferences (email, in-app, SMS opt-ins)';

CREATE INDEX idx_learner_notif_prefs_user ON public.learner_notification_preferences(user_id);

ALTER TABLE public.learner_notification_preferences ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 17. LEARNER TRADE RATINGS
-- ===========================================
-- [NEW] Star ratings and reviews left by learners on unlocked trades.
CREATE TABLE public.learner_trade_ratings (
  id            TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id    TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trade_id      TEXT NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  rating        SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
  review        TEXT,
  helpful_count INTEGER NOT NULL DEFAULT 0,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT uq_learner_trade_rating UNIQUE (learner_id, trade_id)
);

COMMENT ON TABLE public.learner_trade_ratings IS 'Learner star ratings (1–5) and optional reviews for trade signals';

CREATE INDEX idx_trade_ratings_trade ON public.learner_trade_ratings(trade_id);
CREATE INDEX idx_trade_ratings_learner ON public.learner_trade_ratings(learner_id);

ALTER TABLE public.learner_trade_ratings ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 18. LEARNER CREDITS LOG
-- ===========================================
-- [NEW] Audit trail for every credit deduction, refund, or bonus grant.
CREATE TABLE public.learner_credits_log (
  id                TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id        TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trade_id          TEXT REFERENCES public.trades(id) ON DELETE SET NULL,
  action            TEXT NOT NULL CHECK (action IN ('used','refunded','bonus')),
  amount            INTEGER NOT NULL,
  credits_remaining INTEGER NOT NULL,
  reason            TEXT,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.learner_credits_log IS 'Audit log for learner credit changes: used (unlock), refunded, or bonus';
COMMENT ON COLUMN public.learner_credits_log.amount IS 'Number of credits changed (positive = added, negative = deducted)';
COMMENT ON COLUMN public.learner_credits_log.credits_remaining IS 'Learner credit balance after this transaction';

CREATE INDEX idx_credits_log_learner ON public.learner_credits_log(learner_id);
CREATE INDEX idx_credits_log_created_at ON public.learner_credits_log(learner_id, created_at DESC);

ALTER TABLE public.learner_credits_log ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 19. LEARNER FLAGS
-- ===========================================
-- [NEW] Learner-initiated flags/reports on trade signals (distinct from admin reports).
CREATE TABLE public.learner_flags (
  id           TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  learner_id   TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  trade_id     TEXT NOT NULL REFERENCES public.trades(id) ON DELETE CASCADE,
  reason       TEXT NOT NULL,
  status       TEXT NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending','investigating','resolved')),
  admin_action TEXT CHECK (admin_action IN ('none','warning','penalty','suspension')),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  resolved_at  TIMESTAMPTZ
);

COMMENT ON TABLE public.learner_flags IS 'Learner flags on trade signals; feeds into trades.flag_count and admin review';
COMMENT ON COLUMN public.learner_flags.admin_action IS 'Action taken: none, warning, penalty, or suspension of the trader';

CREATE INDEX idx_learner_flags_learner ON public.learner_flags(learner_id);
CREATE INDEX idx_learner_flags_trade ON public.learner_flags(trade_id);
CREATE INDEX idx_learner_flags_status ON public.learner_flags(status);

ALTER TABLE public.learner_flags ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 20. LOGIN ACTIVITIES
-- ===========================================
-- [NEW] Audit log of user authentication events (login, failed login, etc.).
CREATE TABLE public.login_activities (
  id         TEXT PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  user_id    TEXT NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  ip_address TEXT,
  user_agent TEXT,
  device     TEXT,
  location   TEXT,
  status     TEXT NOT NULL DEFAULT 'success',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.login_activities IS 'Audit log of login attempts (success/failure) for security monitoring';
COMMENT ON COLUMN public.login_activities.ip_address IS 'IPv4 or IPv6 address (max 45 chars for IPv6)';
COMMENT ON COLUMN public.login_activities.status IS 'success or failed';

CREATE INDEX idx_login_activities_user ON public.login_activities(user_id);
CREATE INDEX idx_login_activities_created_at ON public.login_activities(user_id, created_at DESC);

ALTER TABLE public.login_activities ENABLE ROW LEVEL SECURITY;

-- ===========================================
-- 21. PLATFORM SETTINGS
-- ===========================================
-- [CHANGED] updated_by now references public.users (not public.profiles).
CREATE TABLE public.platform_settings (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,
  updated_by TEXT REFERENCES public.users(id) ON DELETE SET NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE public.platform_settings IS 'Admin-configurable platform settings (default credits, fee %, etc.)';

ALTER TABLE public.platform_settings ENABLE ROW LEVEL SECURITY;

-- Default settings
INSERT INTO public.platform_settings (key, value) VALUES
  ('default_credits',              '7'),
  ('platform_fee_percent',         '10'),
  ('min_rationale_words',          '50'),
  ('max_report_flags_before_alert','10'),
  ('min_withdrawal_amount_inr',    '500');
