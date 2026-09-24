/* WIDDX Nexus — Manifest View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showManifestView(area) {
  setActivity('Loading', 'manifest');
  area.innerHTML = TEMPLATES.view('fa-file-invoice', 'Manifest', 'Project MANIFEST.json status',
    '<div id="manifest-content">' + TEMPLATES.loading('Loading manifest...') + '</div>'
  );
  try {
    const r = await fetch('/api/manifest');
    const d = await r.json();
    var html = '';
    if (d.exists) {
      html += '<div class="settings-card">'
        + '<div style="display:flex;align-items:center;gap:10px">'
        + '<span style="font-size:24px;color:var(--success)">\ud83d\udccb</span>'
        + '<div><strong style="color:var(--text-primary)">MANIFEST.json exists</strong>'
        + '<br><span style="color:var(--text-muted);font-size:var(--font-size-sm)">' + escapeHtml(d.message || '') + '</span></div></div></div>';
    } else {
      html += '<div class="settings-card">'
        + '<div style="display:flex;align-items:center;gap:10px">'
        + '<span style="font-size:24px;color:var(--warning)">\u26a0\ufe0f</span>'
        + '<div><strong style="color:var(--text-primary)">No MANIFEST.json found</strong>'
        + '<br><span style="color:var(--text-muted);font-size:var(--font-size-sm)">' + escapeHtml(d.message || 'Run a scan to create one.') + '</span></div></div></div>';
    }
    html += '<button data-click="scan-manifest" class="btn-primary"><i class="fa-solid fa-magnifying-glass"></i> Scan Now</button>'
      + '<span id="manifest-scan-status" style="margin-left:12px;font-size:var(--font-size-sm);color:var(--text-muted)"></span>';
    document.getElementById('manifest-content').innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('manifest-content').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.scanManifest = async function() {
  var status = document.getElementById('manifest-scan-status');
  if (status) status.textContent = 'Scanning...';
  try {
    var r = await fetch('/api/manifest/scan', { method:'POST' });
    var d = await r.json();
    if (status) status.textContent = d.status === 'scanned' ? '\u2713 ' + (d.changes || 'No changes') : '\u2717 ' + (d.error || 'Failed');
    showToast(d.status === 'scanned' ? 'Manifest scanned' : 'Scan failed', d.status === 'scanned' ? 'success' : 'error');
  } catch(e) { if (status) status.textContent = '\u2717 ' + e.message; showToast(e.message, 'error'); }
};
