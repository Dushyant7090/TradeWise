-- TradeWise — Admin Auth/Authorization Hardening
-- Version: 1.0.0
-- Date:    2026-03-31
-- Depends: 20260331_001_tradewise_initial_schema.sql
--
-- Purpose:
--   Adds the admin-specific database layer required for the admin login
--   system and dashboard/moderation tooling.  Kept in a separate migration
--   so the base canonical schema remains uncluttered and this file can be
--   reviewed and rolled back independently.
--
-- Changes made here:
--   1.  Composite index on profiles(role, user_id) for fast admin checks.
--   2.  public.is_admin(uid)           — lightweight RLS helper.
--   3.  public.promote_user_to_admin() — secure bootstrap function.
--   4.  Admin RLS policies on all moderation/ops tables (least-privilege).
--   5.  platform_settings admin-update policy.
--
-- Auth compatibility note:
--   All policies use public.current_user_id() which reads the app.user_id
--   session variable set by trusted server-side middleware.  See the base
--   migration for the full security note on why clients must never be
--   permitted to set app.user_id directly.

BEGIN;

-- ================================================================
-- 1. PERFORMANCE INDEX FOR ADMIN ROLE CHECKS
-- ================================================================
-- Rationale: RLS policies and the is_admin() helper perform
-- role-equality lookups on profiles.  A composite index on (role, user_id)
-- avoids sequential scans on every policy evaluation.
CREATE INDEX IF NOT EXISTS idx_profiles_role_user_id
  ON public.profiles(role, user_id);

-- ================================================================
-- 2. HELPER FUNCTION: is_admin(uid)
-- ================================================================
-- Rationale: Centralises the "is this user an admin?" check so that
-- every policy does not inline the same sub-select.  SECURITY DEFINER
-- with a fixed search_path prevents search-path hijacking.
CREATE OR REPLACE FUNCTION public.is_admin(uid varchar(36))
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1
    FROM public.profiles
    WHERE user_id = uid
      AND role = 'admin'
  );
$$;

COMMENT ON FUNCTION public.is_admin(varchar) IS
  'Returns TRUE if the given user_id belongs to an admin profile. '
  'Used by RLS policies; SECURITY DEFINER to prevent search-path hijacking.';

-- ================================================================
-- 3. SECURE ADMIN BOOTSTRAP FUNCTION: promote_user_to_admin()
-- ================================================================
-- Rationale: Providing a dedicated, locked-down function for the
-- initial admin promotion prevents ad-hoc UPDATE statements on
-- profiles and creates a single auditable bootstrap path.
--
-- Usage (run as database superuser / service role from a trusted
-- server-side context — NOT from a browser client):
--   SELECT public.promote_user_to_admin('founder@yourdomain.com');
--
-- Security controls:
--   • SECURITY DEFINER  — runs with definer's privileges, not caller's.
--   • SET search_path = public  — prevents search-path injection.
--   • REVOKE ALL … FROM PUBLIC  — no one calls this unless explicitly granted.
--   • Grant narrowly to the Supabase service_role (or a dedicated DBA role).

CREATE OR REPLACE FUNCTION public.promote_user_to_admin(target_email text)
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
DECLARE
  v_user_id varchar(36);
BEGIN
  -- Step 1: Locate the user by email (case-insensitive).
  SELECT id::varchar(36)
  INTO   v_user_id
  FROM   public.users
  WHERE  lower(email) = lower(target_email)
  LIMIT  1;

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION
      'promote_user_to_admin: no user found with email ''%''.  '
      'Ensure the user has completed sign-up before promoting.',
      target_email;
  END IF;

  -- Step 2: Upsert the profile row to role=admin, is_verified=true.
  --   INSERT for first-time setup; UPDATE on conflict so re-running is safe.
  INSERT INTO public.profiles (user_id, role, is_verified, created_at, updated_at)
  VALUES (v_user_id, 'admin', true, NOW(), NOW())
  ON CONFLICT (user_id) DO UPDATE
    SET role        = 'admin',
        is_verified = true,
        updated_at  = NOW();

  RAISE NOTICE
    'promote_user_to_admin: user % (%) promoted to admin.',
    target_email, v_user_id;
END;
$$;

COMMENT ON FUNCTION public.promote_user_to_admin(text) IS
  'Controlled bootstrap function: promotes a user to admin by email. '
  'Looks up public.users (case-insensitive), upserts profiles.role=admin. '
  'SECURITY DEFINER — must be called from trusted server-side context only. '
  'Execution is locked down: REVOKE ALL FROM PUBLIC; grant only to service_role.';

-- Lock execution: nobody can call this unless explicitly granted.
REVOKE ALL ON FUNCTION public.promote_user_to_admin(text) FROM PUBLIC;
-- Grant to the Supabase service_role (or your DBA role) for trusted use:
-- GRANT EXECUTE ON FUNCTION public.promote_user_to_admin(text) TO service_role;

-- Optional one-time bootstrap call (uncomment and run from a trusted session):
-- SELECT public.promote_user_to_admin('founder@yourdomain.com');

-- ================================================================
-- 4. ADMIN RLS POLICIES — LEAST PRIVILEGE
-- ================================================================
-- Rationale: Admins need broader read access for dashboard/monitoring
-- and targeted update rights for moderation actions.  These policies
-- are additive — they do NOT weaken any existing owner-scoped policy.
-- Policy names use the "admin_" prefix to avoid clashes with base policies.

