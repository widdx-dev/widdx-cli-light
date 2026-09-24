/* WIDDX Nexus — Cron/Scheduler View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

async function showCronView(area) {
  setActivity('Loading', 'cron jobs');
  area.innerHTML = TEMPLATES.view('fa-calendar-clock', 'Scheduled Tasks', 'Manage cron jobs',
    '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-plus"></i> Add Task</div>'
    + '<div class="flex gap-8" style="flex-wrap:wrap">'
    + '<input id="cron-name" class="settings-input flex-1" style="min-width:120px" placeholder="Task name">'
    + '<input id="cron-cmd" class="settings-input flex-2" style="min-width:200px" placeholder="Command to run">'
    + '<select id="cron-interval" class="settings-select flex-0-auto">'
    + '<option value="5">5 min</option><option value="15">15 min</option><option value="30">30 min</option>'
    + '<option value="60">1 hour</option><option value="360">6 hours</option><option value="1440">Daily</option>'
    + '</select>'
    + '<button class="send-btn w-auto px-8 rounded-6" data-click="add-cron">Add</button>'
    + '</div></div>'
    + '<div id="cron-list">' + TEMPLATES.skeleton(3) + '</div>');
  try {
    const r = await fetch('/api/dashboard/cron');
    const jobs = await r.json();
    const el = document.getElementById('cron-list');
    if (!jobs.length) {
      el.innerHTML = TEMPLATES.empty('fa-calendar-clock', 'No scheduled tasks', 'Add a task above to get started.');
    } else {
      el.innerHTML = jobs.map(function(j) {
        var name = j.name || j.id || 'task';
        var interval = j.interval || j.schedule || '?';
        var status = j.status || 'idle';
        var color = status === 'running' ? 'var(--success)' : status === 'error' ? 'var(--error)' : 'var(--text-muted)';
        return '<div class="flex-ac-sb py-8 border-bottom-light">'
          + '<div><strong>' + escapeHtml(name) + '</strong><br><span class="text-11 text-muted">Every ' + interval + 's · ' + escapeHtml(j.command || '') + '</span></div>'
          + '<div><span style="color:' + color + '">● ' + status + '</span>'
          + ' <button class="btn-icon-warning" data-click="toggle-cron" data-cron="' + encodeURIComponent(j.id || name) + '" title="Toggle">⏸</button>'
          + ' <button class="btn-icon-error" data-click="del-cron" data-cron="' + encodeURIComponent(j.id || name) + '" title="Remove">✕</button></div></div>';
      }).join('');
    }
    setActivity('Ready', '—');
  } catch(e) {
    var el2 = document.getElementById('cron-list');
    if (el2) el2.innerHTML = TEMPLATES.errorRetry(e.message, 'retry-cron-view');
    setActivity('Ready', '—');
  }
}

window.addCronJob = async function() {
  var name = document.getElementById('cron-name')?.value.trim();
  var cmd = document.getElementById('cron-cmd')?.value.trim();
  var interval = parseInt(document.getElementById('cron-interval')?.value || '60', 10);
  if (!name || !cmd) { showToast('Name and command required', 'error'); return; }
  try {
    await fetch('/api/cron', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name, command:cmd, interval:interval}) });
    showToast('Cron job added', 'success');
    showCronView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};

window.toggleCron = async function(id) {
  id = decodeURIComponent(id);
  try {
    var r = await fetch('/api/cron/' + encodeURIComponent(id) + '/toggle', { method:'POST' });
    var d = await r.json();
    showToast(d.status === 'toggled' ? 'Toggled' : (d.error || 'Failed'), 'info');
    showCronView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};

window.delCron = async function(id) {
  id = decodeURIComponent(id);
  var ok = await showConfirm('Remove scheduled task?', 'This task will be permanently deleted.', { confirmText: 'Remove', danger: true });
  if (!ok) return;
  try {
    await fetch('/api/cron/' + encodeURIComponent(id), { method:'DELETE' });
    showToast('Task removed', 'success');
    showCronView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};
