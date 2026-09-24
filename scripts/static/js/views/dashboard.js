/* WIDDX Nexus — Live Dashboard (Phase 4) */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, ICON_MAP) */

var _dashTimer = null;

async function showDashboardView(area) {
  setActivity('Loading', 'dashboard');
  area.innerHTML = '<div class="view-container"><div class="view-header"><h2><i class="fa-solid fa-gauge-high"></i> Mission Control</h2><p>Live system overview · auto-refreshes every 10s</p></div>'
    + '<div class="view-body" id="dash-body">'
    + '<div class="dashboard-grid" id="dash-stats">'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon blue"><i class="fa-solid fa-microchip"></i></div><div class="stat-value" id="dash-platform">—</div></div><div class="stat-label">Platform</div><div class="stat-detail" id="dash-detail-platform">Loading...</div></div>'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon purple"><i class="fa-solid fa-shield-halved"></i></div><div class="stat-value" id="dash-sandbox">—</div></div><div class="stat-label">Sandbox Mode</div><div class="stat-detail" id="dash-detail-sandbox">Loading...</div></div>'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon green"><i class="fa-solid fa-robot"></i></div><div class="stat-value" id="dash-agents">0</div></div><div class="stat-label">Active Agents</div><div class="stat-detail" id="dash-detail-agents">Loading...</div></div>'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon orange"><i class="fa-solid fa-clock"></i></div><div class="stat-value" id="dash-cron">0</div></div><div class="stat-label">Scheduled Tasks</div><div class="stat-detail" id="dash-detail-cron">Loading...</div></div>'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon gray"><i class="fa-solid fa-code-branch"></i></div><div class="stat-value" id="dash-git">—</div></div><div class="stat-label">Git Branch</div><div class="stat-detail" id="dash-detail-git">Loading...</div></div>'
    + '  <div class="stat-card"><div class="stat-row"><div class="stat-icon purple"><i class="fa-solid fa-coins"></i></div><div class="stat-value" id="dash-tokens">—</div></div><div class="stat-label">Token Budget</div><div class="stat-detail" id="dash-detail-tokens">Loading...</div></div>'
    + '</div>'
    + '<div class="flex gap-8 mt-8" style="align-items:stretch">'
    + '  <div class="section-card" style="flex:1">'
    + '    <div class="section-card-header flex-ac"><i class="fa-solid fa-tower-broadcast"></i> Gateway <span id="gateway-count" class="text-xs text-muted ml-auto"></span></div>'
    + '    <div class="section-card-body"><div class="gateway-grid" id="gateway-grid"><div class="empty-state" style="padding:20px"><i class="fa-solid fa-spinner fa-spin"></i><p>Loading...</p></div></div></div>'
    + '  </div>'
    + '  <div class="section-card" style="flex:1">'
    + '    <div class="section-card-header"><i class="fa-solid fa-chart-simple"></i> Resource Usage</div>'
    + '    <div class="section-card-body" id="dash-resources"><div class="text-muted text-sm">Loading...</div></div>'
    + '  </div>'
    + '</div>'
    + '<div class="section-card mt-8"><div class="section-card-header"><i class="fa-solid fa-chart-simple"></i> Recent Activity</div>'
    + '  <div class="section-card-body"><div class="activity-feed" id="dash-activity"><div class="empty-state" style="padding:20px"><i class="fa-solid fa-spinner fa-spin"></i></div></div></div>'
    + '</div>'
    + '</div></div>';

  _loadDashboard();
  _dashTimer = setInterval(_loadDashboardSilent, 10000);
}

