/* WIDDX Nexus — Token Budget View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

async function showTokenBudgetView(area) {
  setActivity('Loading', 'token budget');
  area.innerHTML = TEMPLATES.view('fa-coins', 'Token Budget', 'Monitor and manage token usage',
    '<div id="token-budget-content">' + TEMPLATES.loading('Loading token budget...') + '</div>'
  );
  try {
    const r = await fetch('/api/token-budget');
    const d = await r.json();
    var used = d.used || 0;
    var limit = d.limit || 0;
    var remaining = d.remaining || 0;
    var pct = d.percentage || 0;
    var html = ''
      + '<div class="settings-card">'
      + '<div class="flex mb-8" style="justify-content:space-between">'
      + '<span class="text-secondary text-sm">Used</span>'
      + '<strong class="text-primary">' + used.toLocaleString() + '</strong></div>'
      + '<div style="background:var(--fill-active);border-radius:var(--radius-full);height:10px;overflow:hidden">'
      + '<div style="width:' + Math.min(pct, 100) + '%;height:100%;background:' + (pct > 80 ? 'var(--error)' : pct > 50 ? 'var(--warning)' : 'var(--success)') + ';border-radius:var(--radius-full);transition:width 0.5s"></div></div>'
      + '<div class="flex text-xs" style="justify-content:space-between;margin-top:6px">'
      + '<span style="color:var(--text-tertiary)">' + pct + '% used</span>'
      + '<span style="color:var(--text-tertiary)">' + remaining.toLocaleString() + ' remaining</span>'
      + '</div></div>'
      + '<div class="settings-card">'
      + '<div class="flex" style="justify-content:space-between">'
      + '<span class="text-secondary">Limit</span>'
      + '<strong class="text-primary">' + (limit ? limit.toLocaleString() : 'Unlimited') + '</strong>'
      + '</div></div>'
      + '<button data-click="reset-token-budget" class="btn-primary" style="background:var(--warning);color:#000"><i class="fa-solid fa-rotate"></i> Reset Budget</button>'
      + '<span id="token-budget-status" class="text-sm text-muted" style="margin-left:12px"></span>';
    document.getElementById('token-budget-content').innerHTML = html;
    setActivity('Ready', '\u2014');
  } catch(e) {
    document.getElementById('token-budget-content').innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.resetTokenBudget = async function() {
  var ok = await showConfirm('Reset token budget?', 'All token usage counters will be reset to zero.', { confirmText: 'Reset', danger: true });
  if (!ok) return;
  var status = document.getElementById('token-budget-status');
  if (status) status.textContent = 'Resetting...';
  try {
    var r = await fetch('/api/token-budget/reset', { method:'POST' });
    var d = await r.json();
    if (status) status.textContent = d.status === 'reset' ? '\u2713 Reset' : '\u2717 ' + (d.error || 'Failed');
    if (d.status === 'reset') { showToast('Token budget reset', 'success'); showTokenBudgetView(document.getElementById('messagesArea')); }
  } catch(e) { if (status) status.textContent = '\u2717 ' + e.message; showToast(e.message, 'error'); }
};
