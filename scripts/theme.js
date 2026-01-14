/**
 * Theme Toggle - Nemo Operans
 *
 * Dark mode is DEFAULT. Light mode is the override.
 * Saves preference to localStorage. Respects system preference as secondary.
 */

(function() {
  const STORAGE_KEY = 'nemo-theme';

  // Get the toggle button (may not exist on page load for FOUC script)
  function getToggleButton() {
    return document.getElementById('theme-toggle');
  }

  // Get current theme
  function getCurrentTheme() {
    return document.documentElement.getAttribute('data-theme') || 'dark';
  }

  // Set theme
  function setTheme(theme) {
    if (theme === 'light') {
      document.documentElement.setAttribute('data-theme', 'light');
    } else {
      document.documentElement.removeAttribute('data-theme');
    }
  }

  // Update toggle button icon
  function updateIcon() {
    const toggle = getToggleButton();
    if (!toggle) return;

    const icon = toggle.querySelector('.theme-icon');
    if (!icon) return;

    const currentTheme = getCurrentTheme();
    // Show sun when in dark mode (click to go light)
    // Show moon when in light mode (click to go dark)
    icon.textContent = currentTheme === 'dark' ? '\u2600\uFE0F' : '\uD83C\uDF19';
  }

  // Toggle theme
  function toggleTheme() {
    const currentTheme = getCurrentTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    setTheme(newTheme);
    localStorage.setItem(STORAGE_KEY, newTheme);
    updateIcon();
  }

  // Initialize on DOM ready
  function init() {
    const toggle = getToggleButton();
    if (toggle) {
      toggle.addEventListener('click', toggleTheme);
      updateIcon();
    }
  }

  // Run init when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for external use if needed
  window.NemoTheme = {
    toggle: toggleTheme,
    get: getCurrentTheme,
    set: setTheme
  };
})();
