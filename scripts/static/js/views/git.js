/* WIDDX Nexus — Git Panel (Phase 4) */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

var _gitCurrentBranch = '';

async function showGitView(area) {
  setActivity('Loading', 'git');
  area.innerHTML = TEMPLATES.view('fa-code-branch', 'Git Panel', 'Full source control management',
    '<div class="flex gap-8 mb-12" style="flex-wrap:wrap">'
    + '<button class="send-btn w-auto rounded-6" style="padding:6px 16px" data-click="git-refresh"><i class="fa-solid fa-rotate"></i> Refresh</button>'
    + '<button class="send-btn w-auto rounded-6" style="padding:6px 16px;background:var(--accent);color:#fff" data-click="git-push"><i class="fa-solid fa-cloud-arrow-up"></i> Push</button>'
    + '<button class="send-btn w-auto rounded-6" style="padding:6px 16px;background:var(--text-secondary);color:#fff" data-click="git-pull"><i class="fa-solid fa-cloud-arrow-down"></i> Pull</button>'
    + '<button class="send-btn w-auto rounded-6" style="padding:6px 16px;background:var(--error);color:#fff" data-click="git-undo"><i class="fa-solid fa-rotate-left"></i> Undo Last Commit</button>'
    + '</div>'
    + '<div class="flex gap-8" style="align-items:stretch">'
    + '  <div style="flex:1">'
    + '    <div id="git-status" class="settings-card">Loading status...</div>'
    + '    <div id="git-commit-area" class="settings-card mt-8" style="display:none">'
    + '      <div class="settings-card-label">✏️ Commit</div>'
    + '      <textarea id="git-commit-msg" class="settings-input resize-v" style="min-height:60px;padding:8px;font-size:13px" placeholder="Commit message (leave blank for auto)..."></textarea>'
    + '      <div class="mt-8"><button class="send-btn w-auto rounded-6" style="padding:6px 20px;background:var(--accent);color:#fff" data-click="git-commit"><i class="fa-solid fa-check"></i> Commit</button>'
    + '      <span id="git-commit-status" class="text-sm text-muted ml-8"></span></div>'
    + '    </div>'
    + '  </div>'
    + '  <div style="flex:0 0 240px">'
    + '    <div class="settings-card" style="height:100%">'
    + '      <div class="settings-card-label">🌿 Branches</div>'
    + '      <div id="git-branches" class="text-sm" style="max-height:260px;overflow-y:auto">Loading...</div>'
    + '      <div class="flex gap-4 mt-8"><input id="git-new-branch" class="settings-input text-12" style="flex:1" placeholder="New branch name">'
    + '      <button class="send-btn w-auto rounded-6 text-12" style="padding:4px 10px" data-click="git-create-branch">Create</button></div>'
    + '    </div>'
    + '  </div>'
    + '</div>'
    + '<div id="git-history" class="settings-card mt-8">'
    + '  <div class="settings-card-label">📜 Recent Commits</div>'
    + '  <div id="git-commits">Loading...</div>'
    + '</div>'
    + '<div id="git-diff-area" class="settings-card mt-8" style="display:none">'
    + '  <div class="settings-card-label flex-ac"><span>📄 Diff: <span id="git-diff-file"></span></span>'
    + '  <button class="send-btn w-auto rounded-6 text-12" style="padding:2px 8px;margin-left:auto" data-click="git-close-diff">✕ Close</button></div>'
    + '  <div id="git-diff-content" class="text-12 text-mono overflow-auto" style="max-height:400px;padding:8px;background:var(--bg-input);border-radius:4px"></div>'
    + '</div>'
  );
  await _gitRefreshAll();
  setActivity('Ready', '\u2014');
}

async function _gitRefreshAll() {
  try {
    var [r1, r2] = await Promise.all([
      fetch('/api/git'),
      fetch('/api/git/branches'),
    ]);
    var status = await r1.json();
    var branches = await r2.json();
    _gitRenderStatus(status);
    _gitRenderBranches(branches);
    _gitRenderHistory(status.recent_commits);
  } catch(e) {
    document.getElementById('git-status').innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  }
}

