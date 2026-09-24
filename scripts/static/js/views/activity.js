/* WIDDX Nexus — Activity View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, ICON_MAP) */

async function showActivityView(area) {
  setActivity('Loading', 'activity');
  area.innerHTML = TEMPLATES.view('fa-chart-simple', 'Activity Feed', 'Real-time event log',
    '<div class="filter-bar">'
    + '<button class="filter-btn" data-click="load-activity-view"><i class="fa-solid fa-rotate"></i> Refresh</button>'
    + '<span class="text-xs text-muted">Auto-refreshes every 10s</span>'
    + '</div>'
    + '<div class="activity-feed" id="activity-feed">' + TEMPLATES.loading('Loading activity...') + '</div>'
  );

  try {
    const r = await fetch('/api/dashboard/activity?limit=50');
    var events = await r.json();
    var feed = document.getElementById('activity-feed');
    if (!feed) return;
    if (events.length) {
      feed.innerHTML = events.map(function(e) {
        var type = ICON_MAP[e.icon] || e.type || 'message';
        return '<div class="activity-item"><div class="activity-icon ' + type + '"><i class="fa-solid ' + (e.icon || 'fa-circle') + '"></i></div><div class="activity-content"><div class="activity-detail">' + escapeHtml(e.detail || '') + '</div><div class="activity-meta"><span class="activity-agent">' + escapeHtml(e.agent || 'system') + '</span><span class="activity-time">' + (e.timestamp ? new Date(e.timestamp).toLocaleString() : '') + '</span><span class="activity-status ' + (e.status || 'done') + '">' + (e.status || 'done') + '</span></div></div></div>';
      }).join('');
    } else {
      feed.innerHTML = TEMPLATES.empty('fa-inbox', 'No activity yet', 'Events will appear here as you use WIDDX.');
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    var f = document.getElementById('activity-feed');
    if (f) f.innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.loadActivityView = function() {
  var area = document.getElementById('messagesArea');
  if (area && typeof showActivityView === 'function') showActivityView(area);
};
