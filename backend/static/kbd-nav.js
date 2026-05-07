/**
 * initKbdNav — keyboard navigation for search+dropdown combos.
 *
 * @param inputEl      The text input element
 * @param getItems     () => NodeList/Array of selectable item elements
 * @param onActivate   (el) => called when Enter/Space is pressed on a highlighted item
 * @param getDropdown  () => the dropdown container element (for Escape to close), or null
 */
function initKbdNav(inputEl, getItems, onActivate, getDropdown) {
  let idx = -1;

  function items() { return [...getItems()]; }

  function applyHighlight(newIdx) {
    const els = items();
    els.forEach(el => el.classList.remove('kbd-active'));
    idx = Math.max(0, Math.min(newIdx, els.length - 1));
    if (els[idx]) {
      els[idx].classList.add('kbd-active');
      els[idx].scrollIntoView({ block: 'nearest' });
    }
  }

  function clearHighlight() {
    items().forEach(el => el.classList.remove('kbd-active'));
    idx = -1;
  }

  inputEl.addEventListener('keydown', e => {
    const els = items();
    if (!els.length) return;

    if (e.key === 'ArrowDown') {
      e.preventDefault();
      applyHighlight(idx < 0 ? 0 : idx + 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      applyHighlight(idx <= 0 ? 0 : idx - 1);
    } else if ((e.key === 'Enter' || e.key === ' ') && idx >= 0 && els[idx]) {
      e.preventDefault();
      onActivate(els[idx]);
    } else if (e.key === 'Escape') {
      getDropdown?.()?.classList.add('hidden');
      clearHighlight();
    } else {
      clearHighlight(); // reset on any other key (user is typing)
    }
  });

  // Clear when focus leaves (slight delay so mousedown can fire first)
  inputEl.addEventListener('blur', () => setTimeout(clearHighlight, 150));
}
