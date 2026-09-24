/* WIDDX Nexus — Plugins View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showPluginsView(area) {
  setActivity('Loading', 'plugins');
  area.innerHTML = TEMPLATES.view('fa-puzzle-piece', 'Plugins', 'Manage installed plugins',
    '<div id="plugin-list">Loading...</div>'
  );
  try {
    const r = await fetch('/api/plugins');
    const plugins = await r.json();
    const el = document.getElementById('plugin-list');
    if (Array.isArray(plugins) && plugins.length) {
      el.innerHTML = plugins.map(function(p) {
        const name = p.name || p.id || 'unknown';
        const enabled = p.enabled !== false;
        const desc = p.description || p.summary || '';
        return '<div class="flex-ac-sb py-8 border-bottom-light">'
          + '<div><strong>' + escapeHtml(name) + '</strong><br><span style="font-size:11px;color:var(--text-muted)">' + escapeHtml(desc.slice(0, 60)) + '</span></div>'
          + '<div><span style="color:' + (enabled ? 'var(--success)' : 'var(--text-muted)') + '">' + (enabled ? '\u25cf Enabled' : '\u25cb Disabled') + '</span>'
           + ' <button class="' + (enabled ? 'btn-icon-warning' : 'btn-icon-success') + '" data-click="toggle-plugin" data-plugin="' + encodeURIComponent(name) + '" data-enabled="' + enabled + '">' + (enabled ? 'Disable' : 'Enable') + '</button></div></div>';
      }).join('');
    } else {
      el.innerHTML = '<span style="color:var(--text-muted)">No plugins installed</span>';
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('plugin-list');
    if (el) el.innerHTML = '<span style="color:var(--error)">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}

// Toggle plugin handler with safe decoding
window.togglePlugin = async function(nameEncoded, isEnabled) {
  const name = decodeURIComponent(nameEncoded);
  const action = isEnabled ? 'disable' : 'enable';
  try {
    await fetch('/api/plugins/' + encodeURIComponent(name) + '/' + action, { method:'POST' });
    showToast('Plugin ' + action + 'd', 'success');
    showPluginsView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
