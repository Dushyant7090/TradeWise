-- TradeWise — Pro-Trader Onboarding & Verification-Gated Trading
-- Migration: 20260421_005_onboarding_verification.sql
-- Requires: 20260331_001, 20260331_002 applied first
--
-- Adds:
--   1. onboarding_step, is_review_pending, cf_seller_id to pro_trader_profiles
--   2. subscription_plans table (stores pricing in paise)
--   3. Backfills existing pro-trader data to correct states
--   4. Updates trades INSERT RLS to require is_verified = true
--
-- Safety: All statements are idempotent (IF NOT EXISTS / ADD COLUMN IF NOT EXISTS).
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. ADD COLUMNS TO pro_trader_profiles
--    Single source of truth for onboarding state.
-- ---------------------------------------------------------------------------

-- onboarding_step: 0=new, 1=profile done (EXPLORER), 2=financial done, 3=pricing done
ALTER TABLE public.pro_trader_profiles
  ADD COLUMN IF NOT EXISTS onboarding_step INTEGER NOT NULL DEFAULT 0;

-- is_review_pending: true when user has submitted all steps for admin review
ALTER TABLE public.pro_trader_profiles
  ADD COLUMN IF NOT EXISTS is_review_pending BOOLEAN NOT NULL DEFAULT FALSE;

-- cf_seller_id: Cashfree vendor/seller ID from financial setup
ALTER TABLE public.pro_trader_profiles
  ADD COLUMN IF NOT EXISTS cf_seller_id TEXT NULL;

COMMENT ON COLUMN public.pro_trader_profiles.onboarding_step IS
  '0=new, 1=profile complete (EXPLORER), 2=financial setup done, 3=pricing/storefront done';
COMMENT ON COLUMN public.pro_trader_profiles.is_review_pending IS
  'TRUE after user completes all onboarding steps + KYC docs and submits for admin review (PENDING state)';
COMMENT ON COLUMN public.pro_trader_profiles.cf_seller_id IS
  'Cashfree vendor/seller ID created during onboarding Step 2 (financial setup)';

-- Partial index for efficient admin queries on pending reviews
CREATE INDEX IF NOT EXISTS idx_pro_trader_profiles_review_pending
  ON public.pro_trader_profiles (is_review_pending)
  WHERE is_review_pending = TRUE;


-- ---------------------------------------------------------------------------
-- 2. SUBSCRIPTION PLANS TABLE
--    Stores pricing in paise (integer) to avoid floating-point errors.
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.subscription_plans (
  id               VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  trader_id        VARCHAR(36)   NOT NULL REFERENCES public.users (id) ON DELETE CASCADE,

  plan_name        VARCHAR(100)  NOT NULL DEFAULT '1 Month',
  duration_months  INTEGER       NOT NULL DEFAULT 1,
  price_paise      BIGINT        NOT NULL DEFAULT 0,     -- INR price in paise (integer)
  is_active        BOOLEAN       NOT NULL DEFAULT TRUE,

  created_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
  updated_at       TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

  CONSTRAINT chk_subscription_plans_price_non_negative CHECK (price_paise >= 0),
  CONSTRAINT chk_subscription_plans_duration_positive  CHECK (duration_months > 0)
);

COMMENT ON TABLE  public.subscription_plans IS
  'Pro-trader subscription plan pricing; amounts stored in paise (1 INR = 100 paise) to avoid floating-point errors';
COMMENT ON COLUMN public.subscription_plans.price_paise IS
  'Subscription price in paise. Example: ₹499 = 49900 paise';

CREATE INDEX IF NOT EXISTS idx_subscription_plans_trader_id
  ON public.subscription_plans (trader_id);

CREATE INDEX IF NOT EXISTS idx_subscription_plans_active
  ON public.subscription_plans (trader_id, is_active)
  WHERE is_active = TRUE;

ALTER TABLE public.subscription_plans ENABLE ROW LEVEL SECURITY;

-- RLS: anyone can read plans (learner discovery), only owner can write
DO $$ BEGIN
  CREATE POLICY "subscription_plans_select_all"
    ON public.subscription_plans FOR SELECT
    USING (TRUE);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "subscription_plans_insert_own"
    ON public.subscription_plans FOR INSERT
    WITH CHECK (trader_id = public.current_user_id());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "subscription_plans_update_own"
    ON public.subscription_plans FOR UPDATE
    USING (trader_id = public.current_user_id());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "subscription_plans_delete_own"
    ON public.subscription_plans FOR DELETE
    USING (trader_id = public.current_user_id());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Admin can manage all plans
DO $$ BEGIN
  CREATE POLICY "subscription_plans_select_admin"
    ON public.subscription_plans FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "subscription_plans_update_admin"
    ON public.subscription_plans FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- 3. BACKFILL EXISTING DATA
--    Migrate existing pro-traders to the new state model.
--    - Verified traders (profiles.is_verified = true) → onboarding_step=3
--    - Unverified traders with existing profile rows → onboarding_step=1
--    - Others → remain at default 0
-- ---------------------------------------------------------------------------

-- Verified pro-traders: fully onboarded
UPDATE public.pro_trader_profiles ptp
SET    onboarding_step = 3,
       is_review_pending = FALSE
FROM   public.profiles p
WHERE  ptp.user_id = p.user_id
AND    p.is_verified = TRUE
AND    p.role = 'pro_trader'
AND    ptp.onboarding_step = 0;

-- Unverified pro-traders who have a bio OR have uploaded KYC docs: at least step 1
UPDATE public.pro_trader_profiles ptp
SET    onboarding_step = 1
FROM   public.profiles p
WHERE  ptp.user_id = p.user_id
AND    p.is_verified = FALSE
AND    p.role = 'pro_trader'
AND    ptp.onboarding_step = 0
AND    (ptp.bio IS NOT NULL OR (ptp.kyc_documents IS NOT NULL AND ptp.kyc_documents::TEXT <> '{}'));


-- ---------------------------------------------------------------------------
-- 4. UPDATE TRADES INSERT RLS POLICY
--    Only verified pro-traders can insert trades.
--    The existing policy "trades_insert_own" only checks role = pro_trader.
--    We replace it to also require is_verified = true on the profile.
-- ---------------------------------------------------------------------------

-- Drop the old permissive insert policy
DROP POLICY IF EXISTS "trades_insert_own" ON public.trades;

-- Create stricter policy requiring verification
CREATE POLICY "trades_insert_verified_only"
  ON public.trades FOR INSERT
  WITH CHECK (
    trader_id = public.current_user_id()
    AND EXISTS (
      SELECT 1 FROM public.profiles p
      WHERE p.user_id = public.current_user_id()
      AND p.role = 'pro_trader'
      AND p.is_verified = TRUE
    )
  );


COMMIT;

-- =============================================================================
-- END OF MIGRATION: 20260421_005_onboarding_verification.sql
-- =============================================================================
