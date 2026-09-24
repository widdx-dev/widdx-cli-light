/* WIDDX Nexus — Workflows View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showToast) */

async function showWorkflowsView(area) {
  setActivity('Loading', 'workflows');
  area.innerHTML = TEMPLATES.view('fa-diagram-project', 'Workflows', 'Automated multi-step processes',
    '<div style="display:flex;gap:8px;margin-bottom:12px">'
    + '<input id="wf-name" style="flex:1;background:var(--bg-input);border:1px solid var(--border-main);border-radius:6px;color:var(--text-primary);padding:6px 10px;font-size:13px" placeholder="Workflow name">'
    + '<input id="wf-steps" style="flex:2;background:var(--bg-input);border:1px solid var(--border-main);border-radius:6px;color:var(--text-primary);padding:6px 10px;font-size:13px" placeholder="Steps (comma-separated): research, code, review">'
    + '<button class="send-btn" style="width:auto;padding:0 16px;border-radius:6px" data-click="create-workflow">Create</button>'
    + '</div>'
    + '<div id="workflow-list">Loading...</div>'
  );
  try {
    const r = await fetch('/api/workflows');
    const workflows = await r.json();
    const el = document.getElementById('workflow-list');
    if (Array.isArray(workflows) && workflows.length) {
      el.innerHTML = workflows.map(function(w) {
        const id = w.id || '';
        const name = w.name || 'Untitled';
        const steps = w.steps || [];
        return '<div class="flex-ac-sb py-8 border-bottom-light">'
          + '<div><strong>' + escapeHtml(name) + '</strong><br><span style="font-size:11px;color:var(--text-muted)">' + (Array.isArray(steps) ? steps.join(' \u2192 ') : (steps || '')) + '</span></div>'
          + '<div><button class="btn-icon-success" data-click="run-workflow" data-workflow="' + encodeURIComponent(id) + '" title="Run">\u25b6</button></div></div>';
      }).join('');
    } else {
      el.innerHTML = '<span style="color:var(--text-muted)">No workflows created yet</span>';
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    const el = document.getElementById('workflow-list');
    if (el) el.innerHTML = '<span style="color:var(--error)">' + escapeHtml(e.message) + '</span>';
    setActivity('Ready', '\u2014');
  }
}

window.createWorkflow = async function() {
  const name = document.getElementById('wf-name')?.value.trim();
  const steps = document.getElementById('wf-steps')?.value.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
  if (!name || !steps?.length) { showToast('Name and steps required', 'error'); return; }
  try {
    await fetch('/api/workflows', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name, steps:steps}) });
    showToast('Workflow created', 'success');
    showWorkflowsView(document.getElementById('messagesArea'));
  } catch(e) { showToast(e.message, 'error'); }
};

window.runWorkflow = async function(idEncoded) {
  const id = decodeURIComponent(idEncoded);
  try {
    showToast('Running workflow...', 'info');
    const r = await fetch('/api/workflows/' + encodeURIComponent(id) + '/run', { method:'POST' });
    const d = await r.json();
    showToast(d.status === 'completed' ? 'Workflow completed' : (d.error || 'Failed'), d.status === 'completed' ? 'success' : 'error');
  } catch(e) { showToast(e.message, 'error'); }
};
