/* WIDDX Nexus — Debug View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity) */

async function showDebugView(area) {
  setActivity('Loading', 'debug');
  area.innerHTML = TEMPLATES.view('fa-bug', 'Debug Information', 'Low-level system diagnostics',
    '<div class="mb-12"><button class="send-btn w-auto rounded-6" data-click="refresh-debug" style="padding:6px 16px"><i class="fa-solid fa-rotate"></i> Refresh</button></div>'
    + '<div id="debug-content">Loading...</div>'
  );
  try {
    const r = await fetch('/api/debug');
    const d = await r.json();
    const el = document.getElementById('debug-content');
    let html = '';
    if (d.errors && Array.isArray(d.errors)) {
      html += '<h4 class="mb-8">Recent Errors (' + d.errors.length + ')</h4>';
      if (d.errors.length) {
        html += d.errors.map(function(e) {
          return '<div class="border-bottom-light text-12 text-mono" style="padding:4px 0">' + escapeHtml(JSON.stringify(e).slice(0, 200)) + '</div>';
        }).join('');
      } else {
        html += '<span style="color:var(--success)">No errors recorded</span>';
      }
    }
    if (d.config) {
      html += '<h4 class="mt-12 mb-8">Config</h4><pre class="bg-input p-8 rounded-4 text-11 max-h-200 overflow-auto">' + escapeHtml(d.config.slice(0, 500)) + '</pre>';
    }
    if (d.tools !== undefined) {
      html += '<h4 class="mt-12 mb-8">Tools</h4><span>' + d.tools + ' tool definitions loaded</span>';
    }
    el.innerHTML = html || '<span class="text-muted">No debug data</span>';
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('debug-content');
    if (el) el.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}