async function _loadDashboard() {
  try {
    var [statusR, dashR, activityR, gatewayR, tokenR] = await Promise.all([
      fetch('/api/status'), fetch('/api/dashboard'),
      fetch('/api/dashboard/activity'), fetch('/api/dashboard/gateway'),
      fetch('/api/token-budget')
    ]);
    var status, dash, activity, gateway, tokens;
    try { status = await statusR.json(); } catch(e) { status = {}; }
    try { dash = await dashR.json(); } catch(e) { dash = {}; }
    try { activity = await activityR.json(); } catch(e) { activity = []; }
    try { gateway = await gatewayR.json(); } catch(e) { gateway = {channels: []}; }
    try { tokens = await tokenR.json(); } catch(e) { tokens = {}; }

    // Platform
    var el = document.getElementById('dash-platform');
    if (el) el.textContent = dash?.system?.platform?.split('-')[0] || '—';
    el = document.getElementById('dash-detail-platform');
    if (el) el.textContent = 'Python ' + (dash?.system?.python || '—') + ' · ' + (dash?.system?.cpu_count || '?') + ' cores';

    // Sandbox
    el = document.getElementById('dash-sandbox');
    if (el) el.textContent = (dash?.mode || status?.sandbox?.mode || 'auto').toUpperCase();
    el = document.getElementById('dash-detail-sandbox');
    if (el) el.textContent = 'Provider: ' + (status?.provider?.model || '—');

    // Agents
    el = document.getElementById('dash-agents');
    if (el) el.textContent = (dash?.agents?.length || 0) + (dash?.background?.length ? '+' + dash.background.length : '');
    el = document.getElementById('dash-detail-agents');
    if (el) el.textContent = (dash?.agents?.length || 0) + ' active · ' + (dash?.background?.length || 0) + ' bg tasks';

    // Cron
    el = document.getElementById('dash-cron');
    if (el) el.textContent = dash?.cron?.length || 0;
    el = document.getElementById('dash-detail-cron');
    if (el) el.textContent = (dash?.skills || 0) + ' skills · ' + (dash?.memories || 0) + ' memories';

    // Tokens
    el = document.getElementById('dash-tokens');
    var pct = tokens?.percentage || 0;
    if (el) el.textContent = pct + '%';
    el = document.getElementById('dash-detail-tokens');
    if (el) el.textContent = (tokens?.used || 0) + ' used · ' + (tokens?.remaining || 0) + ' remaining';

    // Git
    fetch('/api/git').then(function(r){return r.json()}).then(function(g){
      var de=document.getElementById('dash-detail-git'); if(!de) return;
      var info = (g.dirty ? '⚠ uncommitted' : '✓ clean') + ' — ' + (g.recent_commits||'').split('\n')[0].slice(0,7)||'';
      de.textContent = info;
      var ve=document.getElementById('dash-git');
      if(ve) ve.textContent = g.dirty ? '!' : '✓';
    }).catch(function(){});

    // Gateway
    var gwGrid = document.getElementById('gateway-grid');
    var gwCount = document.getElementById('gateway-count');
    if (gwCount) gwCount.textContent = (gateway.active_channels || gateway?.channels?.length || 0) + ' connected';
    if (gwGrid && gateway?.channels?.length) {
      gwGrid.innerHTML = gateway.channels.map(function(ch) {
        return '<div class="gateway-card"><div class="gateway-top"><span class="gateway-name">' + escapeHtml(ch.name) + '</span>'
          + '<span class="gateway-status ' + ch.status + '">' + (ch.status === 'running' ? '🟢 Live' : '⚫ Offline') + '</span></div>'
          + '<div class="gateway-meta">' + (ch.message_count || 0) + ' msgs' + (ch.last_message ? ' · ' + new Date(ch.last_message).toLocaleString() : '') + '</div></div>';
      }).join('');
    } else if (gwGrid) {
      gwGrid.innerHTML = '<div class="empty-state" style="padding:16px"><i class="fa-solid fa-plug"></i><p>No channels</p></div>';
    }

    // Activity
    var actEl = document.getElementById('dash-activity');
    if (actEl && activity?.length) {
      actEl.innerHTML = activity.slice(0, 10).map(function(e) {
        var type = ICON_MAP[e.icon] || 'message';
        return '<div class="activity-item"><div class="activity-icon ' + type + '"><i class="fa-solid ' + (e.icon || 'fa-circle') + '"></i></div>'
          + '<div class="activity-content"><div class="activity-detail">' + escapeHtml(e.detail) + '</div>'
          + '<div class="activity-meta"><span class="activity-agent">' + escapeHtml(e.agent || 'system') + '</span>'
          + '<span class="activity-time">' + (e.timestamp ? new Date(e.timestamp).toLocaleTimeString() : '') + '</span>'
          + '<span class="activity-status ' + e.status + '">' + (e.status || 'done') + '</span></div></div></div>';
      }).join('');
    } else if (actEl) {
      actEl.innerHTML = '<div class="empty-state" style="padding:16px"><i class="fa-solid fa-inbox"></i><p>No activity</p></div>';
    }

    // Resource usage bars
    _renderResources(dash);

    setActivity('Ready', '—');
  } catch(e) {
    var body = document.querySelector('.view-body');
    if (body) body.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Error</h3><p>' + escapeHtml(e.message) + '</p><button class="btn-primary mt-12" data-click="dash-retry">Retry</button></div>';
    setActivity('Ready', '—');
  }
}

function _loadDashboardSilent() {
  _loadDashboard();
}

function _renderResources(dash) {
  var el = document.getElementById('dash-resources');
  if (!el) return;
  var agents = dash?.agents?.length || 0;
  var bg = dash?.background?.length || 0;
  var skills = dash?.skills || 0;
  var cron = dash?.cron?.length || 0;
  var mem = dash?.system?.mem_usage || 0;

  el.innerHTML = ''
    + '<div class="mb-4"><div class="flex-ac-sb text-xs"><span>Agents</span><span>' + agents + '</span></div><div class="dash-bar-bg"><div class="dash-bar green" style="width:' + Math.min(agents * 20, 100) + '%"></div></div></div>'
    + '<div class="mb-4"><div class="flex-ac-sb text-xs"><span>Background Tasks</span><span>' + bg + '</span></div><div class="dash-bar-bg"><div class="dash-bar blue" style="width:' + Math.min(bg * 20, 100) + '%"></div></div></div>'
    + '<div class="mb-4"><div class="flex-ac-sb text-xs"><span>Skills</span><span>' + skills + '</span></div><div class="dash-bar-bg"><div class="dash-bar purple" style="width:' + Math.min(skills * 10, 100) + '%"></div></div></div>'
    + '<div class="mb-4"><div class="flex-ac-sb text-xs"><span>Cron Jobs</span><span>' + cron + '</span></div><div class="dash-bar-bg"><div class="dash-bar orange" style="width:' + Math.min(cron * 20, 100) + '%"></div></div></div>'
    + (mem ? '<div class="mb-4"><div class="flex-ac-sb text-xs"><span>Memory</span><span>' + mem + '</span></div><div class="dash-bar-bg"><div class="dash-bar purple" style="width:' + Math.min(parseInt(mem)||0, 100) + '%"></div></div></div>' : '');
}

// Register handler
if (typeof CLICK_HANDLERS !== 'undefined') {
  CLICK_HANDLERS['dash-retry'] = function() { _loadDashboard(); };
}
