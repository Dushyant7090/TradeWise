(function () {
  var DEFAULT_THEME = 'light';

  function normalizeTheme(value) {
    return value === 'light' || value === 'dark' ? value : '';
  }

  function applyLearnerTheme(theme) {
    var normalized = normalizeTheme(theme) || DEFAULT_THEME;
    document.documentElement.setAttribute('data-theme', normalized);
    localStorage.setItem('theme', normalized);
  }

  try {
    if (window.TradeWiseTheme && typeof window.TradeWiseTheme.initTheme === 'function') {
      window.TradeWiseTheme.initTheme();
    } else {
      applyLearnerTheme(localStorage.getItem('theme'));
    }
    window.addEventListener('storage', function (event) {
      if (event.key === 'theme') {
        applyLearnerTheme(event.newValue);
      }
    });
  } catch (err) {
    document.documentElement.setAttribute('data-theme', DEFAULT_THEME);
  }
})();