function _gitRenderStatus(status) {
  var el = document.getElementById('git-status');
  if (!el) return;

  var changes = status.changes || '';
  var branch = (status.branch || '').replace(/^\*\s*/, '');
  _gitCurrentBranch = branch;

  var fileList = '';
  if (changes) {
    var files = changes.split('\n').filter(Boolean);
    fileList = files.map(function(f) {
      var match = f.match(/^([ MARCUD?!])\s+(.+)/);
      if (!match) return '<div class="py-4 text-12 text-secondary">' + escapeHtml(f) + '</div>';
      var code = match[1].trim();
      var path = match[2];
      var icon = code === 'M' ? '✏️' : code === 'A' ? '➕' : code === 'D' ? '🗑️' : code === '?' ? '❓' : code === '!' ? '⚠️' : '📄';
      var cls = code === 'M' ? 'text-warning' : code === 'A' ? 'text-success' : code === 'D' ? 'text-error' : 'text-muted';
      return '<div class="flex-ac gap-4 py-2 git-file-item" data-file="' + escapeHtml(path) + '" style="cursor:pointer;padding:2px 4px;border-radius:3px">'
        + '<input type="checkbox" class="git-stage-cb" data-file="' + escapeHtml(path) + '" checked>'
        + '<span class="' + cls + ' text-12" style="width:20px">' + icon + '</span>'
        + '<span class="flex-1 text-12">' + escapeHtml(path) + '</span>'
        + '<span class="text-xs text-muted git-diff-btn" data-file="' + escapeHtml(path) + '" style="cursor:pointer;padding:0 4px" title="View diff">↕</span>'
        + '</div>';
    }).join('');
  } else {
    fileList = '<div class="text-muted text-sm py-4">✓ No uncommitted changes</div>';
  }

  el.innerHTML = '<div class="flex-ac-sb mb-4">'
    + '<span><strong class="text-primary">🌿 ' + escapeHtml(branch) + '</strong>'
    + (status.ahead ? ' <span class="text-sm text-muted">· ' + (status.ahead || 0) + ' ahead</span>' : '')
    + '</span>'
    + '<span class="text-xs text-muted">' + (status.commits || 0) + ' commits</span>'
    + '</div>'
    + '<div class="git-files">' + fileList + '</div>';

  // Show commit area if there are changes
  var commitArea = document.getElementById('git-commit-area');
  if (commitArea) {
    commitArea.style.display = files && files.length ? 'block' : 'none';
  }
}

function _gitRenderBranches(branches) {
  var el = document.getElementById('git-branches');
  if (!el) return;
  if (!Array.isArray(branches) || !branches.length) {
    el.innerHTML = '<span class="text-muted">No branches</span>';
    return;
  }
  el.innerHTML = branches.map(function(b) {
    var name = b.name || '';
    var current = b.current || false;
    return '<div class="flex-ac-sb py-2 ' + (current ? 'text-accent text-semibold' : 'text-secondary') + '">'
      + '<span>' + (current ? '● ' : '') + escapeHtml(name) + '</span>'
      + (!current ? '<button class="git-switch-btn text-xs text-muted bg-none border-none cursor-pointer" data-branch="' + escapeHtml(name) + '" title="Switch">↩</button>' : '')
      + '</div>';
  }).join('');
}

function _gitRenderHistory(commits) {
  var el = document.getElementById('git-commits');
  if (!el) return;
  if (!commits || commits === 'No commits') {
    el.innerHTML = '<span class="text-muted text-sm">No commits yet</span>';
    return;
  }
  var lines = String(commits).split('\n').filter(Boolean);
  el.innerHTML = '<div class="text-12 text-mono" style="max-height:300px;overflow-y:auto">'
    + lines.map(function(l) {
      var m = l.match(/^([a-f0-9]{7,})\s+(.+)/);
      if (m) {
        return '<div class="py-1 border-bottom-light"><span class="text-accent">' + m[1] + '</span> <span class="text-secondary">' + escapeHtml(m[2]) + '</span></div>';
      }
      return '<div class="py-1 text-secondary">' + escapeHtml(l) + '</div>';
    }).join('') + '</div>';
}

// ── Handlers ──
async function _gitCommit() {
  var msg = document.getElementById('git-commit-msg')?.value.trim();
  var statusEl = document.getElementById('git-commit-status');
  if (statusEl) statusEl.textContent = 'Committing...';

  // Collect staged files
  var cbs = document.querySelectorAll('.git-stage-cb:checked');
  var files = Array.from(cbs).map(function(cb) { return cb.getAttribute('data-file'); }).filter(Boolean);

  try {
    var r = await fetch('/api/git/commit', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({message: msg || 'Auto-commit from WIDDX Nexus', files: files.length ? files : undefined})
    });
    var d = await r.json();
    if (d.status === 'committed') {
      if (statusEl) { statusEl.textContent = '✅ Committed'; statusEl.style.color = 'var(--success)'; }
      document.getElementById('git-commit-msg').value = '';
      showToast('Committed: ' + (d.hash || ''), 'success');
      _gitRefreshAll();
    } else {
      if (statusEl) { statusEl.textContent = '❌ ' + (d.error || 'Failed'); statusEl.style.color = 'var(--error)'; }
    }
  } catch(e) {
    if (statusEl) { statusEl.textContent = '❌ ' + e.message; statusEl.style.color = 'var(--error)'; }
  }
}

