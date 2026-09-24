/* WIDDX Nexus — Delegation View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity) */

async function showDelegationView(area) {
  setActivity('Loading', 'delegation');
  area.innerHTML = '<div class="view-container"><div class="view-header"><h2><i class="fa-solid fa-diagram-project"></i> Delegation Network</h2><p>Sub-agents and task distribution</p></div><div class="view-body"><div class="delegation-tree" id="delegation-tree">' + TEMPLATES.loading('Loading delegation tree...') + '</div></div></div>';

  try {
    const [agentsR, bgR] = await Promise.all([
      fetch('/api/dashboard/agents'),
      fetch('/api/dashboard/background')
    ]);
    var agents = await agentsR.json();
    var bgTasks = await bgR.json();
    var tree = document.getElementById('delegation-tree');
    if (!tree) return;

    var html = '';
    html += '<div class="delegation-node"><div class="node-avatar main"><i class="fa-solid fa-w"></i></div><div class="node-info"><div class="node-title">Main Agent</div><div class="node-detail">Orchestrator \u2014 ' + (agents.length + bgTasks.length) + ' total tasks</div></div><span class="node-status running">active</span></div>';

    if (agents.length) {
      agents.forEach(function(a) {
        html += '<div class="delegation-connector"><i class="fa-solid fa-corner-down-right"></i></div>';
        html += '<div class="delegation-node"><div class="node-avatar child"><i class="fa-solid fa-robot"></i></div><div class="node-info"><div class="node-title">' + escapeHtml(a.goal || 'Sub-agent') + '</div><div class="node-detail">' + escapeHtml(a.id || '') + ' \u00b7 ' + (a.elapsed || '\u2014') + '</div></div><span class="node-status ' + (a.status || 'waiting') + '">' + (a.status || 'waiting') + '</span></div>';
      });
    }

    if (bgTasks.length) {
      bgTasks.forEach(function(t) {
        html += '<div class="delegation-connector"><i class="fa-solid fa-corner-down-right"></i></div>';
        html += '<div class="delegation-node"><div class="node-avatar child"><i class="fa-solid fa-gear"></i></div><div class="node-info"><div class="node-title">' + escapeHtml(t.summary || t.name || 'Background task') + '</div><div class="node-detail">' + escapeHtml(t.id || '') + ' \u00b7 ' + (t.elapsed || '\u2014') + '</div></div><span class="node-status ' + (t.status || 'running') + '">' + (t.status || 'running') + '</span></div>';
      });
    }

    if (!agents.length && !bgTasks.length) {
      html = '<div class="empty-state"><i class="fa-solid fa-diagram-project"></i><h3>No active delegations</h3><p>Sub-agents and background tasks will appear here when they are running.</p></div>';
    }

    tree.innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    var t2 = document.getElementById('delegation-tree');
    if (t2) t2.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Error</h3><p>' + escapeHtml(e.message) + '</p></div>';
    setActivity('Ready', '\u2014');
  }
}
