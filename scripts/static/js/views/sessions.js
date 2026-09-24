/* WIDDX Nexus — Sessions View + Sidebar Loader */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showView, showConfirm, showToast, S) */

async function showSessionsView(area) {
  setActivity('Loading', 'sessions');
  area.innerHTML = TEMPLATES.view('fa-clock-rotate-left', 'Saved Sessions', 'Persistent conversation history',
    '<div class="mb-12"><input id="session-search" class="w-full bg-input border-main rounded-6 text-primary text-13" style="padding:8px 12px;box-sizing:border-box" placeholder="Search sessions..." oninput="searchSessions(this.value)"></div>'
    + '<div id="session-list">Loading...</div>'
  );
  await refreshSessionList();
  setActivity('Ready', '\u2014');
}

async function refreshSessionList() {
  try {
    const r = await fetch('/api/dashboard/sessions');
    const sessions = await r.json();
    const el = document.getElementById('session-list');
    if (!el) return;
    if (!Array.isArray(sessions) || !sessions.length) {
      el.innerHTML = '<span class="text-muted">No saved sessions. Chat messages are auto-saved.</span>';
    } else {
      el.innerHTML = sessions.map(function(s) {
        const id = s.id || s.session_id || '';
        const name = s.name || 'Untitled';
        const date = s.created_at ? new Date(s.created_at * 1000).toLocaleString() : (s.timestamp || '');
        const msgCount = s.message_count || s.messages?.length || 0;
        return '<div class="flex-ac-sb py-8 border-bottom-light">'
          + '<div><strong>' + escapeHtml(name) + '</strong><br><span class="text-11 text-muted">' + escapeHtml(date) + ' \u00b7 ' + msgCount + ' messages</span></div>'
          + '<div>'
          + '<button class="btn-icon-accent" data-click="load-session-btn" data-session="' + escapeHtml(id) + '" title="Load">\uD83D\uDCC2</button>'
          + '<button class="btn-icon-success" data-click="export-session" data-session="' + escapeHtml(id) + '" title="Export as Markdown">\uD83D\uDCC4</button>'
          + '<button class="btn-icon-error" data-click="del-session" data-session="' + escapeHtml(id) + '" title="Delete">\u2715</button></div></div>';
      }).join('');
    }
  } catch(e) {
    const el = document.getElementById('session-list');
    if (el) el.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  }
}

window.loadSession = async function(id) {
  try {
    const r = await fetch('/api/sessions/' + encodeURIComponent(id));
    const d = await r.json();
    if (d.status === 'ok' && d.session) {
      S.messages = d.session.messages || [];
      showView('chat');
      showToast('Session loaded', 'success');
    } else { showToast(d.error || 'Load failed', 'error'); }
  } catch(e) { showToast(e.message, 'error'); }
};

window.exportSession = async function(id) {
  try {
    const r = await fetch('/api/sessions/' + encodeURIComponent(id) + '/export');
    const d = await r.json();
    if (d.status === 'ok' && d.markdown) {
      await navigator.clipboard.writeText(d.markdown);
      showToast('Exported as Markdown (copied to clipboard)', 'success');
    } else { showToast(d.error || 'Export failed', 'error'); }
  } catch(e) { showToast(e.message, 'error'); }
};

window.delSession = async function(id) {
  var ok = await showConfirm('Delete session?', 'This conversation will be permanently removed.', { confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    await fetch('/api/sessions/' + encodeURIComponent(id), { method:'DELETE' });
    showToast('Session deleted', 'success');
    await refreshSessionList();
  } catch(e) { showToast(e.message, 'error'); }
};

window.searchSessions = function(q) {
  var items = document.querySelectorAll('#session-list > div');
  if (!q) { items.forEach(function(i) { i.style.display = ''; }); return; }
  var query = q.toLowerCase().trim();
  items.forEach(function(i) {
    i.style.display = i.textContent.toLowerCase().indexOf(query) !== -1 ? '' : 'none';
  });
};

async function loadSidebar() {
  try {
    const r = await fetch('/api/dashboard/sessions');
    const sessions = await r.json();
    const nav = document.querySelector('.sidebar-nav');

    var oldItems = nav.querySelectorAll('.chat-item, .nav-section-label.nav-recent');
    oldItems.forEach(function(o) { o.remove(); });

    if (sessions.length > 0) {
      var label = document.createElement('div');
      label.className = 'nav-section-label nav-recent';
      label.textContent = 'Recent';
      nav.appendChild(label);
      sessions.slice(0, 8).forEach(function(s) {
        var item = document.createElement('div');
        item.className = 'chat-item';
        var sid = s.id || s.session_id || '';
        item.innerHTML = '<div class="chat-item-content"><div class="chat-item-title">' + escapeHtml(s.name || s.title || 'Chat') + '</div><div class="chat-item-meta">' + (s.created_at ? new Date(s.created_at * 1000).toLocaleDateString() : '') + '</div></div>';
        item.setAttribute('data-click', 'sidebar-load-session');
        item.setAttribute('data-sid', sid);
        nav.appendChild(item);
      });
    }

    var cronR = await fetch('/api/dashboard/cron');
    var cron = await cronR.json();
    var badge = document.getElementById('cronBadge');
    if (badge) {
      var count = cron.length || 0;
      badge.textContent = count;
      badge.style.display = count > 0 ? '' : 'none';
    }

    var tasksR = await fetch('/api/dashboard/background');
    var tasks = await tasksR.json();
    var plan = document.getElementById('plan-badge');
    if (plan && tasks.length) plan.textContent = '\ud83d\udfe2 ' + tasks.length + ' running';
  } catch(e) { console.log('Sidebar:', e.message); }
}