-- --- profiles: admin read (KYC dashboard, user management) ---
DROP POLICY IF EXISTS "profiles_admin_select" ON public.profiles;
CREATE POLICY "profiles_admin_select"
  ON public.profiles FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- profiles: admin update (verify users, role changes via bootstrap fn) ---
DROP POLICY IF EXISTS "profiles_admin_update" ON public.profiles;
CREATE POLICY "profiles_admin_update"
  ON public.profiles FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- pro_trader_profiles: admin read (KYC / compliance) ---
DROP POLICY IF EXISTS "pro_trader_profiles_admin_select" ON public.pro_trader_profiles;
CREATE POLICY "pro_trader_profiles_admin_select"
  ON public.pro_trader_profiles FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- learner_profiles: admin read (support / moderation) ---
DROP POLICY IF EXISTS "learner_profiles_admin_select" ON public.learner_profiles;
CREATE POLICY "learner_profiles_admin_select"
  ON public.learner_profiles FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- trades: admin read (monitoring) ---
DROP POLICY IF EXISTS "trades_admin_select" ON public.trades;
CREATE POLICY "trades_admin_select"
  ON public.trades FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- trades: admin update (moderation_status, trade_status lifecycle) ---
DROP POLICY IF EXISTS "trades_admin_update" ON public.trades;
CREATE POLICY "trades_admin_update"
  ON public.trades FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- payments: admin read (financial monitoring) ---
DROP POLICY IF EXISTS "payments_admin_select" ON public.payments;
CREATE POLICY "payments_admin_select"
  ON public.payments FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- payments: admin update (status corrections, refund processing) ---
DROP POLICY IF EXISTS "payments_admin_update" ON public.payments;
CREATE POLICY "payments_admin_update"
  ON public.payments FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- subscriptions: admin read (operations / dispute resolution) ---
DROP POLICY IF EXISTS "subscriptions_admin_select" ON public.subscriptions;
CREATE POLICY "subscriptions_admin_select"
  ON public.subscriptions FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- subscriptions: admin update (cancel/expire for policy violations) ---
DROP POLICY IF EXISTS "subscriptions_admin_update" ON public.subscriptions;
CREATE POLICY "subscriptions_admin_update"
  ON public.subscriptions FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- revenue_splits: admin read (financial reconciliation) ---
DROP POLICY IF EXISTS "revenue_splits_admin_select" ON public.revenue_splits;
CREATE POLICY "revenue_splits_admin_select"
  ON public.revenue_splits FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- revenue_splits: admin update (mark settled after manual payout) ---
DROP POLICY IF EXISTS "revenue_splits_admin_update" ON public.revenue_splits;
CREATE POLICY "revenue_splits_admin_update"
  ON public.revenue_splits FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- payouts: admin read (payout queue monitoring) ---
DROP POLICY IF EXISTS "payouts_admin_select" ON public.payouts;
CREATE POLICY "payouts_admin_select"
  ON public.payouts FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- payouts: admin update (process/fail payouts, add transfer IDs) ---
DROP POLICY IF EXISTS "payouts_admin_update" ON public.payouts;
CREATE POLICY "payouts_admin_update"
  ON public.payouts FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- learner_flags: admin read + update (flag review / verdict) ---
DROP POLICY IF EXISTS "learner_flags_admin_select" ON public.learner_flags;
CREATE POLICY "learner_flags_admin_select"
  ON public.learner_flags FOR SELECT
  USING (public.is_admin(current_user_id()));

DROP POLICY IF EXISTS "learner_flags_admin_update" ON public.learner_flags;
CREATE POLICY "learner_flags_admin_update"
  ON public.learner_flags FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- reports: admin read + update (review / action reports) ---
DROP POLICY IF EXISTS "reports_admin_select" ON public.reports;
CREATE POLICY "reports_admin_select"
  ON public.reports FOR SELECT
  USING (public.is_admin(current_user_id()));

DROP POLICY IF EXISTS "reports_admin_update" ON public.reports;
CREATE POLICY "reports_admin_update"
  ON public.reports FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- comments_threads: admin update (soft-delete / moderation) ---
DROP POLICY IF EXISTS "comments_threads_admin_update" ON public.comments_threads;
CREATE POLICY "comments_threads_admin_update"
  ON public.comments_threads FOR UPDATE
  USING (public.is_admin(current_user_id()));

-- --- notifications: admin read (monitoring system alerts) ---
DROP POLICY IF EXISTS "notifications_admin_select" ON public.notifications;
CREATE POLICY "notifications_admin_select"
  ON public.notifications FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- learner_notifications: admin read (support monitoring) ---
DROP POLICY IF EXISTS "learner_notifications_admin_select" ON public.learner_notifications;
CREATE POLICY "learner_notifications_admin_select"
  ON public.learner_notifications FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- login_activities: admin read (security / fraud monitoring) ---
DROP POLICY IF EXISTS "login_activities_admin_select" ON public.login_activities;
CREATE POLICY "login_activities_admin_select"
  ON public.login_activities FOR SELECT
  USING (public.is_admin(current_user_id()));

-- --- platform_settings: admin update (configuring platform parameters) ---
DROP POLICY IF EXISTS "platform_settings_admin_update" ON public.platform_settings;
CREATE POLICY "platform_settings_admin_update"
  ON public.platform_settings FOR UPDATE
  USING (public.is_admin(current_user_id()));

COMMIT;
