/* =====================================================
   pro-trader.js — Pro Trader Dashboard Logic
   Auth guard, fetch helper, toast notifications,
   and shared formatters for the Pro Trader section.
   ===================================================== */

'use strict';

/* ===== CONFIG ===== */
const API_BASE = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:5000/api'
  : '/api';

const TOKEN_KEY = 'tw_jwt_token';
const USER_KEY  = 'tw_user';

/* ===== AUTH GUARD ===== */
function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function requireAuth() {
  if (!getToken()) {
    window.location.replace('../../pro-trader/pages/register.html');
  }
}

function logout() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.location.replace('../../pro-trader/pages/register.html');
}

/* ===== FETCH HELPER ===== */
async function apiRequest(path, options = {}) {
  const token = getToken();
  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  if (res.status === 401) { logout(); return null; }
  return res;
}

/* ===== TOAST NOTIFICATIONS ===== */
function showToast(message, type = 'info') {
  const existing = document.getElementById('pt-toast');
  if (existing) existing.remove();

  const toast = document.createElement('div');
  toast.id = 'pt-toast';
  toast.textContent = message;
  Object.assign(toast.style, {
    position: 'fixed',
    bottom: '24px',
    right: '24px',
    padding: '12px 20px',
    borderRadius: '10px',
    color: '#fff',
    fontWeight: '600',
    fontSize: '0.9rem',
    zIndex: '9999',
    background: type === 'error' ? '#EF4444'
              : type === 'success' ? '#10B981'
              : '#3B82F6',
    boxShadow: '0 4px 20px rgba(0,0,0,0.3)',
    transition: 'opacity 0.3s',
  });
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 3500);
}

/* ===== FORMATTERS ===== */
function formatCurrency(value, currency = 'INR') {
  return new Intl.NumberFormat('en-IN', { style: 'currency', currency }).format(value ?? 0);
}

function formatPercent(value, decimals = 1) {
  const num = parseFloat(value ?? 0);
  const sign = num >= 0 ? '+' : '';
  return `${sign}${num.toFixed(decimals)}%`;
}

function formatDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatDateTime(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-IN', {
    day: '2-digit', month: 'short', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
}

/* ===== INIT ===== */
document.addEventListener('DOMContentLoaded', () => {
  requireAuth();
});
