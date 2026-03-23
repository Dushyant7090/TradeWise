-- ===========================================
-- RLS POLICIES FOR TRADEWISE
-- Applied to Supabase project: jzzazbmufhjaaivlbidk
-- ===========================================

-- ===== PROFILES =====
CREATE POLICY "profiles_select_all" ON public.profiles FOR SELECT USING (true);
CREATE POLICY "profiles_update_own" ON public.profiles FOR UPDATE USING (auth.uid() = id);
CREATE POLICY "profiles_insert_own" ON public.profiles FOR INSERT WITH CHECK (auth.uid() = id);

-- ===== TRADES =====
CREATE POLICY "trades_select_all" ON public.trades FOR SELECT USING (true);
CREATE POLICY "trades_insert_mentor" ON public.trades FOR INSERT WITH CHECK (
  auth.uid() = mentor_id AND EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'pro_trader')
);
CREATE POLICY "trades_update_mentor" ON public.trades FOR UPDATE USING (auth.uid() = mentor_id);

-- ===== MENTOR STATS =====
CREATE POLICY "mentor_stats_select_all" ON public.mentor_stats FOR SELECT USING (true);
CREATE POLICY "mentor_stats_insert" ON public.mentor_stats FOR INSERT WITH CHECK (auth.uid() = mentor_id);
CREATE POLICY "mentor_stats_update" ON public.mentor_stats FOR UPDATE USING (auth.uid() = mentor_id);

-- ===== UNLOCKED TRADES =====
CREATE POLICY "unlocked_trades_select_own" ON public.unlocked_trades FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "unlocked_trades_insert_own" ON public.unlocked_trades FOR INSERT WITH CHECK (auth.uid() = user_id);

-- ===== SUBSCRIPTION PLANS =====
CREATE POLICY "subscription_plans_select_all" ON public.subscription_plans FOR SELECT USING (true);
CREATE POLICY "subscription_plans_insert_mentor" ON public.subscription_plans FOR INSERT WITH CHECK (auth.uid() = mentor_id);
CREATE POLICY "subscription_plans_update_mentor" ON public.subscription_plans FOR UPDATE USING (auth.uid() = mentor_id);

-- ===== SUBSCRIPTIONS =====
CREATE POLICY "subscriptions_select_own" ON public.subscriptions FOR SELECT USING (auth.uid() = public_trader_id OR auth.uid() = mentor_id);
CREATE POLICY "subscriptions_insert_learner" ON public.subscriptions FOR INSERT WITH CHECK (auth.uid() = public_trader_id);

-- ===== REPORTS =====
CREATE POLICY "reports_select_own" ON public.reports FOR SELECT USING (auth.uid() = reporter_id);
CREATE POLICY "reports_select_admin" ON public.reports FOR SELECT USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));
CREATE POLICY "reports_insert_auth" ON public.reports FOR INSERT WITH CHECK (auth.uid() = reporter_id);
CREATE POLICY "reports_update_admin" ON public.reports FOR UPDATE USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));

-- ===== COMMENTS =====
CREATE POLICY "comments_select_all" ON public.comments FOR SELECT USING (true);
CREATE POLICY "comments_insert_auth" ON public.comments FOR INSERT WITH CHECK (auth.uid() = user_id);
CREATE POLICY "comments_delete_own" ON public.comments FOR DELETE USING (auth.uid() = user_id);

-- ===== NOTIFICATIONS =====
CREATE POLICY "notifications_select_own" ON public.notifications FOR SELECT USING (auth.uid() = user_id);
CREATE POLICY "notifications_update_own" ON public.notifications FOR UPDATE USING (auth.uid() = user_id);
CREATE POLICY "notifications_insert" ON public.notifications FOR INSERT WITH CHECK (true);

-- ===== WALLET =====
CREATE POLICY "wallet_select_own" ON public.wallet FOR SELECT USING (auth.uid() = mentor_id);
CREATE POLICY "wallet_insert_own" ON public.wallet FOR INSERT WITH CHECK (auth.uid() = mentor_id);
CREATE POLICY "wallet_update_own" ON public.wallet FOR UPDATE USING (auth.uid() = mentor_id);

-- ===== TRANSACTIONS =====
CREATE POLICY "transactions_select_own" ON public.transactions FOR SELECT USING (auth.uid() = mentor_id);
CREATE POLICY "transactions_insert" ON public.transactions FOR INSERT WITH CHECK (true);

-- ===== PLATFORM SETTINGS =====
CREATE POLICY "platform_settings_select_all" ON public.platform_settings FOR SELECT USING (true);
CREATE POLICY "platform_settings_update_admin" ON public.platform_settings FOR UPDATE USING (EXISTS (SELECT 1 FROM public.profiles WHERE id = auth.uid() AND role = 'admin'));
