const THEME_KEY = 'theme';
const DEFAULT_THEME = 'light';

function normalizeTheme(value) {
  return value === 'light' || value === 'dark' ? value : DEFAULT_THEME;
}

export function getSavedProTheme() {
  try {
    if (window.TradeWiseTheme?.getSavedTheme) return window.TradeWiseTheme.getSavedTheme();
    return normalizeTheme(localStorage.getItem(THEME_KEY));
  } catch (err) {
    return DEFAULT_THEME;
  }
}

export function getCurrentProTheme() {
  return normalizeTheme(document.documentElement.getAttribute('data-theme'));
}

export function applyProTheme(theme, options = {}) {
  const normalized = normalizeTheme(theme);
  if (window.TradeWiseTheme?.applyTheme) {
    window.TradeWiseTheme.applyTheme(normalized, { persist: !options.skipPersist });
  } else {
    document.documentElement.setAttribute('data-app', 'pro-trader');
    document.documentElement.setAttribute('data-theme', normalized);

    if (!options.skipPersist) {
      try {
        localStorage.setItem(THEME_KEY, normalized);
      } catch (err) {
        // Ignore storage issues.
      }
    }
  }

  window.dispatchEvent(new CustomEvent('tw:pro-theme-changed', { detail: { theme: normalized } }));
  return normalized;
}

export function initProTheme() {
  return applyProTheme(getSavedProTheme(), { skipPersist: true });
}

export function getProThemeToggleLabel(theme = getCurrentProTheme()) {
  return theme === 'light' ? 'Switch to Dark Mode' : 'Switch to Light Mode';
}

export function bindProThemeToggle(button) {
  if (!button) return;

  const updateButton = () => {
    const current = getCurrentProTheme();
    const label = getProThemeToggleLabel(current);
    button.textContent = label;
    button.title = label;
    button.setAttribute('aria-label', label);
    button.setAttribute('aria-pressed', current === 'dark' ? 'true' : 'false');
    button.dataset.themeState = current;
  };

  button.addEventListener('click', () => {
    if (window.TradeWiseTheme?.toggleTheme) {
      window.TradeWiseTheme.toggleTheme();
    } else {
      const next = getCurrentProTheme() === 'light' ? 'dark' : 'light';
      applyProTheme(next);
    }
    updateButton();
  });

  window.addEventListener('tw:pro-theme-changed', updateButton);
  window.addEventListener('tw:theme-changed', updateButton);
  updateButton();
}
