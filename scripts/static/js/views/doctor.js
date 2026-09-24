/* WIDDX Nexus — Doctor (Health) View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity) */

async function showDoctorView(area) {
  setActivity('Running', 'health checks');
  area.innerHTML = TEMPLATES.view('fa-stethoscope', 'System Health', 'Diagnostics and system checks',
    '<div class="mb-12"><button class="send-btn w-auto rounded-6" data-click="run-doctor" style="padding:6px 16px"><i class="fa-solid fa-stethoscope"></i> Run Checks</button></div>'
    + '<div id="doctor-results">Running checks...</div>'
  );
  try {
    const r = await fetch('/api/doctor');
    const checks = await r.json();
    const el = document.getElementById('doctor-results');
    if (Array.isArray(checks) && checks.length) {
      el.innerHTML = checks.map(function(c) {
        const icons = {ok:'\u2705', warning:'\u26a0\ufe0f', error:'\u274c', info:'\u2139\ufe0f'};
        const icon = icons[c.status] || '\u2753';
        const colorMap = {ok:'var(--success)', warning:'var(--warning)', error:'var(--error)', info:'var(--text-muted)'};
        return '<div class="py-8 border-bottom-light flex gap-8" style="align-items:flex-start">'
          + '<span>' + icon + '</span>'
          + '<div><strong>' + escapeHtml(c.check) + '</strong><br><span style="color:' + (colorMap[c.status] || 'var(--text-muted)') + ';font-size:12px">' + escapeHtml(c.message || '') + '</span></div></div>';
      }).join('');
    } else {
      el.innerHTML = '<span class="text-muted">No diagnostic data available</span>';
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('doctor-results');
    if (el) el.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}
