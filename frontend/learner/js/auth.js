/**
 * auth.js — JWT authentication, login/logout, token management for Learner
 */

import Storage from './storage.js';
import { authAPI } from './api.js?v=api-host-3';

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
    if (role === 'pro_trader') {
      window.location.href = '/pro-trader/pages/dashboard.html';
      return false;
    }
    return true;
  },

  redirectToLogin() {
    window.location.href = '/learner/pages/auth.html';
  },

  redirectToDashboard() {
    window.location.href = '/learner/pages/dashboard.html';
  },

  // ===== LOGIN =====
  // Backend response: { token, user: {id, email, role}, profile: {credits, interests, experience_level} }
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
    if (data.profile?.role === 'public_trader' || data.profile?.role === 'learner') {
      Storage.setLearnerProfile(data.profile);
    }
  },

  // ===== REGISTER =====
  // Backend response: { user_id, token, profile: {id, credits: 7, interests: []} }
  async register(email, password) {
    const data = await authAPI.register({ email, password, role: 'public_trader' });
    if (data.token) Storage.setToken(data.token);
    if (data.profile) Storage.setLearnerProfile(data.profile);
    return data;
  },

  // ===== LOGOUT =====
  async logout() {
    try {
      await authAPI.logout();
    } catch {
      // Ignore logout API errors
    } finally {
      Storage.clearAll();
      window.location.href = '/learner/pages/auth.html';
    }
  },

  // ===== CURRENT USER =====
  getCurrentUser() {
    return Storage.getUser();
  },

  getLearnerProfile() {
    return Storage.getLearnerProfile();
  },

  getCredits() {
    const profile = Storage.getLearnerProfile();
    return profile?.credits ?? 0;
  },
};

