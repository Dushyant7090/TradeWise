-- TradeWise — ROLLBACK for 20260421_005_onboarding_verification.sql
-- Run this to UNDO the migration and restore the previous state.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 4. RESTORE ORIGINAL TRADES INSERT RLS POLICY
--    Remove the verified-only policy and re-create the original one.
-- ---------------------------------------------------------------------------

DROP POLICY IF EXISTS "trades_insert_verified_only" ON public.trades;

CREATE POLICY "trades_insert_own"
  ON public.trades FOR INSERT
  WITH CHECK (trader_id = public.current_user_id());


-- ---------------------------------------------------------------------------
-- 3. No need to "un-backfill" — the columns will be dropped in step 1.
--    Old data in onboarding_step/is_review_pending just disappears.
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 2. DROP SUBSCRIPTION PLANS TABLE (and all RLS policies with it)
-- ---------------------------------------------------------------------------

DROP TABLE IF EXISTS public.subscription_plans CASCADE;


-- ---------------------------------------------------------------------------
-- 1. REMOVE ADDED COLUMNS FROM pro_trader_profiles
-- ---------------------------------------------------------------------------

-- Drop the index first
DROP INDEX IF EXISTS idx_pro_trader_profiles_review_pending;

-- Drop columns
ALTER TABLE public.pro_trader_profiles
  DROP COLUMN IF EXISTS onboarding_step;

ALTER TABLE public.pro_trader_profiles
  DROP COLUMN IF EXISTS is_review_pending;

ALTER TABLE public.pro_trader_profiles
  DROP COLUMN IF EXISTS cf_seller_id;


COMMIT;

-- =============================================================================
-- END OF ROLLBACK
-- =============================================================================
