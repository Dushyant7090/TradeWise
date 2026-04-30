-- Additional performance indexes for high-frequency query patterns.
-- Safe to re-run: all use IF NOT EXISTS.

-- Notifications: every page load queries (user_id, is_read) + ORDER BY created_at DESC
CREATE INDEX IF NOT EXISTS idx_notifications_user_read_created
  ON public.notifications (user_id, is_read, created_at DESC);

-- Learner notifications: same pattern
CREATE INDEX IF NOT EXISTS idx_learner_notifications_user_read_created
  ON public.learner_notifications (learner_id, is_read, created_at DESC);

-- Learner unlocked trades: access checks in feed (learner_id, trade_id)
CREATE INDEX IF NOT EXISTS idx_learner_unlocked_trades_learner_trade
  ON public.learner_unlocked_trades (learner_id, trade_id);

-- Comments: trade detail page loads comments sorted by created_at
CREATE INDEX IF NOT EXISTS idx_comments_trade_created
  ON public.comments (trade_id, created_at DESC);

-- Revenue splits: earnings/analytics joins on (trader_id, payment_id)
CREATE INDEX IF NOT EXISTS idx_revenue_splits_trader_payment
  ON public.revenue_splits (trader_id, payment_id);

-- Trades: closed_at used for analytics charts and trade history ordering
CREATE INDEX IF NOT EXISTS idx_trades_trader_closed_at
  ON public.trades (trader_id, closed_at DESC);

-- Pro trader profiles: user_id lookups (may exist via FK but ensure index)
CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_user_id
  ON public.pro_trader_profiles (user_id);

-- Profiles: user_id lookups
CREATE INDEX IF NOT EXISTS idx_profiles_user_id
  ON public.profiles (user_id);
