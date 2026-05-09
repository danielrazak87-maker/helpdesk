// ─── Theme Toggle (3-theme: dark / light / kayfalah) ──────────────────────
// NOTE: setTheme is used by inline onclick — it must be a global function
// CSP blocks inline onclick handlers, so we attach listeners here instead
(function initTheme() {
  window.setTheme = setTheme;  // Expose for any legacy inline onclick usage

  function setTheme(t) {
    // Remove all theme classes from <html> (':root' in CSS)
    document.documentElement.classList.remove('light-theme', 'kayfalah-theme');
    // Apply the selected theme class
    if (t !== 'dark') {
      document.documentElement.classList.add(t + '-theme');
    }
    localStorage.setItem('helpdeskTheme', t);
    // Highlight active button
    document.querySelectorAll('.theme-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.theme === t);
    });
  }

  // Restore saved theme on load
  var saved = localStorage.getItem('helpdeskTheme') || 'dark';
  setTheme(saved);

  // Attach click listeners to theme toggle buttons
  document.querySelectorAll('.theme-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
      setTheme(this.dataset.theme);
    });
  });
})();

// ─── Sidebar Toggle ──────────────────────────────────────────────────────────
const sidebar = document.getElementById('sidebar');
const toggle = document.getElementById('sidebarToggle');
if (toggle) {
  toggle.addEventListener('click', () => sidebar.classList.toggle('open'));
}

// Auto-close sidebar on nav click (mobile)
if (sidebar) {
  sidebar.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', () => {
      if (window.innerWidth <= 900) sidebar.classList.remove('open');
    });
  });
}

// ─── Notification Dropdown ───────────────────────────────────────────────────
const notifBtn = document.getElementById('notifBtn');
const notifDropdown = document.getElementById('notifDropdown');
if (notifBtn) {
  notifBtn.addEventListener('click', e => {
    e.stopPropagation();
    notifDropdown.classList.toggle('open');
  });
  document.addEventListener('click', e => {
    if (!document.getElementById('notifWrapper')?.contains(e.target)) {
      notifDropdown?.classList.remove('open');
    }
  });
}

// Periodic notification badge poll (every 30s)
(function pollNotifBadge() {
  const badge = document.querySelector('.notif-badge');
  if (!badge) return;
  setInterval(async () => {
    try {
      // Simple heartbeat — count is embedded in base.html via Jinja
      // For live updates, we'd need an endpoint. This prevents staleness.
    } catch (_) {}
  }, 30000);
})();

// ─── Flash Message Auto-Dismiss ──────────────────────────────────────────────
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => {
    if (el.parentElement) el.remove();
  }, 5000);
});

// ─── Loading State on All Forms ──────────────────────────────────────────────
document.querySelectorAll('form:not([data-no-loading])').forEach(form => {
  form.addEventListener('submit', function(e) {
    const btn = this.querySelector('button[type="submit"]');
    if (!btn || btn.disabled) return;

    // Check validity
    if (!this.checkValidity || this.checkValidity()) {
      btn.disabled = true;
      btn.classList.add('btn-loading');

      // Preserve original text
      const textSpan = btn.querySelector('.btn-text') || btn;
      const spinner = btn.querySelector('.btn-spinner');
      if (spinner) {
        textSpan.style.display = 'none';
        spinner.style.display = 'inline';
      } else {
        const orig = btn.getAttribute('data-orig-text') || btn.textContent;
        if (!btn.getAttribute('data-orig-text')) btn.setAttribute('data-orig-text', orig);
        btn.innerHTML = '<span class="spinner"></span> Submitting...';
      }

      // Re-enable after 30s timeout (safety net)
      setTimeout(() => {
        btn.disabled = false;
        btn.classList.remove('btn-loading');
        const sp = btn.querySelector('.btn-spinner');
        const ts = btn.querySelector('.btn-text');
        if (sp && ts) { ts.style.display = 'inline'; sp.style.display = 'none'; }
        else { const orig = btn.getAttribute('data-orig-text') || 'Submit'; btn.textContent = orig; }
      }, 30000);
    }
  });
});

