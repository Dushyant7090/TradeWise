/**
 * Global TradeWise theme persistence for the multi-page frontend.
 * This script is intentionally non-module so it can run in <head> before paint.
 */
(function (window, document) {
  'use strict';

  var THEME_KEY = 'theme';
  var DEFAULT_THEME = 'light';

  function normalizeTheme(value) {
    return value === 'dark' || value === 'light' ? value : '';
  }

  function readStorage(key) {
    try {
      return localStorage.getItem(key);
    } catch (err) {
      return null;
    }
  }

  function writeStorage(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (err) {
      // The current document still gets the theme even when storage is blocked.
    }
  }

  function detectApp() {
    var path = window.location.pathname;
    if (path.indexOf('/pro-trader/') !== -1) return 'pro-trader';
    if (path.indexOf('/learner/') !== -1) return 'learner';
    if (path.indexOf('/admin/') !== -1 || path.indexOf('/secure-access/') !== -1) return 'admin';
    return '';
  }

  function getSavedTheme() {
    var savedTheme = normalizeTheme(readStorage(THEME_KEY));
    return savedTheme || DEFAULT_THEME;
  }

  function applyTheme(theme, options) {
    var normalized = normalizeTheme(theme) || DEFAULT_THEME;
    var app = detectApp();

    document.documentElement.setAttribute('data-theme', normalized);
    if (app) {
      document.documentElement.setAttribute('data-app', app);
    }

    if (!options || options.persist !== false) {
      writeStorage(THEME_KEY, normalized);
    }

    window.dispatchEvent(new CustomEvent('tw:theme-changed', { detail: { theme: normalized } }));
    return normalized;
  }

  function initTheme() {
    return applyTheme(getSavedTheme());
  }

  function toggleTheme() {
    var current = normalizeTheme(readStorage(THEME_KEY)) ||
      normalizeTheme(document.documentElement.getAttribute('data-theme')) ||
      DEFAULT_THEME;
    var next = current === 'light' ? 'dark' : 'light';
    return applyTheme(next);
  }

  window.TradeWiseTheme = {
    key: THEME_KEY,
    defaultTheme: DEFAULT_THEME,
    getSavedTheme: getSavedTheme,
    applyTheme: applyTheme,
    initTheme: initTheme,
    toggleTheme: toggleTheme
  };
  window.initTheme = initTheme;
  window.toggleTheme = toggleTheme;

  initTheme();

  document.addEventListener('DOMContentLoaded', initTheme);
  window.addEventListener('storage', function (event) {
    if (event.key === THEME_KEY) {
      applyTheme(event.newValue || DEFAULT_THEME, { persist: false });
    }
  });
})(window, document);
