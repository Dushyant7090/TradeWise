-- TradeWise - Cashfree Easy Split compatibility schema
-- Adds the columns/tables needed by Supabase Edge Function payment flow.

BEGIN;

ALTER TABLE public.profiles
  ADD COLUMN IF NOT EXISTS full_name TEXT NULL,
  ADD COLUMN IF NOT EXISTS cashfree_vendor_id TEXT NULL,
  ADD COLUMN IF NOT EXISTS accuracy_pct NUMERIC(5, 2) NULL,
  ADD COLUMN IF NOT EXISTS credits INTEGER NULL;

COMMENT ON COLUMN public.profiles.cashfree_vendor_id IS
  'Cashfree Easy Split vendor ID for pro-trader settlement. Existing deployments may also store this as pro_trader_profiles.cf_seller_id.';

ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS mentor_id VARCHAR(36) NULL,
  ADD COLUMN IF NOT EXISTS start_date TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS end_date TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS amount_paid NUMERIC(12, 2) NULL,
  ADD COLUMN IF NOT EXISTS cashfree_order_id VARCHAR(100) NULL;

UPDATE public.subscriptions
SET mentor_id = COALESCE(mentor_id, trader_id),
    start_date = COALESCE(start_date, started_at),
    end_date = COALESCE(end_date, ends_at)
WHERE mentor_id IS NULL
   OR start_date IS NULL
   OR end_date IS NULL;

DO $$ BEGIN
  ALTER TABLE public.subscriptions
    ADD CONSTRAINT uq_subscriptions_cashfree_order_id UNIQUE (cashfree_order_id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE INDEX IF NOT EXISTS idx_subscriptions_mentor_id
  ON public.subscriptions (mentor_id);

CREATE TABLE IF NOT EXISTS public.transactions (
  id                  VARCHAR(36) PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  order_id            VARCHAR(100) NOT NULL,
  payment_id          VARCHAR(100) NULL,
  amount              NUMERIC(12, 2) NOT NULL,
  status              TEXT NOT NULL DEFAULT 'PENDING',
  subscriber_id       VARCHAR(36) NOT NULL,
  mentor_id           VARCHAR(36) NOT NULL,
  split_admin_amount  NUMERIC(12, 2) NOT NULL DEFAULT 0,
  split_mentor_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
  raw_event           JSONB NULL,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_transactions_order_id UNIQUE (order_id),
  CONSTRAINT chk_transactions_amount_positive CHECK (amount > 0),
  CONSTRAINT chk_transactions_split_non_negative CHECK (
    split_admin_amount >= 0 AND split_mentor_amount >= 0
  )
);

COMMENT ON TABLE public.transactions IS
  'Cashfree order/payment ledger for Edge Function subscription payments. order_id is unique for webhook idempotency.';

CREATE INDEX IF NOT EXISTS idx_transactions_subscriber_id
  ON public.transactions (subscriber_id);

CREATE INDEX IF NOT EXISTS idx_transactions_mentor_id
  ON public.transactions (mentor_id);

CREATE INDEX IF NOT EXISTS idx_transactions_status
  ON public.transactions (status);

ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;

DO $$ BEGIN
  CREATE POLICY "transactions_select_own_or_admin"
    ON public.transactions FOR SELECT
    USING (
      subscriber_id = public.current_user_id()
      OR mentor_id = public.current_user_id()
      OR public.is_admin(public.current_user_id())
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Writes are intentionally performed by service-role Edge Functions only.

COMMIT;
