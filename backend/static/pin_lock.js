// PIN lock overlay — included on every protected page.
// Auth is server-side: the backend sets an httpOnly session cookie on correct PIN.
// On successful PIN entry the page is reloaded so all data fetches run authenticated.

// ── 401 interceptor ──────────────────────────────────────────────────────────
// If a session expires while the user is on the page, re-show the overlay.
(function () {
  const _orig = window.fetch;
  window.fetch = async function (...args) {
    const res = await _orig.apply(this, args);
    if (res.status === 401) {
      const url = typeof args[0] === 'string' ? args[0] : (args[0]?.url || '');
      if (!url.includes('/api/auth/')) window.__ptShowPin?.();
    }
    return res;
  };
})();

// ── Overlay ───────────────────────────────────────────────────────────────────
async function __ptBoot() {
  let status;
  try {
    const r = await fetch('/api/auth/status');
    status = await r.json();
  } catch (_) { return; }

  if (!status.pin_enabled || status.authenticated) return;
  window.__ptShowPin();
}

window.__ptShowPin = function () {
  if (document.getElementById('pin-overlay')) return;

  const overlay = document.createElement('div');
  overlay.id = 'pin-overlay';
  overlay.style.cssText = [
    'position:fixed', 'inset:0', 'z-index:9999',
    'background:rgba(15,23,42,0.97)',
    'display:flex', 'flex-direction:column',
    'align-items:center', 'justify-content:center',
    'font-family:Inter,system-ui,sans-serif',
  ].join(';');

  overlay.innerHTML = `
    <div style="text-align:center;max-width:320px;width:100%;padding:0 24px">
      <div style="width:56px;height:56px;border-radius:16px;background:#059669;display:flex;align-items:center;justify-content:center;margin:0 auto 20px">
        <svg width="28" height="28" fill="none" viewBox="0 0 24 24" stroke="white" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
          <path stroke-linecap="round" stroke-linejoin="round" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
        </svg>
      </div>
      <p style="color:#f8fafc;font-size:20px;font-weight:700;margin:0 0 6px">Myne</p>
      <p style="color:#94a3b8;font-size:14px;margin:0 0 28px">Enter your PIN to continue</p>
      <div id="pin-dots" style="display:flex;justify-content:center;gap:12px;margin-bottom:24px">
        ${Array(6).fill('<span class="dot" style="width:14px;height:14px;border-radius:50%;background:#334155;transition:background .15s"></span>').join('')}
      </div>
      <p id="pin-error" style="color:#f87171;font-size:13px;min-height:18px;margin:0 0 16px;opacity:0;transition:opacity .2s"></p>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:10px">
        ${[1,2,3,4,5,6,7,8,9,'',0,'⌫'].map(k => `
          <button data-key="${k}" style="
            padding:16px 0;border-radius:14px;border:none;cursor:${k===''?'default':'pointer'};
            background:${k===''?'transparent':'#1e293b'};color:#f8fafc;font-size:20px;font-weight:600;
            transition:background .1s;${k===''?'pointer-events:none':''}
          " ${k===''?'disabled':''} onmouseover="if(this.dataset.key!=='')this.style.background='#334155'" onmouseout="if(this.dataset.key!=='')this.style.background='#1e293b'">${k}</button>
        `).join('')}
      </div>
    </div>
  `;

  document.body.appendChild(overlay);

  let pin = '';
  let locked = false;
  const dots = overlay.querySelectorAll('.dot');
  const errorEl = overlay.querySelector('#pin-error');

  function updateDots() {
    dots.forEach((d, i) => { d.style.background = i < pin.length ? '#0d9488' : '#334155'; });
  }

  function shake() {
    overlay.querySelector('div').animate(
      [{ transform: 'translateX(-8px)' }, { transform: 'translateX(8px)' },
       { transform: 'translateX(-6px)' }, { transform: 'translateX(6px)' },
       { transform: 'translateX(0)' }],
      { duration: 350, easing: 'ease-out' }
    );
  }

  function showError(msg, durationMs = 2500) {
    errorEl.textContent = msg;
    errorEl.style.opacity = '1';
    setTimeout(() => { errorEl.style.opacity = '0'; }, durationMs);
  }

  function startLockoutCountdown(seconds) {
    locked = true;
    let remaining = seconds;
    const tick = () => {
      showError(`Too many attempts — try again in ${remaining}s`, 1200);
      if (remaining-- > 0) setTimeout(tick, 1000);
      else locked = false;
    };
    tick();
  }

  async function submitPin() {
    if (locked) return;
    try {
      const r = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pin }),
      });
      if (r.status === 429) {
        const d = await r.json();
        shake();
        pin = ''; updateDots();
        startLockoutCountdown(d.retry_after ?? 60);
        return;
      }
      const d = await r.json();
      if (d.ok) {
        // Cookie is now set by the server — reload so all page data fetches run authenticated
        window.location.reload();
      } else {
        shake();
        const msg = d.remaining === 0
          ? 'Too many attempts — locked for 60s'
          : `Incorrect PIN${d.remaining != null ? ` (${d.remaining} left)` : ''}`;
        showError(msg);
        pin = ''; updateDots();
        if (d.remaining === 0) startLockoutCountdown(60);
      }
    } catch (_) {}
  }

  overlay.addEventListener('click', async (e) => {
    if (locked) return;
    const key = e.target.closest('button')?.dataset?.key;
    if (key === undefined) return;
    if (key === '⌫') { pin = pin.slice(0, -1); }
    else if (pin.length < 6) { pin += key; }
    updateDots();
    if (pin.length === 6) await submitPin();
  });

  document.addEventListener('keydown', async (e) => {
    if (!document.getElementById('pin-overlay') || locked) return;
    if (e.key >= '0' && e.key <= '9' && pin.length < 6) { pin += e.key; }
    else if (e.key === 'Backspace') { pin = pin.slice(0, -1); }
    else if (e.key === 'Enter' && pin.length > 0) { await submitPin(); return; }
    updateDots();
    if (pin.length === 6) await submitPin();
  });
};

__ptBoot();
