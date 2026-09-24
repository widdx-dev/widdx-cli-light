/* WIDDX Nexus — Checkpoints View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

async function showCheckpointsView(area) {
  setActivity('Loading', 'checkpoints');
  area.innerHTML = TEMPLATES.view('fa-camera-retro', 'Checkpoints', 'Snapshot-based file saves (no Git required)',
    '<div class="mb-12"><button class="send-btn w-auto rounded-6" style="padding:6px 16px" data-click="create-checkpoint"><i class="fa-solid fa-camera"></i> Create Checkpoint</button></div>'
    + '<div id="checkpoint-list">Loading...</div>'
  );
  try {
    const r = await fetch('/api/checkpoints');
    const cps = await r.json();
    const el = document.getElementById('checkpoint-list');
    if (!Array.isArray(cps) || !cps.length) {
      el.innerHTML = '<span class="text-muted">No checkpoints yet.</span>';
    } else {
      el.innerHTML = cps.map(function(c) {
        const id = c.id || '';
        const ts = c.timestamp || c.created_at || '';
        return '<div class="flex-ac-sb py-8 border-bottom-light">'
          + '<span><strong>' + escapeHtml(id.slice(0, 12)) + '</strong> \u00b7 ' + escapeHtml(ts) + '</span>'
          + '<span>'
          + '<button class="btn-icon-accent" data-click="restore-checkpoint" data-checkpoint="' + escapeHtml(id) + '" title="Restore">\u21a9</button>'
          + '<button class="btn-icon-error" data-click="del-checkpoint" data-checkpoint="' + escapeHtml(id) + '" title="Delete">\u2715</button></span></div>';
      }).join('');
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('checkpoint-list');
    if (el) el.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}

window.createCheckpoint = async function() {
  try {
    const r = await fetch('/api/checkpoints', { method:'POST' });
    const d = await r.json();
    showToast(d.status === 'created' ? 'Checkpoint created' : (d.error || 'Failed'), d.status === 'created' ? 'success' : 'error');
    showCheckpointsView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};

window.restoreCheckpoint = async function(id) {
  var ok = await showConfirm('Restore checkpoint?', 'This will overwrite current file state. This action cannot be undone.', { confirmText: 'Restore', danger: true });
  if (!ok) return;
  try {
    const r = await fetch('/api/checkpoints/' + encodeURIComponent(id) + '/restore', { method:'POST' });
    const d = await r.json();
    showToast(d.status === 'restored' ? 'Checkpoint restored' : (d.error || 'Failed'), d.status === 'restored' ? 'success' : 'error');
  } catch(e) { showToast(e.message, 'error'); }
};

window.delCheckpoint = async function(id) {
  var ok = await showConfirm('Delete checkpoint?', 'This checkpoint will be permanently removed.', { confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    await fetch('/api/checkpoints/' + encodeURIComponent(id), { method:'DELETE' });
    showToast('Checkpoint deleted', 'success');
    showCheckpointsView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
