/* WIDDX Nexus — API Keys View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity) */

async function showApiKeysView(area) {
  setActivity('Loading', 'API keys');
  area.innerHTML = TEMPLATES.view('fa-key', 'API Keys', 'Stored provider API keys (values masked)',
    '<div id="apikeys-content">' + TEMPLATES.loading('Loading API keys...') + '</div>'
  );
  try {
    const r = await fetch('/api/apikeys');
    const d = await r.json();
    var html = '';
    var entries = Object.entries(d);
    if (entries.length) {
      html += entries.map(function(kv) {
        var name = kv[0];
        var info = kv[1] || {};
        var masked = info.masked || 'has key';
        var hasKey = info.has_key;
        return '<div class="settings-card"><div style="display:flex;align-items:center;gap:10px">'
          + '<span style="font-size:20px;color:' + (hasKey ? 'var(--success)' : 'var(--text-muted)') + '">\ud83d\udd11</span>'
          + '<div style="flex:1"><strong style="color:var(--text-primary)">' + escapeHtml(name) + '</strong>'
          + '<br><span style="color:var(--text-muted);font-size:var(--font-size-sm);font-family:var(--font-mono)">' + escapeHtml(masked) + '</span></div>'
          + (hasKey ? '<span style="color:var(--success);font-size:var(--font-size-xs)">\u25cf Configured</span>' : '<span style="color:var(--text-muted);font-size:var(--font-size-xs)">\u25cf No key</span>')
          + '</div></div>';
      }).join('');
    } else {
      html = TEMPLATES.empty('fa-key', 'No API keys stored', 'Add API keys in Settings to see them here.');
    }
    document.getElementById('apikeys-content').innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('apikeys-content').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}
