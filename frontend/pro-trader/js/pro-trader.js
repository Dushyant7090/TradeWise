/**
 * pro-trader.js — Pro Trader module utilities
 *
 * Shared helpers used across pro-trader pages.
 * Relies on window.TW_API_BASE_URL and window.tw_jwt_token
 * (or localStorage key 'tw_jwt_token').
 */

'use strict';

// ===== AUTH HELPERS =====

const ProTraderAuth = {
  getToken() {
    return localStorage.getItem('tw_jwt_token');
  },

  isAuthenticated() {
    return !!this.getToken();
  },

  /** Redirect to login if not authenticated. Returns false if redirected. */
  requireAuth() {
    if (!this.isAuthenticated()) {
      // Relative path from pro-trader/pages/ — works regardless of deploy sub-path
      window.location.href = '../../learner/pages/register.html';
      return false;
    }
    return true;
  },

  logout() {
    localStorage.removeItem('tw_jwt_token');
    localStorage.removeItem('tw_refresh_token');
    window.location.href = '../../index.html';
  },
};

// ===== API FETCH HELPER =====

async function proTraderFetch(path, options = {}) {
  const base = window.TW_API_BASE_URL || 'http://localhost:5000/api';
  const token = ProTraderAuth.getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  const res = await fetch(`${base}${path}`, { ...options, headers });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ message: res.statusText }));
    throw new Error(err.message || `HTTP ${res.status}`);
  }
  return res.json();
}

// ===== TOAST SYSTEM =====

const Toast = {
  _icons: {
    success: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"/></svg>',
    error:   '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>',
    info:    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    warning: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>',
  },
  show(msg, type = 'info', duration = 5000) {
    const container = document.getElementById('toast-container');
    if (!container) return;
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.innerHTML = `<div class="toast-icon">${this._icons[type] || this._icons.info}</div><div class="toast-content"><div class="toast-message">${msg}</div></div><button class="toast-dismiss" aria-label="Dismiss">×</button>`;
    container.appendChild(t);
    requestAnimationFrame(() => t.classList.add('show'));
    const dismiss = () => { t.classList.remove('show'); setTimeout(() => t.remove(), 350); };
    t.querySelector('.toast-dismiss').addEventListener('click', dismiss);
    setTimeout(dismiss, duration);
  },
};

// ===== SIDEBAR TOGGLE =====

function initSidebar() {
  const hamburger = document.getElementById('hamburger');
  const sidebar   = document.getElementById('sidebar');
  const overlay   = document.getElementById('sidebar-overlay');
  if (!hamburger || !sidebar) return;
  hamburger.addEventListener('click', () => {
    sidebar.classList.toggle('open');
    overlay && overlay.classList.toggle('active');
    hamburger.setAttribute('aria-expanded', sidebar.classList.contains('open'));
  });
  overlay && overlay.addEventListener('click', () => {
    sidebar.classList.remove('open');
    overlay.classList.remove('active');
    hamburger.setAttribute('aria-expanded', 'false');
  });
}

// ===== LOGOUT BUTTON =====

function initLogout() {
  const btn = document.getElementById('logout-btn');
  btn && btn.addEventListener('click', () => ProTraderAuth.logout());
}

// ===== FORMATTERS =====

function formatCurrency(value, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency, maximumFractionDigits: 2 }).format(value ?? 0);
}

function formatPercent(value) {
  const v = parseFloat(value) || 0;
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%';
}

function timeAgo(dateStr) {
  if (!dateStr) return '—';
  const diff = Date.now() - new Date(dateStr).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1)  return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

// ===== DOM-READY INIT =====

document.addEventListener('DOMContentLoaded', () => {
  initSidebar();
  initLogout();
});

// Export for use in page scripts (works without a bundler via globals)
window.ProTraderAuth  = ProTraderAuth;
window.proTraderFetch = proTraderFetch;
window.Toast          = Toast;
window.formatCurrency = formatCurrency;
window.formatPercent  = formatPercent;
window.timeAgo        = timeAgo;