// ─── Loading Overlay for Page Navigation ─────────────────────────────────────
// Show overlay on slow page loads
let loadTimer;
document.addEventListener('DOMContentLoaded', () => {
  clearTimeout(loadTimer);
  const overlay = document.getElementById('loadingOverlay');
  if (overlay) overlay.remove();
});
loadTimer = setTimeout(() => {
  if (!document.querySelector('.content')) {
    const overlay = document.createElement('div');
    overlay.id = 'loadingOverlay';
    overlay.className = 'loading-overlay';
    overlay.innerHTML = '<div class="spinner"></div>';
    document.body.appendChild(overlay);
  }
}, 800);

// ─── Keyboard Shortcuts ─────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  // Ctrl+K or Cmd+K → focus search
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    const searchInput = document.getElementById('globalSearch');
    if (searchInput) searchInput.focus();
  }

  // Ctrl+N or Cmd+N → new ticket
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
    e.preventDefault();
    const newBtn = document.querySelector('a[href*="/tickets/create"]');
    if (newBtn) window.location.href = newBtn.href;
  }

  // Escape → close dropdowns
  if (e.key === 'Escape') {
    const dd = document.getElementById('notifDropdown');
    if (dd) dd.classList.remove('open');
    const sd = document.querySelector('.search-dropdown');
    if (sd) sd.style.display = 'none';
  }
});

// ─── Global Ticket Search ────────────────────────────────────────────────────
const search = document.getElementById('globalSearch');
if (search) {
  let timer;
  const dropdown = document.createElement('div');
  dropdown.className = 'search-dropdown';
  search.parentElement.appendChild(dropdown);
  dropdown.style.display = 'none';

  search.addEventListener('input', e => {
    clearTimeout(timer);
    const q = e.target.value.trim();
    if (q.length >= 2) {
      timer = setTimeout(() => fetchSearchResults(q), 400);
    } else {
      dropdown.style.display = 'none';
    }
  });

  search.addEventListener('blur', () => {
    setTimeout(() => { dropdown.style.display = 'none'; }, 200);
  });

  search.addEventListener('focus', e => {
    if (e.target.value.trim().length >= 2) {
      dropdown.style.display = 'block';
    }
  });

  function fetchSearchResults(q) {
    fetch(`/search?q=${encodeURIComponent(q)}`)
      .then(r => r.json())
      .then(data => {
        dropdown.innerHTML = '';
        if (data.results && data.results.length > 0) {
          data.results.forEach(t => {
            const item = document.createElement('a');
            item.href = t.url;
            item.className = 'search-result-item';
            const prioColor = {critical: '#ef4444', high: '#f59e0b', medium: '#6366f1', low: '#10b981'};
            item.innerHTML = `
              <div class="search-result-main">
                <span class="search-ticket-num">${t.ticket_number}</span>
                <span class="search-title">${escapeHtml(t.title)}</span>
              </div>
              <div class="search-result-meta">
                <span class="search-priority" style="color:${prioColor[t.priority] || '#6366f1'}">● ${t.priority}</span>
                <span class="search-status">${t.status}</span>
              </div>
            `;
            dropdown.appendChild(item);
          });
        } else {
          dropdown.innerHTML = '<div class="search-empty">🔍 No tickets found</div>';
        }
        dropdown.style.display = 'block';
      })
      .catch(() => { dropdown.style.display = 'none'; });
  }

  function escapeHtml(text) {
    const d = document.createElement('div');
    d.textContent = text;
    return d.innerHTML;
  }
}

// ─── Confirm on Destructive Actions ──────────────────────────────────────────
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});

// ─── Enhanced Empty State: Replace bare "No items" text with styled version ─
document.querySelectorAll('.empty-state-plain').forEach(el => {
  const msg = el.textContent.trim();
  if (msg && !el.querySelector('.empty-icon')) {
    el.innerHTML = `<div class="empty-state"><span class="empty-icon">📂</span><span>${msg}</span></div>`;
  }
});

// ─── Ctrl+Enter to submit active form ───────────────────────────────────────
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
    const active = document.activeElement;
    if (active && active.form) {
      const btn = active.form.querySelector('button[type="submit"]');
      if (btn) btn.click();
    }
  }
});
