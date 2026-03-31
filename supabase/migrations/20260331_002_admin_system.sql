-- TradeWise — Admin System Migration
-- File:   supabase/migrations/20260331_002_admin_system.sql
-- Requires: 20260331_001_tradewise_schema.sql applied first
--
-- Adds everything needed for a robust, production-safe admin system:
--   1. public.is_admin(uid)            — lightweight role-check helper
--   2. public.promote_to_admin(email)  — secure bootstrap promotion function
--   3. public.admin_audit_log          — immutable admin-action audit table
--   4. Admin RLS policies              — across all moderation-relevant tables
--   5. Partial index on profiles.role  — fast admin lookups
--   6. Explicit REVOKE/GRANT           — no insecure PUBLIC access on privileged fns
--
-- Safety guarantees:
--   • Every DDL statement is idempotent (IF NOT EXISTS / DO…EXCEPTION blocks).
--   • SECURITY DEFINER functions always declare SET search_path = public.
--   • No existing user/trader/learner policies are touched or removed.
-- =============================================================================

BEGIN;

-- ---------------------------------------------------------------------------
-- 1. HELPER: public.is_admin(uid)
--
--    Returns TRUE when the supplied user_id maps to an admin-role profile.
--    Called inside every admin RLS policy USING clause.
--
--    SECURITY DEFINER: runs as function owner so it can read public.profiles
--    without being blocked by any future RLS tightening on that table.
--    STABLE: safe to inline/cache within a single statement.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.is_admin(uid VARCHAR(36))
RETURNS BOOLEAN
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM   public.profiles
    WHERE  user_id = uid
    AND    role    = 'admin'
  );
$$;

COMMENT ON FUNCTION public.is_admin(VARCHAR) IS
  'Returns TRUE when the supplied user_id belongs to an admin-role profile. '
  'SECURITY DEFINER + explicit search_path = public. '
  'Used in RLS USING clauses — must remain GRANT EXECUTE to PUBLIC.';

-- is_admin() is a non-privileged predicate (returns only a boolean).
-- It MUST remain callable by all DB roles because it is invoked during
-- RLS policy evaluation, which runs as the querying user's role.
-- We explicitly re-grant to make the intent clear in future reviews.
REVOKE ALL    ON FUNCTION public.is_admin(VARCHAR) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.is_admin(VARCHAR) TO PUBLIC;


-- ---------------------------------------------------------------------------
-- 2. BOOTSTRAP: public.promote_to_admin(target_email)
--
--    One-shot function to promote an existing active user to admin role.
--    Intended for initial setup or emergency use by a superuser / service-role.
--
--    Security:
--      • SECURITY DEFINER — can upsert profiles bypassing RLS.
--      • REVOKE from PUBLIC / GRANT to service_role only.
--      • Input is normalised (lower + trim) to prevent trivial mismatches.
--      • Rejects inactive (soft-deleted) accounts.
--      • Fully idempotent — safe to run multiple times.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION public.promote_to_admin(target_email TEXT)
RETURNS TEXT
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id      VARCHAR(36);
  v_current_role user_role;
  v_clean_email  TEXT := lower(trim(target_email));
BEGIN
  -- Resolve email → user_id (active accounts only)
  SELECT id
  INTO   v_user_id
  FROM   public.users
  WHERE  email     = v_clean_email
  AND    is_active = TRUE;

  IF v_user_id IS NULL THEN
    RETURN 'ERROR: No active user found for email: ' || v_clean_email;
  END IF;

  -- Read existing profile role for idempotency reporting
  SELECT role
  INTO   v_current_role
  FROM   public.profiles
  WHERE  user_id = v_user_id;

  -- Upsert the profile row to role = admin
  INSERT INTO public.profiles (user_id, role)
  VALUES (v_user_id, 'admin')
  ON CONFLICT (user_id)
  DO UPDATE SET role = 'admin';

  IF v_current_role = 'admin' THEN
    RETURN 'INFO: ' || v_clean_email || ' is already admin — no change made.';
  ELSE
    RETURN 'SUCCESS: ' || v_clean_email
      || ' promoted to admin (previous role: '
      || COALESCE(v_current_role::TEXT, 'no profile')
      || ').';
  END IF;
