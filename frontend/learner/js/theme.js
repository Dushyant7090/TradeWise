const THEME_KEY = 'theme';
const DEFAULT_THEME = 'light';

function normalizeTheme(value) {
  return value === 'light' || value === 'dark' ? value : DEFAULT_THEME;
}

export function getSavedTheme() {
  try {
    if (window.TradeWiseTheme?.getSavedTheme) return window.TradeWiseTheme.getSavedTheme();
    return normalizeTheme(localStorage.getItem(THEME_KEY));
  } catch (err) {
    return DEFAULT_THEME;
  }
}

export function getCurrentTheme() {
  return normalizeTheme(document.documentElement.getAttribute('data-theme'));
}

export function applyTheme(theme, options = {}) {
  const normalized = normalizeTheme(theme);
  if (window.TradeWiseTheme?.applyTheme) {
    window.TradeWiseTheme.applyTheme(normalized, { persist: !options.skipPersist });
  } else {
    document.documentElement.setAttribute('data-theme', normalized);

    if (!options.skipPersist) {
      try {
        localStorage.setItem(THEME_KEY, normalized);
      } catch (err) {
        // Ignore storage errors in private mode.
      }
    }
  }

  window.dispatchEvent(new CustomEvent('tw:learner-theme-changed', { detail: { theme: normalized } }));
  return normalized;
}

export function initLearnerTheme() {
  return applyTheme(getSavedTheme(), { skipPersist: true });
}

export function getThemeToggleLabel(theme = getCurrentTheme()) {
  return theme === 'light' ? 'Switch to Dark' : 'Switch to Light';
}

export function bindThemeToggle(button) {
  if (!button) return;

  const updateButton = () => {
    const label = getThemeToggleLabel();
    button.textContent = label;
    button.title = label;
    button.setAttribute('aria-label', label);
  };

  button.addEventListener('click', () => {
    if (window.TradeWiseTheme?.toggleTheme) {
      window.TradeWiseTheme.toggleTheme();
    } else {
      const next = getCurrentTheme() === 'light' ? 'dark' : 'light';
      applyTheme(next);
    }
    updateButton();
  });

  window.addEventListener('tw:learner-theme-changed', updateButton);
  window.addEventListener('tw:theme-changed', updateButton);
  updateButton();
}
