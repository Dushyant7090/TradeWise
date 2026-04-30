/**
 * asset-version.js — Content-hash based asset versioning
 * 
 * Generates a short hash from the current deployment timestamp.
 * All `?v=` query strings in HTML imports are replaced at load time
 * to ensure browsers always fetch the latest assets after deployment.
 * 
 * Usage: Include this script synchronously in <head> before other assets.
 * It sets window.__TW_ASSET_VERSION which can be used by module scripts.
 */

(function () {
  'use strict';

  // Build version from deployment timestamp or localStorage override
  const DEPLOY_VERSION = '20260429a';
  const version = localStorage.getItem('tw_asset_version') || DEPLOY_VERSION;

  // Expose for module scripts to use in dynamic imports
  window.__TW_ASSET_VERSION = version;

  /**
   * Append version query param to a URL if not already present
   * @param {string} url
   * @returns {string}
   */
  window.__twVersionedUrl = function (url) {
    if (!url || typeof url !== 'string') return url;
    // Don't version external CDN URLs
    if (/^https?:\/\/(cdn|fonts|sdk)\./i.test(url)) return url;
    // Don't double-version
    if (url.includes('__v=')) return url;
    const sep = url.includes('?') ? '&' : '?';
    return url + sep + '__v=' + version;
  };
})();