END;
$$;

COMMENT ON FUNCTION public.promote_to_admin(TEXT) IS
  'Bootstrap: promotes an active user to admin role by email address. '
  'Call as superuser or service_role only. Idempotent — safe to re-run. '
  'Example: SELECT public.promote_to_admin(''admin@example.com'');';

-- This function CAN change roles — restrict to service_role / superuser.
REVOKE ALL    ON FUNCTION public.promote_to_admin(TEXT) FROM PUBLIC;
GRANT  EXECUTE ON FUNCTION public.promote_to_admin(TEXT) TO service_role;


-- ---------------------------------------------------------------------------
-- 3. ADMIN AUDIT LOG
--
--    Immutable record of every admin moderation action.
--    Backend writes one row per admin operation (KYC decision, trade removal,
--    user suspension, flag resolution, payout override, etc.).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS public.admin_audit_log (
  id            VARCHAR(36)   PRIMARY KEY DEFAULT gen_random_uuid()::TEXT,
  -- NULL when the admin account is later deleted; preserves the audit record.
  admin_id      VARCHAR(36)   NULL REFERENCES public.users (id) ON DELETE SET NULL,

  -- What was done
  action        VARCHAR(100)  NOT NULL,    -- e.g. 'kyc_approve', 'trade_delete', 'user_suspend'
  target_table  VARCHAR(100)  NULL,        -- name of the affected table (NULL for platform actions)
  target_id     VARCHAR(36)   NULL,        -- PK of the affected row

  -- Structured context: before/after state, reason, notes, etc.
  details       JSONB         NOT NULL DEFAULT '{}',

  created_at    TIMESTAMPTZ   NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  public.admin_audit_log IS
  'Immutable log of all admin moderation actions; used for accountability and audit trails';
COMMENT ON COLUMN public.admin_audit_log.action       IS
  'Short snake_case action name: kyc_approve | kyc_reject | trade_remove | '
  'user_suspend | user_reactivate | flag_resolve | report_resolve | payout_override | credits_adjust';
COMMENT ON COLUMN public.admin_audit_log.target_table IS
  'PostgreSQL table name of the affected row (nullable for platform-level operations)';
COMMENT ON COLUMN public.admin_audit_log.target_id    IS
  'Primary key value of the affected row (nullable for bulk/platform operations)';
COMMENT ON COLUMN public.admin_audit_log.details      IS
  'Arbitrary JSON with before/after values, free-text reason, or action metadata';
COMMENT ON COLUMN public.admin_audit_log.admin_id     IS
  'Admin who performed the action; SET NULL on admin account deletion to preserve audit history';

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_admin_id
  ON public.admin_audit_log (admin_id);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_created_at
  ON public.admin_audit_log (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_action
  ON public.admin_audit_log (action);

CREATE INDEX IF NOT EXISTS idx_admin_audit_log_target
  ON public.admin_audit_log (target_table, target_id)
  WHERE target_id IS NOT NULL;

ALTER TABLE public.admin_audit_log ENABLE ROW LEVEL SECURITY;

-- Admins can read the full audit log.
DO $$ BEGIN
  CREATE POLICY "admin_audit_log_select_admin"
    ON public.admin_audit_log FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Backend service inserts audit entries on behalf of the admin user.
-- WITH CHECK (TRUE) is intentional: row ownership is recorded in admin_id column.
DO $$ BEGIN
  CREATE POLICY "admin_audit_log_insert_service"
    ON public.admin_audit_log FOR INSERT
    WITH CHECK (TRUE);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ===========================================================================
-- 4. ADMIN RLS POLICIES
--
--    Each policy is wrapped in a DO … EXCEPTION WHEN duplicate_object block
--    so the migration is idempotent and does not error if re-applied.
--
--    Naming convention: <table>_<operation>_admin
--    All existing user/trader/learner policies are left completely untouched.
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- TABLE: users
--    Admin can view all accounts (user management / search).
--    Admin can update any account (toggle is_active for suspension/reactivation).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "users_select_admin"
    ON public.users FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "users_update_admin"
    ON public.users FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: profiles
--    Admin can update any profile (change role, set is_verified after KYC).
--    SELECT is already open to everyone via "profiles_select_all" (USING TRUE).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "profiles_update_admin"
    ON public.profiles FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: pro_trader_profiles
--    Admin can update any record (kyc_status approval/rejection, is_active).
--    SELECT already open via "pro_trader_profiles_select_all" (USING TRUE).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "pro_trader_profiles_update_admin"
    ON public.pro_trader_profiles FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: learner_profiles
--    Admin can read all learner profiles (support, dispute resolution).
--    Admin can update learner profiles (e.g. credits adjustment, account mgmt).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "learner_profiles_select_admin"
    ON public.learner_profiles FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "learner_profiles_update_admin"
    ON public.learner_profiles FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: trades
--    Admin can update any trade (force-close / cancel for rule violations).
--    Admin can delete any trade (content moderation — last-resort removal).
--    SELECT already open via "trades_select_all" (USING TRUE).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "trades_update_admin"
    ON public.trades FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "trades_delete_admin"
    ON public.trades FOR DELETE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: payments
--    Admin can view all payment records (financial oversight, dispute resolution).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "payments_select_admin"
    ON public.payments FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: subscriptions
--    Admin can view all subscriptions (platform health monitoring).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "subscriptions_select_admin"
    ON public.subscriptions FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: revenue_splits
--    Admin can view all revenue splits (financial reporting, reconciliation).
--    Previously comment in schema said "use service-role key" — now has an
--    explicit RLS path for admins authenticated via session variable.
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "revenue_splits_select_admin"
    ON public.revenue_splits FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: payouts
--    Admin can view all payout requests.
--    Admin can update payout status (override failed → retry, reconcile).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "payouts_select_admin"
    ON public.payouts FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "payouts_update_admin"
    ON public.payouts FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: learner_flags
--    Admin can view all flags (moderation queue).
--    Admin can update flags (set status, admin_action, resolved_at).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "learner_flags_select_admin"
    ON public.learner_flags FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "learner_flags_update_admin"
    ON public.learner_flags FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: reports
--    Admin can view all reports (moderation queue).
--    Admin can update reports (set admin_verdict, status, resolved_at).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "reports_select_admin"
    ON public.reports FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "reports_update_admin"
    ON public.reports FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: comments_threads
--    Admin can delete any comment (content moderation, harmful content removal).
--    Admin can update any comment (e.g. redact specific text).
--    SELECT already open via "comments_select_all" (USING TRUE).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "comments_threads_delete_admin"
    ON public.comments_threads FOR DELETE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "comments_threads_update_admin"
    ON public.comments_threads FOR UPDATE
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: login_activities
--    Admin can view all login history (security monitoring, anomaly detection).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "login_activities_select_admin"
    ON public.login_activities FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: learner_credits_log
--    Admin can view all credit log entries (audit trails, dispute resolution).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "learner_credits_log_select_admin"
    ON public.learner_credits_log FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ---------------------------------------------------------------------------
-- TABLE: learner_unlocked_trades
--    Admin can view all unlock records (audit, fraud investigation).
-- ---------------------------------------------------------------------------
DO $$ BEGIN
  CREATE POLICY "learner_unlocked_trades_select_admin"
    ON public.learner_unlocked_trades FOR SELECT
    USING (public.is_admin(public.current_user_id()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ===========================================================================
-- 5. PERFORMANCE INDEX
--
--    A partial index that only covers admin-role rows in profiles.
--    is_admin() will benefit from this: the full idx_profiles_role already
--    exists, but the partial index below is a smaller, faster structure for
--    the common case where we only care about admin rows.
-- ===========================================================================
CREATE INDEX IF NOT EXISTS idx_profiles_role_admin
  ON public.profiles (user_id)
  WHERE role = 'admin';

COMMENT ON INDEX public.idx_profiles_role_admin IS
  'Partial index covering only admin-role profile rows. '
  'Speeds up is_admin() lookups — typically a tiny fraction of all profiles.';


COMMIT;

-- =============================================================================
-- END OF MIGRATION: 20260331_002_admin_system.sql
-- =============================================================================
