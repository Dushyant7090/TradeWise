-- ===========================================
-- RLS POLICIES FOR TRADEWISE (Corrected & Complete)
-- Updated: 2026-03-24
--
-- NOTES:
--  • The Flask backend accesses Supabase using SUPABASE_SERVICE_KEY, which
--    bypasses RLS entirely. These policies protect direct client-side access.
--  • auth.uid() maps to the Supabase Auth session; for backend-only tables
--    (users, login_activities, etc.) policies default to service-role only.
--  • All tables have RLS enabled in schema.sql — no policy = no access for
--    non-service clients (safe default).
--
-- CHANGELOG vs previous rls-policies.sql:
--  [CHANGED] profiles: policies updated for new user_id column (was id)
--  [NEW]     pro_trader_profiles: select public / update own
--  [NEW]     learner_profiles: select own / update own
--  [CHANGED] trades: column renamed trader_id (was mentor_id); status values updated
--  [REMOVED] mentor_stats policies (table removed)
--  [RENAMED] unlocked_trades → learner_unlocked_trades policies
--  [REMOVED] subscription_plans policies (table removed)
--  [CHANGED] subscriptions: column renamed subscriber_id (was public_trader_id),
--             trader_id (was mentor_id)
--  [NEW]     payments: select own (subscriber or trader)
--  [NEW]     payouts: select own (trader)
--  [NEW]     revenue_splits: select own (trader)
--  [CHANGED] reports: updated column names (reporter_id already correct)
--  [RENAMED] comments → comments_threads policies
--  [CHANGED] notifications: user_id already correct; insert now service-only
--  [NEW]     learner_notifications: select own / insert service-only
--  [NEW]     notification_preferences: select/update own
--  [NEW]     learner_notification_preferences: select/update own
--  [NEW]     learner_trade_ratings: select all / insert own
--  [NEW]     learner_credits_log: select own
--  [NEW]     learner_flags: select own / insert own
--  [NEW]     login_activities: select own
--  [REMOVED] wallet policies (table removed)
--  [REMOVED] transactions policies (table removed)
--  [CHANGED] platform_settings: insert restricted to admin
-- ===========================================

-- ===== USERS =====
-- The users table is managed exclusively by the Flask backend via service role.
-- No direct client read/write is permitted.
CREATE POLICY "users_no_direct_access" ON public.users FOR ALL USING (FALSE);

-- ===== PROFILES =====
-- Anyone can read profiles (public discovery of traders).
-- Users can only update or insert their own profile row.
CREATE POLICY "profiles_select_all"  ON public.profiles FOR SELECT USING (TRUE);
CREATE POLICY "profiles_insert_own"  ON public.profiles FOR INSERT WITH CHECK (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "profiles_update_own"  ON public.profiles FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== PRO TRADER PROFILES =====
-- Public read (for discovery / learner feed); only the owner may update.
-- Inserts are handled by the backend service role on registration.
CREATE POLICY "pro_trader_profiles_select_all" ON public.pro_trader_profiles FOR SELECT USING (TRUE);
CREATE POLICY "pro_trader_profiles_update_own" ON public.pro_trader_profiles FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== LEARNER PROFILES =====
-- Learners may only read and update their own profile.
CREATE POLICY "learner_profiles_select_own" ON public.learner_profiles FOR SELECT USING (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "learner_profiles_update_own" ON public.learner_profiles FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== TRADES =====
-- All users can browse trade signals (required for the public feed).
-- Only the owning pro trader may create, update, or delete their own trades.
CREATE POLICY "trades_select_all"     ON public.trades FOR SELECT USING (TRUE);
CREATE POLICY "trades_insert_own"     ON public.trades FOR INSERT WITH CHECK (
  auth.uid()::TEXT = trader_id
  AND EXISTS (
    SELECT 1 FROM public.profiles
    WHERE user_id = auth.uid()::TEXT AND role = 'pro_trader'
  )
);
CREATE POLICY "trades_update_own"     ON public.trades FOR UPDATE USING (
  auth.uid()::TEXT = trader_id
);
CREATE POLICY "trades_delete_own"     ON public.trades FOR DELETE USING (
  auth.uid()::TEXT = trader_id
);

-- ===== LEARNER UNLOCKED TRADES =====
-- Learners can only see and insert their own unlocks.
CREATE POLICY "learner_unlocked_select_own" ON public.learner_unlocked_trades FOR SELECT USING (
  auth.uid()::TEXT = learner_id
);
CREATE POLICY "learner_unlocked_insert_own" ON public.learner_unlocked_trades FOR INSERT WITH CHECK (
  auth.uid()::TEXT = learner_id
);

-- ===== PAYMENTS =====
-- Payments visible to the subscriber or the receiving trader.
-- Inserts are handled by the backend service role only.
CREATE POLICY "payments_select_own" ON public.payments FOR SELECT USING (
  auth.uid()::TEXT = subscriber_id OR auth.uid()::TEXT = trader_id
);

-- ===== SUBSCRIPTIONS =====
-- Subscriptions visible to both the subscriber and the trader.
-- Backend service role handles inserts and status updates.
CREATE POLICY "subscriptions_select_own" ON public.subscriptions FOR SELECT USING (
  auth.uid()::TEXT = subscriber_id OR auth.uid()::TEXT = trader_id
);

-- ===== PAYOUTS =====
-- Only the owning trader may view their payout history.
CREATE POLICY "payouts_select_own" ON public.payouts FOR SELECT USING (
  auth.uid()::TEXT = trader_id
);

-- ===== REVENUE SPLITS =====
-- Only the owning trader may view their revenue split records.
CREATE POLICY "revenue_splits_select_own" ON public.revenue_splits FOR SELECT USING (
  auth.uid()::TEXT = trader_id
);

-- ===== REPORTS =====
-- Reporters see their own reports; admins see all reports.
CREATE POLICY "reports_select_own"    ON public.reports FOR SELECT USING (
  auth.uid()::TEXT = reporter_id
);
CREATE POLICY "reports_select_admin"  ON public.reports FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);
CREATE POLICY "reports_insert_auth"   ON public.reports FOR INSERT WITH CHECK (
  auth.uid()::TEXT = reporter_id
);
CREATE POLICY "reports_update_admin"  ON public.reports FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);

