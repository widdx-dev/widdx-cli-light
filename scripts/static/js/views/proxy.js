/* WIDDX Nexus — Proxy View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showProxyView(area) {
  setActivity('Loading', 'proxy');
  area.innerHTML = TEMPLATES.view('fa-plug', 'Proxy Settings', 'HTTP/HTTPS proxy configuration',
    '<div id="proxy-form">' + TEMPLATES.loading('Loading proxy settings...') + '</div>'
  );
  try {
    const r = await fetch('/api/proxy');
    const d = await r.json();
    var html = ''
      + '<div class="settings-card">'
      + '<label class="settings-card-label"><i class="fa-solid fa-toggle-on"></i> Enable Proxy</label>'
      + '<label style="display:flex;align-items:center;gap:8px;cursor:pointer">'
      + '<input type="checkbox" id="proxy-enabled" ' + (d.enabled ? 'checked' : '') + '>'
      + '<span style="font-size:var(--font-size-sm);color:var(--text-secondary)">' + (d.enabled ? 'Enabled' : 'Disabled') + '</span>'
      + '</label></div>'
      + '<div class="settings-card">'
      + '<label class="settings-card-label"><i class="fa-solid fa-link"></i> HTTP Proxy</label>'
      + '<input id="proxy-http" class="settings-input" placeholder="http://proxy:8080" value="' + escapeHtml(d.http || '') + '">'
      + '</div>'
      + '<div class="settings-card">'
      + '<label class="settings-card-label"><i class="fa-solid fa-link"></i> HTTPS Proxy</label>'
      + '<input id="proxy-https" class="settings-input" placeholder="https://proxy:8443" value="' + escapeHtml(d.https || '') + '">'
      + '</div>'
      + '<button data-click="save-proxy" class="btn-primary" style="margin-top:4px"><i class="fa-solid fa-floppy-disk"></i> Save Proxy</button>'
      + '<span id="proxy-status" style="margin-left:12px;font-size:var(--font-size-sm);color:var(--text-muted)"></span>';
    document.getElementById('proxy-form').innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('proxy-form').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.saveProxy = async function() {
  var enabled = document.getElementById('proxy-enabled')?.checked || false;
  var http = document.getElementById('proxy-http')?.value || '';
  var https = document.getElementById('proxy-https')?.value || '';
  var status = document.getElementById('proxy-status');
  if (status) status.textContent = 'Saving...';
  try {
    var r = await fetch('/api/proxy', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({http:http, https:https, enabled:enabled}) });
    var d = await r.json();
    if (status) status.textContent = d.status === 'updated' ? '\u2713 Saved' : '\u2717 ' + (d.error || 'Failed');
    if (d.status === 'updated') showToast('Proxy updated', 'success');
  } catch(e) { if (status) status.textContent = '\u2717 ' + e.message; showToast(e.message, 'error'); }
};
