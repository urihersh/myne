// dark mode (shared by all pages)
(function () {
  function applyDark(dark) {
    document.documentElement.classList.toggle('dark', dark);
    const moon = document.getElementById('dark-icon-moon');
    const sun  = document.getElementById('dark-icon-sun');
    if (moon) moon.classList.toggle('hidden', dark);
    if (sun)  sun.classList.toggle('hidden', !dark);
  }

  window.toggleDark = function () {
    const dark = !document.documentElement.classList.contains('dark');
    localStorage.setItem('myne_dark', dark ? '1' : '');
    applyDark(dark);
  };

  // Apply immediately so there's no flash
  applyDark(!!localStorage.getItem('myne_dark'));
})();
