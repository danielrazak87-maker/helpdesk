// Sidebar toggle
const sidebar = document.getElementById('sidebar');
const toggle = document.getElementById('sidebarToggle');
if (toggle) toggle.addEventListener('click', () => sidebar.classList.toggle('open'));

// Notification dropdown
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

// Auto-dismiss flash messages after 4 seconds
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => el.remove(), 4000);
});

// Global ticket search
const search = document.getElementById('globalSearch');
if (search) {
  let timer;
  search.addEventListener('input', e => {
    clearTimeout(timer);
    const q = e.target.value.trim();
    if (q.length >= 2) {
      timer = setTimeout(() => {
        window.location.href = `/tickets/?search=${encodeURIComponent(q)}`;
      }, 600);
    }
  });
}

// Confirm on destructive actions
document.querySelectorAll('[data-confirm]').forEach(el => {
  el.addEventListener('click', e => {
    if (!confirm(el.dataset.confirm)) e.preventDefault();
  });
});
