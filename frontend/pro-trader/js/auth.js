/**
 * auth.js — JWT authentication, login/logout, token management for Pro-Trader
 */

import Storage from './storage.js';
import { authAPI } from './api.js?v=api-host-4';

const Auth = {
  // ===== AUTH STATUS =====
  isAuthenticated() {
    return !!Storage.getToken();
  },

  /**
   * Guard: redirect to login if not authenticated.
   * Call at the top of every protected page.
   */
  requireAuth() {
    if (!this.isAuthenticated()) {
      this.redirectToLogin();
      return false;
    }
    const role = (Storage.getUser()?.role || '').toLowerCase();
    if (role === 'public_trader' || role === 'learner') {
      window.location.href = '/learner/pages/dashboard.html';
      return false;
    }
    return true;
  },

  redirectToLogin() {
    window.location.href = '/pro-trader/pages/register.html';
  },

  redirectToDashboard() {
    window.location.href = '/pro-trader/pages/dashboard.html';
  },

  // ===== LOGIN =====
  async login(email, password) {
    const data = await authAPI.login({ email, password });
    this._storeSession(data);
    return data;
  },

  _storeSession(data) {
    Storage.clearAll();
    if (data.token)         Storage.setToken(data.token);
    if (data.access_token)  Storage.setToken(data.access_token);
    if (data.refresh_token) Storage.setRefreshToken(data.refresh_token);
    const user = {
      ...(data.user || {}),
      ...(data.profile ? {
        role: data.profile.role,
        display_name: data.profile.display_name,
        avatar_url: data.profile.avatar_url,
        profile_id: data.profile.id,
      } : {}),
    };
    if (Object.keys(user).length) Storage.setUser(user);
    if (data.profile?.role === 'pro_trader') Storage.setProProfile(data.profile);
  },

  // ===== REGISTER =====
  async register(email, password, displayName) {
    return authAPI.register({ email, password, display_name: displayName, role: 'pro_trader' });
  },

  // ===== LOGOUT =====
  async logout() {
    try {
      await authAPI.logout();
    } catch {
      // Ignore logout API errors
    } finally {
      Storage.clearAll();
      window.location.href = '/pro-trader/pages/register.html';
    }
  },

  // ===== GET CURRENT USER =====
  getCurrentUser() {
    return Storage.getUser();
  },
};

export default Auth;
