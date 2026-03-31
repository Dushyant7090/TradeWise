// TODO: Move VALID_KEY to environment variable (e.g. via build-time injection) before production deployment.
(function () {
  'use strict';

  var VALID_KEY = 'TW_ADM_2024_X9K';

  // Hide the entire document immediately to prevent any content or style flash.
  document.documentElement.style.visibility = 'hidden';

  var params = new URLSearchParams(window.location.search);
  var supplied = params.get('key');

  if (supplied !== VALID_KEY) {
    // Wrong or missing key — silently redirect to 404, never reveal this path.
    window.location.replace('/frontend/404.html');
    return; // visibility stays hidden; navigation will complete
  }

  // Key is valid — strip it from the address bar without triggering a page reload.
  params.delete('key');
  var clean = window.location.pathname +
    (params.toString() ? '?' + params.toString() : '') +
    window.location.hash;
  history.replaceState(null, '', clean);

  // Restore visibility now that the key has been removed from the URL.
  document.documentElement.style.visibility = '';
})();
