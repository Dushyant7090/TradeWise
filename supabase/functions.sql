-- =============================================================
-- TradeWise Database Functions & Triggers
-- Supabase Project: jzzazbmufhjaaivlbidk
-- Note: all monetary amounts (prices, balances) are stored in
--       paise (smallest INR unit). 100 paise = ₹1.
-- =============================================================

-- ===========================================
-- HELPER VIEW: active subscriptions
-- Centralises the "subscription is currently active" predicate
-- used by several notification triggers below.
-- ===========================================
CREATE OR REPLACE VIEW public.active_subscriptions AS
  SELECT *
  FROM public.subscriptions
  WHERE status   = 'active'
    AND end_date > NOW();

-- ===========================================
-- 1. AUTO-CREATE MENTOR_STATS & WALLET ON PRO TRADER PROFILE INSERT/UPDATE
-- ===========================================
CREATE OR REPLACE FUNCTION public.handle_new_pro_trader()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.mentor_stats (mentor_id)
  VALUES (NEW.id)
  ON CONFLICT (mentor_id) DO NOTHING;

  INSERT INTO public.wallet (mentor_id)
  VALUES (NEW.id)
  ON CONFLICT (mentor_id) DO NOTHING;

  RETURN NEW;
END;
$$;

-- Fires when a new profile is created with role = 'pro_trader'
CREATE TRIGGER on_pro_trader_profile_created
  AFTER INSERT ON public.profiles
  FOR EACH ROW
  WHEN (NEW.role = 'pro_trader')
  EXECUTE FUNCTION public.handle_new_pro_trader();

-- Fires when an existing profile is promoted to 'pro_trader'
CREATE TRIGGER on_pro_trader_role_updated
  AFTER UPDATE OF role ON public.profiles
  FOR EACH ROW
  WHEN (NEW.role = 'pro_trader' AND OLD.role IS DISTINCT FROM 'pro_trader')
  EXECUTE FUNCTION public.handle_new_pro_trader();

-- ===========================================
-- 2. RECALCULATE MENTOR_STATS WHEN A TRADE IS CLOSED
-- ===========================================
CREATE OR REPLACE FUNCTION public.update_mentor_stats_on_trade_close()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_total    INTEGER;
  v_wins     INTEGER;
  v_losses   INTEGER;
  v_accuracy DECIMAL;
  v_avg_rrr  DECIMAL;
BEGIN
  IF NEW.trade_status IN ('WIN', 'LOSS') AND OLD.trade_status = 'ACTIVE' THEN
    SELECT
      COUNT(*)           FILTER (WHERE trade_status IN ('WIN', 'LOSS')),
      COUNT(*)           FILTER (WHERE trade_status = 'WIN'),
      COUNT(*)           FILTER (WHERE trade_status = 'LOSS'),
      COALESCE(AVG(risk_reward_ratio) FILTER (WHERE trade_status IN ('WIN', 'LOSS')), 0)
    INTO v_total, v_wins, v_losses, v_avg_rrr
    FROM public.trades
    WHERE mentor_id = NEW.mentor_id;

    v_accuracy := CASE
      WHEN v_total > 0 THEN ROUND((v_wins::DECIMAL / v_total) * 100, 2)
      ELSE 0
    END;

    INSERT INTO public.mentor_stats
      (mentor_id, total_trades, winning_trades, losing_trades, accuracy_pct, avg_risk_reward)
    VALUES
      (NEW.mentor_id, v_total, v_wins, v_losses, v_accuracy, v_avg_rrr)
    ON CONFLICT (mentor_id) DO UPDATE SET
      total_trades    = EXCLUDED.total_trades,
      winning_trades  = EXCLUDED.winning_trades,
      losing_trades   = EXCLUDED.losing_trades,
      accuracy_pct    = EXCLUDED.accuracy_pct,
      avg_risk_reward = EXCLUDED.avg_risk_reward;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_trade_closed
  AFTER UPDATE OF trade_status ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.update_mentor_stats_on_trade_close();

-- ===========================================
-- 3. DEDUCT 1 CREDIT WHEN A PUBLIC TRADER UNLOCKS A TRADE
-- ===========================================
CREATE OR REPLACE FUNCTION public.deduct_credit_on_unlock()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.profiles
  SET credits = GREATEST(credits - 1, 0)
  WHERE id = NEW.user_id;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_trade_unlocked
  AFTER INSERT ON public.unlocked_trades
  FOR EACH ROW
  EXECUTE FUNCTION public.deduct_credit_on_unlock();