async function _gitPush() {
  try {
    showToast('Pushing...', 'info');
    var r = await fetch('/api/git/push', { method: 'POST' });
    var d = await r.json();
    showToast(d.status === 'pushed' ? 'Pushed ✓' : (d.error || 'Push failed'), d.status === 'pushed' ? 'success' : 'error');
    _gitRefreshAll();
  } catch(e) { showToast('Push error: ' + e.message, 'error'); }
}

async function _gitPull() {
  try {
    showToast('Pulling...', 'info');
    var r = await fetch('/api/git/pull', { method: 'POST' });
    var d = await r.json();
    showToast(d.status === 'pulled' ? 'Pulled ✓' : (d.error || 'Pull failed'), d.status === 'pulled' ? 'success' : 'error');
    _gitRefreshAll();
  } catch(e) { showToast('Pull error: ' + e.message, 'error'); }
}

async function _gitCreateBranch() {
  var name = document.getElementById('git-new-branch')?.value.trim();
  if (!name) { showToast('Enter a branch name', 'error'); return; }
  try {
    var r = await fetch('/api/git/branch', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name, from: _gitCurrentBranch})
    });
    var d = await r.json();
    showToast(d.status === 'created' ? 'Branch created: ' + name : (d.error || 'Failed'), d.status === 'created' ? 'success' : 'error');
    if (d.status === 'created') { document.getElementById('git-new-branch').value = ''; _gitRefreshAll(); }
  } catch(e) { showToast(e.message, 'error'); }
}

async function _gitSwitchBranch(name) {
  try {
    var r = await fetch('/api/git/checkout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({branch: name})
    });
    var d = await r.json();
    showToast(d.status === 'switched' ? 'Switched to ' + name : (d.error || 'Failed'), d.status === 'switched' ? 'success' : 'error');
    if (d.status === 'switched') _gitRefreshAll();
  } catch(e) { showToast(e.message, 'error'); }
}

async function _gitShowDiff(filePath) {
  var diffArea = document.getElementById('git-diff-area');
  var diffFile = document.getElementById('git-diff-file');
  var diffContent = document.getElementById('git-diff-content');
  if (!diffArea || !diffFile || !diffContent) return;
  diffArea.style.display = 'block';
  diffFile.textContent = filePath;
  diffContent.innerHTML = '<span class="text-muted"><i class="fa-solid fa-spinner fa-spin"></i> Loading diff...</span>';
  try {
    var r = await fetch('/api/git/diff?file=' + encodeURIComponent(filePath));
    var d = await r.json();
    diffContent.innerHTML = d.diff ? '<pre class="text-12" style="margin:0;white-space:pre-wrap">' + escapeHtml(d.diff) + '</pre>' : '<span class="text-muted">No diff available</span>';
  } catch(e) {
    diffContent.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  }
}

// ── Register CLICK_HANDLERS ──
CLICK_HANDLERS['git-refresh'] = function() { _gitRefreshAll(); };
CLICK_HANDLERS['git-commit'] = function() { _gitCommit(); };
CLICK_HANDLERS['git-push'] = function() { _gitPush(); };
CLICK_HANDLERS['git-pull'] = function() { _gitPull(); };
CLICK_HANDLERS['git-undo'] = function() { _gitUndo(); };
CLICK_HANDLERS['git-create-branch'] = function() { _gitCreateBranch(); };
CLICK_HANDLERS['git-close-diff'] = function() {
  var a = document.getElementById('git-diff-area');
  if (a) a.style.display = 'none';
};

// ── Event delegation for branch switch + diff ──
document.addEventListener('click', function(e) {
  var btn = e.target.closest('.git-switch-btn');
  if (btn) { _gitSwitchBranch(btn.getAttribute('data-branch')); return; }
  var diffBtn = e.target.closest('.git-diff-btn');
  if (diffBtn) { _gitShowDiff(diffBtn.getAttribute('data-file')); return; }
  var fileItem = e.target.closest('.git-file-item');
  if (fileItem && !e.target.closest('input,button,span')) {
    var cb = fileItem.querySelector('.git-stage-cb');
    if (cb) cb.checked = !cb.checked;
  }
});

// Keep backward compat
window.refreshGitView = _gitRefreshAll;

async function _gitUndo() {
  var ok = await showConfirm('Undo last commit?', 'This does a soft reset — your working changes will be kept.', { confirmText: 'Undo', danger: true });
  if (!ok) return;
  try {
    var r = await fetch('/api/git/undo', { method:'POST' });
    var d = await r.json();
    showToast(d.status === 'undone' ? 'Last commit undone' : (d.error || 'Failed'), d.status === 'undone' ? 'success' : 'error');
    await _gitRefreshAll();
  } catch(e) { showToast(e.message, 'error'); }
}
