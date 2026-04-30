(function () {
  'use strict';

  var API_BASE_KEY = 'tw_api_base_url';
  function isLocalHost(hostname) {
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1';
  }

  function normalizeApiBaseUrl(value) {
    if (!value || typeof value !== 'string') return '';
    return value.replace(/\/$/, '');
  }

  function isLoopbackApiBaseUrl(value) {
    return /^https?:\/\/(localhost|127\.0\.0\.1|\[?::1\]?):5000\/api$/i.test(value);
  }

  function isStaleLocalApiBaseUrl(value) {
    return /^https?:\/\/10\.25\.183\.119:5000\/api$/i.test(value);
  }

  function getDefaultApiBaseUrl() {
    var hostname = window.location.hostname;
    var backendHost = isLocalHost(hostname) ? 'localhost' : hostname;
    return 'http://' + backendHost + ':5000/api';
  }

  function setResolvedApiBaseUrl(value) {
    window.TW_API_BASE_URL = normalizeApiBaseUrl(value);
    try {
      localStorage.setItem(API_BASE_KEY, window.TW_API_BASE_URL);
    } catch (err) {
      // Ignore storage errors in private mode.
    }
  }

  function getStoredApiBaseUrl() {
    try {
      return normalizeApiBaseUrl(localStorage.getItem(API_BASE_KEY));
    } catch (err) {
      return '';
    }
  }

  if (window.TW_API_BASE_URL) {
    var configured = normalizeApiBaseUrl(window.TW_API_BASE_URL);
    setResolvedApiBaseUrl((isLoopbackApiBaseUrl(configured) || isStaleLocalApiBaseUrl(configured)) ? getDefaultApiBaseUrl() : configured);
    return;
  }

  var stored = getStoredApiBaseUrl();
  if (stored) {
    setResolvedApiBaseUrl((isLoopbackApiBaseUrl(stored) || isStaleLocalApiBaseUrl(stored)) ? getDefaultApiBaseUrl() : stored);
    return;
  }

  setResolvedApiBaseUrl(getDefaultApiBaseUrl());
})();