-- ===========================================
-- 4. NOTIFY ACTIVE SUBSCRIBERS WHEN A NEW TRADE IS POSTED
-- ===========================================
CREATE OR REPLACE FUNCTION public.notify_subscribers_on_new_trade()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.notifications (user_id, type, title, message, link)
  SELECT
    s.public_trader_id,
    'new_trade',
    'New Trade Signal',
    'A new ' || NEW.direction || ' signal for ' || NEW.symbol || ' has been posted.',
    '/trade/' || NEW.id
  FROM public.active_subscriptions s
  WHERE s.mentor_id = NEW.mentor_id;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_new_trade_posted
  AFTER INSERT ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_subscribers_on_new_trade();

-- ===========================================
-- 5. NOTIFY ACTIVE SUBSCRIBERS WHEN A TRADE IS CLOSED
-- ===========================================
CREATE OR REPLACE FUNCTION public.notify_subscribers_on_trade_close()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  IF NEW.trade_status IN ('WIN', 'LOSS') AND OLD.trade_status = 'ACTIVE' THEN
    INSERT INTO public.notifications (user_id, type, title, message, link)
    SELECT
      s.public_trader_id,
      'trade_closed',
      'Trade Closed: ' || NEW.trade_status,
      NEW.symbol || ' trade has been closed as a ' || NEW.trade_status || '.',
      '/trade/' || NEW.id
    FROM public.active_subscriptions s
    WHERE s.mentor_id = NEW.mentor_id;
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_trade_status_changed
  AFTER UPDATE OF trade_status ON public.trades
  FOR EACH ROW
  EXECUTE FUNCTION public.notify_subscribers_on_trade_close();

-- ===========================================
-- 6. CREDIT MENTOR WALLET ON NEW SUBSCRIPTION (90 / 10 REVENUE SPLIT)
-- ===========================================
CREATE OR REPLACE FUNCTION public.credit_wallet_on_subscription()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_plan_price       INTEGER;
  v_platform_fee_pct INTEGER;
  v_mentor_share     INTEGER;
BEGIN
  SELECT price INTO v_plan_price
  FROM public.subscription_plans
  WHERE id = NEW.plan_id;

  SELECT COALESCE(value::INTEGER, 10) INTO v_platform_fee_pct
  FROM public.platform_settings
  WHERE key = 'platform_fee_percent';

  -- Mentor receives (100 - platform_fee_percent) % of the plan price
  v_mentor_share := ROUND(v_plan_price * (100 - v_platform_fee_pct) / 100.0);

  INSERT INTO public.wallet (mentor_id, total_earnings, available_balance, pending_balance)
  VALUES (NEW.mentor_id, v_mentor_share, v_mentor_share, 0)
  ON CONFLICT (mentor_id) DO UPDATE SET
    total_earnings    = public.wallet.total_earnings    + EXCLUDED.total_earnings,
    available_balance = public.wallet.available_balance + EXCLUDED.available_balance;

  INSERT INTO public.transactions (mentor_id, amount, type, cashfree_transfer_id, description)
  VALUES (
    NEW.mentor_id,
    v_mentor_share,
    'earning',
    NEW.cashfree_payment_id,
    'Subscription earning (plan id: ' || NEW.plan_id || ')'
  );

  -- Notify the mentor; v_mentor_share is in paise, divide by 100 to show rupees
  INSERT INTO public.notifications (user_id, type, title, message, link)
  VALUES (
    NEW.mentor_id,
    'subscription',
    'New Subscriber',
    'You have a new subscriber! ₹' || (v_mentor_share / 100) || ' has been credited to your wallet.',
    '/earnings'
  );

  RETURN NEW;
END;
$$;

CREATE TRIGGER on_new_subscription
  AFTER INSERT ON public.subscriptions
  FOR EACH ROW
  EXECUTE FUNCTION public.credit_wallet_on_subscription();

-- ===========================================
-- 7. UTILITY: EXPIRE PAST-DUE SUBSCRIPTIONS
-- Schedule with pg_cron:
--   SELECT cron.schedule('expire-subscriptions', '0 * * * *', 'SELECT public.expire_subscriptions()');
-- ===========================================
CREATE OR REPLACE FUNCTION public.expire_subscriptions()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  UPDATE public.subscriptions
  SET status = 'expired'
  WHERE status = 'active'
    AND end_date <= NOW();
END;
$$;