-- ===== COMMENTS THREADS =====
-- All comments are publicly readable (trade discussion is open).
-- Authenticated users may post; users may delete their own comments.
CREATE POLICY "comments_threads_select_all"  ON public.comments_threads FOR SELECT USING (TRUE);
CREATE POLICY "comments_threads_insert_auth" ON public.comments_threads FOR INSERT WITH CHECK (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "comments_threads_delete_own"  ON public.comments_threads FOR DELETE USING (
  auth.uid()::TEXT = user_id
);

-- ===== NOTIFICATIONS =====
-- Users see only their own notifications.
-- Inserts are performed by the backend service role only (no direct client insert).
CREATE POLICY "notifications_select_own"  ON public.notifications FOR SELECT USING (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "notifications_update_own"  ON public.notifications FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== LEARNER NOTIFICATIONS =====
-- Learners see only their own notifications.
-- Inserts are performed by the backend service role only.
CREATE POLICY "learner_notifications_select_own" ON public.learner_notifications FOR SELECT USING (
  auth.uid()::TEXT = learner_id
);
CREATE POLICY "learner_notifications_update_own" ON public.learner_notifications FOR UPDATE USING (
  auth.uid()::TEXT = learner_id
);

-- ===== NOTIFICATION PREFERENCES =====
-- Users can read and update only their own preferences.
CREATE POLICY "notif_prefs_select_own" ON public.notification_preferences FOR SELECT USING (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "notif_prefs_update_own" ON public.notification_preferences FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== LEARNER NOTIFICATION PREFERENCES =====
-- Learners can read and update only their own preferences.
CREATE POLICY "learner_notif_prefs_select_own" ON public.learner_notification_preferences FOR SELECT USING (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "learner_notif_prefs_update_own" ON public.learner_notification_preferences FOR UPDATE USING (
  auth.uid()::TEXT = user_id
);

-- ===== LEARNER TRADE RATINGS =====
-- Ratings are publicly readable (encourages transparency).
-- Learners may only insert (and update) their own rating for a given trade.
CREATE POLICY "trade_ratings_select_all"  ON public.learner_trade_ratings FOR SELECT USING (TRUE);
CREATE POLICY "trade_ratings_insert_own"  ON public.learner_trade_ratings FOR INSERT WITH CHECK (
  auth.uid()::TEXT = learner_id
);
CREATE POLICY "trade_ratings_update_own"  ON public.learner_trade_ratings FOR UPDATE USING (
  auth.uid()::TEXT = learner_id
);

-- ===== LEARNER CREDITS LOG =====
-- Learners see only their own credit history.
CREATE POLICY "credits_log_select_own" ON public.learner_credits_log FOR SELECT USING (
  auth.uid()::TEXT = learner_id
);

-- ===== LEARNER FLAGS =====
-- Learners see only their own flags; admins see all.
CREATE POLICY "learner_flags_select_own"   ON public.learner_flags FOR SELECT USING (
  auth.uid()::TEXT = learner_id
);
CREATE POLICY "learner_flags_select_admin" ON public.learner_flags FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);
CREATE POLICY "learner_flags_insert_own"   ON public.learner_flags FOR INSERT WITH CHECK (
  auth.uid()::TEXT = learner_id
);
CREATE POLICY "learner_flags_update_admin" ON public.learner_flags FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);

-- ===== LOGIN ACTIVITIES =====
-- Users can view their own login history; admins can view all.
CREATE POLICY "login_activities_select_own"   ON public.login_activities FOR SELECT USING (
  auth.uid()::TEXT = user_id
);
CREATE POLICY "login_activities_select_admin" ON public.login_activities FOR SELECT USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);

-- ===== PLATFORM SETTINGS =====
-- All authenticated users can read platform settings (e.g. default credits).
-- Only admins may insert or update settings.
CREATE POLICY "platform_settings_select_all"    ON public.platform_settings FOR SELECT USING (TRUE);
CREATE POLICY "platform_settings_insert_admin"  ON public.platform_settings FOR INSERT WITH CHECK (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);
CREATE POLICY "platform_settings_update_admin"  ON public.platform_settings FOR UPDATE USING (
  EXISTS (SELECT 1 FROM public.profiles WHERE user_id = auth.uid()::TEXT AND role = 'admin')
);
