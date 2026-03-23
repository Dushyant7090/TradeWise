/**
 * utils.js — Helpers, formatters, and validators
 */

// ===== FORMATTERS =====

/**
 * Format currency in Indian Rupees
 * @param {number} amount
 * @returns {string} e.g. "₹1,23,456.78"
 */
export function formatCurrency(amount) {
  if (amount == null || isNaN(amount)) return '₹0.00';
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Format a number with commas
 */
export function formatNumber(n) {
  if (n == null || isNaN(n)) return '0';
  return new Intl.NumberFormat('en-IN').format(n);
}

/**
 * Format a percentage
 */
export function formatPercent(value, decimals = 1) {
  if (value == null || isNaN(value)) return '0%';
  return `${Number(value).toFixed(decimals)}%`;
}

/**
 * Format a date/time as relative (e.g. "2 hours ago")
 */
export function timeAgo(dateStr) {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  const now = new Date();
  const diffMs = now - date;
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHr = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHr / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin} min ago`;
  if (diffHr < 24) return `${diffHr} hour${diffHr !== 1 ? 's' : ''} ago`;
  if (diffDay < 7) return `${diffDay} day${diffDay !== 1 ? 's' : ''} ago`;
  return formatDate(dateStr);
}

/**
 * Format date as "Jan 15, 2025"
 */
export function formatDate(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

/**
 * Format date with time
 */
export function formatDateTime(dateStr) {
  if (!dateStr) return '';
  return new Date(dateStr).toLocaleString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

/**
 * Format price with decimal places
 */
export function formatPrice(price) {
  if (price == null || isNaN(price)) return '—';
  return Number(price).toFixed(2);
}

/**
 * Mask bank account number: show only last 4 digits
 */
export function maskAccountNumber(num) {
  if (!num) return '';
  const str = String(num);
  return '*'.repeat(Math.max(0, str.length - 4)) + str.slice(-4);
}

// ===== VALIDATORS =====

export function validateEmail(email) {
  if (!email) return 'Email is required.';
  const re = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
  if (!re.test(email)) return 'Please enter a valid email address.';
  return '';
}

export function validatePassword(password) {
  if (!password) return 'Password is required.';
  if (password.length < 8) return 'Password must be at least 8 characters.';
  return '';
}

export function validateRequired(value, fieldName = 'This field') {
  if (!value || String(value).trim() === '') return `${fieldName} is required.`;
  return '';
}

export function validatePositiveNumber(value, fieldName = 'Value') {
  if (!value || isNaN(value)) return `${fieldName} is required.`;
  if (Number(value) <= 0) return `${fieldName} must be greater than 0.`;
  return '';
}

export function validateURL(url) {
  if (!url) return '';
  try {
    new URL(url);
    return '';
  } catch {
    return 'Please enter a valid URL (including http:// or https://).';
  }
}

export function validateIFSC(code) {
  if (!code) return 'IFSC code is required.';
  // Format: 4 uppercase bank code letters + '0' + 6 alphanumeric branch code chars
  const re = /^[A-Z]{4}0[A-Z0-9]{6}$/;
  if (!re.test(code.toUpperCase())) return 'Invalid IFSC code format (e.g. SBIN0012345).';
  return '';
}

export function validateFileSize(file, maxMB = 5) {
  if (!file) return '';
  const maxBytes = maxMB * 1024 * 1024;
  if (file.size > maxBytes) return `File size must be under ${maxMB}MB.`;
  return '';
}

export function validateFileType(file, allowedTypes = ['image/jpeg', 'image/png', 'image/gif']) {
  if (!file) return '';
  if (!allowedTypes.includes(file.type)) {
    return `Allowed formats: ${allowedTypes.map(t => t.split('/')[1].toUpperCase()).join(', ')}.`;
  }
  return '';
}

// ===== RRR CALCULATION =====
export function calculateRRR(direction, entry, stopLoss, target) {
  const e = parseFloat(entry);
  const sl = parseFloat(stopLoss);
  const tp = parseFloat(target);
  if (isNaN(e) || isNaN(sl) || isNaN(tp)) return null;
  if (e === sl) return null;

  const risk = Math.abs(e - sl);
  const reward = Math.abs(tp - e);
  if (risk === 0) return null;

  return parseFloat((reward / risk).toFixed(2));
}

// ===== WORD COUNT =====
export function wordCount(text) {
  if (!text || !text.trim()) return 0;
  return text.trim().split(/\s+/).length;
}

// ===== DOM HELPERS =====
export function $(selector, parent = document) {
  return parent.querySelector(selector);
}

export function $$(selector, parent = document) {
  return Array.from(parent.querySelectorAll(selector));
}

export function setHTML(selector, html, parent = document) {
  const el = $(selector, parent);
  if (el) el.innerHTML = html;
}

export function setText(selector, text, parent = document) {
  const el = $(selector, parent);
  if (el) el.textContent = text;
}

export function showEl(el) {
  if (typeof el === 'string') el = $(el);
  if (el) el.classList.remove('hidden');
}

export function hideEl(el) {
  if (typeof el === 'string') el = $(el);
  if (el) el.classList.add('hidden');
}

export function toggleEl(el, show) {
  if (show) showEl(el);
  else hideEl(el);
}

/**
 * Debounce a function
 */
export function debounce(fn, delay = 300) {
  let timer;
  return function (...args) {
    clearTimeout(timer);
    timer = setTimeout(() => fn.apply(this, args), delay);
  };
}

/**
 * Get initials from a name
 */
export function getInitials(name) {
  if (!name) return 'U';
  return name
    .split(' ')
    .slice(0, 2)
    .map(w => w[0])
    .join('')
    .toUpperCase();
}

/**
 * Capitalize first letter
 */
export function capitalize(str) {
  if (!str) return '';
  return str.charAt(0).toUpperCase() + str.slice(1).replace(/_/g, ' ');
}

/**
 * Get a CSS variable value
 */
export function getCSSVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/**
 * Safe JSON parse
 */
export function safeJSONParse(str, fallback = null) {
  try {
    return JSON.parse(str);
  } catch {
    return fallback;
  }
}
