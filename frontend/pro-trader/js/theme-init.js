(function () {
  var DEFAULT_THEME = 'light';

  function normalizeTheme(value) {
    return value === 'light' || value === 'dark' ? value : '';
  }

  try {
    var themeApi = window.TradeWiseTheme;
    var savedTheme = normalizeTheme(localStorage.getItem('theme')) || DEFAULT_THEME;
    document.documentElement.setAttribute('data-app', 'pro-trader');
    if (themeApi && typeof themeApi.initTheme === 'function') {
      themeApi.initTheme();
    } else {
      document.documentElement.setAttribute('data-theme', savedTheme);
      localStorage.setItem('theme', savedTheme);
    }
  } catch (err) {
    document.documentElement.setAttribute('data-app', 'pro-trader');
    document.documentElement.setAttribute('data-theme', DEFAULT_THEME);
  }
})();
