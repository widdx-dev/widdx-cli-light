/* WIDDX Nexus — Auto-Commit View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showAutoCommitView(area) {
  setActivity('Loading', 'auto-commit');
  area.innerHTML = TEMPLATES.view('fa-arrows-rotate', 'Auto-Commit', 'Automatic git commit scheduling',
    '<div id="autocommit-content">' + TEMPLATES.loading('Loading auto-commit settings...') + '</div>'
  );
  try {
    const r = await fetch('/api/autocommit');
    const d = await r.json();
    var html = ''
      + '<div class="settings-card">'
      + '<div class="flex-ac-sb">'
      + '<div><strong class="text-primary">Status</strong>'
      + '<br><span class="text-muted text-sm">' + (d.enabled ? '\ud83d\udfe2 Running' : '\u26aa Stopped') + '</span></div>'
      + '<button data-click="toggle-autocommit" class="send-btn" style="width:auto;padding:8px 20px;border-radius:6px;background:' + (d.enabled ? 'var(--error)' : 'var(--success)') + '">'
      + (d.enabled ? 'Stop' : 'Start') + '</button>'
      + '</div></div>'
      + '<div class="settings-card">'
      + '<div class="flex" style="justify-content:space-between"><span class="text-secondary">Interval</span>'
      + '<strong class="text-primary">' + (d.interval || '\u2014') + 's</strong></div>'
      + '</div>'
      + '<div class="settings-card">'
      + '<div class="flex" style="justify-content:space-between"><span class="text-secondary">Last Commit</span>'
      + '<strong class="text-primary">' + (d.last_commit || 'Never') + '</strong></div>'
      + '</div>';
    document.getElementById('autocommit-content').innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('autocommit-content').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.toggleAutoCommit = async function() {
  try {
    var r = await fetch('/api/autocommit/toggle', { method:'POST' });
    var d = await r.json();
    showToast(d.status === 'toggled' ? 'Auto-commit ' + (d.enabled ? 'started' : 'stopped') : (d.error || 'Failed'), d.status === 'toggled' ? 'success' : 'error');
    showAutoCommitView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