function initLearnerAuthPage() {
  const loginForm = document.getElementById('login-form');
  const signupForm = document.getElementById('signup-form');
  const forgotForm = document.getElementById('forgot-form');

  // Exit early when this module is imported on non-auth pages.
  if (!loginForm || !signupForm || !forgotForm) return;

  const views = {
    signup: document.getElementById('signup-view'),
    login: document.getElementById('login-view'),
    forgot: document.getElementById('forgot-view'),
  };

  const showView = (name) => {
    Object.values(views).forEach((view) => view?.classList.remove('active'));
    if (name === 'signup') views.signup?.classList.add('active');
    if (name === 'login') views.login?.classList.add('active');
    if (name === 'forgot') views.forgot?.classList.add('active');
  };

  const showMessage = (id, text, type = 'error') => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text || '';
    el.classList.remove('success', 'error', 'show');
    if (text) {
      el.classList.add(type, 'show');
    }
  };

  const setButtonLoading = (buttonId, isLoading) => {
    const button = document.getElementById(buttonId);
    if (!button) return;
    const text = button.querySelector('.btn-text');
    const loader = button.querySelector('.btn-loader');
    button.disabled = isLoading;
    if (text) text.style.display = isLoading ? 'none' : 'inline';
    if (loader) loader.style.display = isLoading ? 'inline-flex' : 'none';
  };

  const initMathCaptcha = ({
    questionId,
    inputId,
    refreshId,
    statusId,
    submitId,
  }) => {
    const question = document.getElementById(questionId);
    const input = document.getElementById(inputId);
    const refresh = document.getElementById(refreshId);
    const status = document.getElementById(statusId);
    const submit = document.getElementById(submitId);
    if (!question || !input || !refresh || !status || !submit) return null;

    let expected = 0;

    const makeChallenge = () => {
      const a = Math.floor(Math.random() * 8) + 3;
      const b = Math.floor(Math.random() * 7) + 2;
      expected = a + b;
      question.textContent = `${a} + ${b} = ?`;
      input.value = '';
      status.textContent = 'Enter answer';
      status.classList.remove('valid');
      submit.disabled = true;
      submit.classList.remove('ready');
    };

    const validate = () => {
      const isValid = Number(input.value.trim()) === expected;
      status.textContent = isValid ? 'Verified' : 'Enter answer';
      status.classList.toggle('valid', isValid);
      submit.disabled = !isValid;
      submit.classList.toggle('ready', isValid);
      return isValid;
    };

    input.addEventListener('input', validate);
    refresh.addEventListener('click', makeChallenge);
    makeChallenge();

    return { validate, reset: makeChallenge };
  };

  const signupCaptcha = initMathCaptcha({
    questionId: 'signup-captcha-question',
    inputId: 'signup-captcha-answer',
    refreshId: 'signup-captcha-refresh',
    statusId: 'signup-captcha-status',
    submitId: 'signup-submit',
  });

  const loginCaptcha = initMathCaptcha({
    questionId: 'login-captcha-question',
    inputId: 'login-captcha-answer',
    refreshId: 'login-captcha-refresh',
    statusId: 'login-captcha-status',
    submitId: 'login-submit',
  });

  document.querySelectorAll('.auth-toggle-link').forEach((link) => {
    link.addEventListener('click', (event) => {
      event.preventDefault();
      const target = link.getAttribute('data-target');
      if (target === 'signup-view') showView('signup');
      if (target === 'login-view') showView('login');
      if (target === 'forgot-view') showView('forgot');
    });
  });

  const forgotLink = document.getElementById('forgot-password-link');
  if (forgotLink) {
    forgotLink.addEventListener('click', (event) => {
      event.preventDefault();
      showView('forgot');
    });
  }

  document.querySelectorAll('.password-toggle').forEach((button) => {
    button.addEventListener('click', () => {
      const targetId = button.getAttribute('data-target');
      const input = targetId ? document.getElementById(targetId) : null;
      if (!input) return;
      const show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      const eye = button.querySelector('.eye-icon');
      const eyeOff = button.querySelector('.eye-off-icon');
      if (eye) eye.style.display = show ? 'none' : 'inline';
      if (eyeOff) eyeOff.style.display = show ? 'inline' : 'none';
    });
  });

  const signupPassword = document.getElementById('signup-password');
  if (signupPassword) {
    signupPassword.addEventListener('input', () => {
      const value = signupPassword.value;
      const fill = document.getElementById('strength-fill');
      const hint = document.getElementById('strength-hint');
      if (!fill || !hint) return;
      let score = 0;
      if (value.length >= 8) score += 1;
      if (/[A-Z]/.test(value)) score += 1;
      if (/[a-z]/.test(value)) score += 1;
      if (/\d/.test(value)) score += 1;
      if (/[^A-Za-z0-9]/.test(value)) score += 1;

      const labels = ['Very weak', 'Weak', 'Fair', 'Good', 'Strong'];
      const widths = ['20%', '40%', '60%', '80%', '100%'];
      const colors = ['#ef4444', '#f97316', '#eab308', '#22c55e', '#10b981'];
      const idx = Math.max(0, Math.min(4, score - 1));

      if (!value) {
        fill.style.width = '0%';
        hint.textContent = '';
      } else {
        fill.style.width = widths[idx];
        fill.style.background = colors[idx];
        hint.textContent = labels[idx];
      }
    });
  }

  const handleRoleRedirect = (user) => {
    const role = (user?.role || '').toLowerCase();
    if (role === 'pro_trader') {
      window.location.href = '/pro-trader/pages/dashboard.html';
      return true;
    }
    if (role && role !== 'public_trader' && role !== 'learner') {
      Storage.clearAll();
      throw new Error('This account cannot use the learner dashboard.');
    }
    return false;
  };

  signupForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    showMessage('signup-message', '');
    if (signupCaptcha && !signupCaptcha.validate()) {
      showMessage('signup-message', 'Complete the security check before creating an account.', 'error');
      return;
    }
    setButtonLoading('signup-submit', true);

    const email = document.getElementById('signup-email')?.value?.trim() || '';
    const password = document.getElementById('signup-password')?.value || '';

    try {
      await Auth.register(email, password);
      await Auth.login(email, password);
      if (handleRoleRedirect(Auth.getCurrentUser())) return;
      window.location.href = '/learner/pages/profile-setup.html';
    } catch (error) {
      showMessage('signup-message', error?.message || 'Signup failed. Please try again.', 'error');
    } finally {
      setButtonLoading('signup-submit', false);
    }
  });

  loginForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    showMessage('login-message', '');
    if (loginCaptcha && !loginCaptcha.validate()) {
      showMessage('login-message', 'Complete the security check before logging in.', 'error');
      return;
    }
    setButtonLoading('login-submit', true);

    const email = document.getElementById('login-email')?.value?.trim() || '';
    const password = document.getElementById('login-password')?.value || '';

    try {
      await Auth.login(email, password);
      if (handleRoleRedirect(Auth.getCurrentUser())) return;
      window.location.href = '/learner/pages/dashboard.html';
    } catch (error) {
      showMessage('login-message', error?.message || 'Login failed. Please check your credentials.', 'error');
    } finally {
      setButtonLoading('login-submit', false);
    }
  });

  forgotForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    showMessage('forgot-message', 'Password reset is not enabled yet. Please contact support.', 'success');
  });

  document.getElementById('google-signup-btn')?.addEventListener('click', () => {
    showMessage('signup-message', 'Google sign-up is not enabled yet.', 'error');
  });
  document.getElementById('google-login-btn')?.addEventListener('click', () => {
    showMessage('login-message', 'Google login is not enabled yet.', 'error');
  });

  // Show login panel by default for returning users.
  showView('login');
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initLearnerAuthPage);
} else {
  initLearnerAuthPage();
}

export default Auth;
