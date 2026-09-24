/* WIDDX Nexus — Permissions View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showPermissionsView(area) {
  setActivity('Loading', 'permissions');
  area.innerHTML = TEMPLATES.view('fa-shield', 'Permissions', 'Control the level of command and tool access',
    '<div id="perm-status">Loading...</div>'
  );
  try {
    const r = await fetch('/api/permissions');
    const d = await r.json();
    const el = document.getElementById('perm-status');
    const levels = d.levels || ['permissive', 'normal', 'strict', 'silent'];
    const current = d.level || 'normal';
    const icons = {permissive:'\ud83d\udfe2', normal:'\ud83d\udd35', strict:'\ud83d\udfe1', silent:'\ud83d\udd34'};
    const descs = {permissive:'Allow all commands', normal:'Block dangerous patterns', strict:'Read-only + safe tools', silent:'Read-only, no confirmations'};
    el.innerHTML = '<div class="mb-12 p-8 bg-input rounded-6">'
      + 'Current level: <strong>' + (icons[current] || '') + ' ' + current + '</strong></div>'
      + '<div class="flex flex-col gap-8">'
      + levels.map(function(l) {
        const active = l === current;
        return '<div style="display:flex;align-items:center;gap:8px;padding:8px;background:' + (active ? 'var(--accent)' : 'var(--bg-input)') + ';border-radius:6px;cursor:pointer;color:' + (active ? '#fff' : 'var(--text-primary)') + '" data-click="set-permission" data-level="' + l + '">'
          + '<span style="font-size:16px">' + (icons[l] || '\u2022') + '</span>'
          + '<div><strong>' + l + '</strong><br><span class="text-11" style="opacity:0.7">' + (descs[l] || '') + '</span></div>'
          + (active ? '<span style="margin-left:auto">\u2713</span>' : '')
          + '</div>';
      }).join('') + '</div>';
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('perm-status');
    if (el) el.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}

window.setPermission = async function(level) {
  try {
    const r = await fetch('/api/permissions', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({level:level}) });
    const d = await r.json();
    showToast(d.status === 'set' ? 'Permission: ' + level : (d.error || 'Failed'), d.status === 'set' ? 'success' : 'error');
    showPermissionsView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
