/* WIDDX Nexus — GGUF View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

async function showGGUFView(area) {
  setActivity('Loading', 'GGUF models');
  area.innerHTML = TEMPLATES.view('fa-box', 'GGUF Models', 'Local GGUF model management',
    '<div class="settings-card">'
    + '<label class="settings-card-label"><i class="fa-solid fa-upload"></i> Load Model</label>'
    + '<div class="flex gap-8">'
    + '<input id="gguf-path" class="settings-input" placeholder="/path/to/model.gguf">'
    + '<button data-click="load-gguf" class="send-btn w-auto px-8 rounded-6">Load</button>'
    + '</div></div>'
    + '<div id="gguf-list">' + TEMPLATES.loading('Loading GGUF models...') + '</div>'
  );
  try {
    const r = await fetch('/api/gguf');
    var models = await r.json();
    var el = document.getElementById('gguf-list');
    if (Array.isArray(models) && models.length) {
      el.innerHTML = '<h4 class="mb-8">Available Models</h4>'
        + models.map(function(m) {
          var name = m.name || m.path || 'unknown';
          var loaded = m.loaded ? '\ud83d\udfe2 Loaded' : '\u26aa Unloaded';
          var size = m.size ? ' \u00b7 ' + Math.round(m.size / 1024 / 1024) + 'MB' : '';
          return '<div class="flex-ac-sb py-8 border-bottom-light">'
            + '<span><strong>' + escapeHtml(name) + '</strong>' + escapeHtml(size) + '</span>'
            + '<span style="color:' + (m.loaded ? 'var(--success)' : 'var(--text-muted)') + '">' + loaded + '</span></div>';
        }).join('')
        + '<button data-click="unload-gguf" class="btn-primary mt-12" style="background:var(--error)"><i class="fa-solid fa-power-off"></i> Unload Current</button>';
    } else {
      el.innerHTML = TEMPLATES.empty('fa-box', 'No GGUF models found', 'Enter a path above to load a GGUF model.');
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('gguf-list').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.loadGGUF = async function() {
  var path = document.getElementById('gguf-path')?.value.trim();
  if (!path) { showToast('Please enter a model path', 'error'); return; }
  try {
    var r = await fetch('/api/gguf/load', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:path}) });
    var d = await r.json();
    showToast(d.status === 'loaded' ? 'Model loaded' : (d.error || 'Failed'), d.status === 'loaded' ? 'success' : 'error');
    showGGUFView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};

window.unloadGGUF = async function() {
  var ok = await showConfirm('Unload GGUF model?', 'The current GGUF model will be unloaded from memory.', { confirmText: 'Unload', danger: true });
  if (!ok) return;
  try {
    var r = await fetch('/api/gguf/unload', { method:'POST' });
    var d = await r.json();
    showToast(d.status === 'unloaded' ? 'Model unloaded' : (d.error || 'Failed'), 'info');
    showGGUFView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
