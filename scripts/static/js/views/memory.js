/* WIDDX Nexus — Memory View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

var _allMemories = [];

async function showMemoryView(area) {
  setActivity('Loading', 'memories');
  area.innerHTML = TEMPLATES.view('fa-brain', 'Memory Vault', 'Persistent knowledge store',
    '<div class="settings-card mb-12">'
    + '<div class="settings-card-label"><i class="fa-solid fa-plus"></i> Add Memory</div>'
    + '<div class="flex gap-8">'
    + '<input id="mem-content" class="settings-input flex-2" placeholder="Memory content...">'
    + '<input id="mem-tags" class="settings-input flex-1" placeholder="Tags (optional)">'
    + '<button data-click="add-memory" class="send-btn w-auto px-8 rounded-6">Add</button>'
    + '</div></div>'
    + TEMPLATES.filterBar('memory-search', 'Search memories...',
      '<button class="filter-btn" data-click="load-memory-view"><i class="fa-solid fa-rotate"></i> Refresh</button>',
      'filterMemoryView(this.value)')
    + '<div id="memory-list">' + TEMPLATES.loading('Loading memories...') + '</div>'
  );

  try {
    const r = await fetch('/api/dashboard/memories');
    var mems = await r.json();
    renderMemoryList(mems);
    setActivity('Ready', '\u2014');
  } catch(e) {
    var ml = document.getElementById('memory-list');
    if (ml) ml.innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.addMemory = async function() {
  var content = document.getElementById('mem-content')?.value.trim();
  var tags = document.getElementById('mem-tags')?.value.trim();
  if (!content) { showToast('Please enter memory content', 'error'); return; }
  try {
    var r = await fetch('/api/memories', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({content:content, tags:tags}) });
    var d = await r.json();
    showToast(d.status === 'ok' ? 'Memory added' : (d.error || 'Failed'), d.status === 'ok' ? 'success' : 'error');
    if (d.status === 'ok') {
      document.getElementById('mem-content').value = '';
      document.getElementById('mem-tags').value = '';
      loadMemoryView();
    }
  } catch(e) { showToast(e.message, 'error'); }
};

window.delMemory = async function(id) {
  if (!id) return;
  var ok = await showConfirm('Delete memory?', 'This memory entry will be permanently removed.', { confirmText: 'Delete', danger: true });
  if (!ok) return;
  try {
    var r = await fetch('/api/memories/' + encodeURIComponent(id), { method:'DELETE' });
    var d = await r.json();
    showToast(d.status === 'deleted' ? 'Memory deleted' : (d.error || 'Failed'), 'info');
    loadMemoryView();
  } catch(e) { showToast(e.message, 'error'); }
};

function renderMemoryList(mems) {
  _allMemories = mems || [];
  var el = document.getElementById('memory-list');
  if (!el) return;
  if (!mems.length) {
    el.innerHTML = '<div class="empty-state" style="padding:24px"><i class="fa-solid fa-brain"></i><h3>No memories yet</h3><p>Use the form above to add a memory, or they are saved automatically.</p></div>';
    return;
  }
  el.innerHTML = '<div class="flex flex-col gap-4">' + mems.map(function(m) {
    var id = m.id || m.memory_id || '';
    var target = m.name || m.fact || m.target || 'memory';
    var content = (m.description || m.content || m.value || '')?.slice(0, 120);
    return '<div class="activity-item memory-item">'
      + '<div class="activity-icon system"><i class="fa-solid fa-brain"></i></div>'
      + '<div class="activity-content"><div class="activity-detail text-bold text-primary">' + escapeHtml(target) + '</div>'
      + '<div class="activity-meta"><span class="activity-agent">' + escapeHtml(content) + '</span></div></div>'
      + (id ? '<button data-click="del-memory" data-memory="' + escapeHtml(id) + '" class="btn-icon-error text-12 flex-shrink-0" title="Delete">✕</button>' : '')
      + '</div>';
  }).join('') + '</div>';
}

window.filterMemoryView = async function(query) {
  var q = (query || '').trim();
  if (!q) {
    renderMemoryList(_allMemories);
    return;
  }
  try {
    var r = await fetch('/api/memories/search?q=' + encodeURIComponent(q));
    var results = await r.json();
    renderMemoryList(Array.isArray(results) ? results : []);
  } catch(e) {
    // Fallback to client-side search
    var filtered = _allMemories.filter(function(m) {
      var text = ((m.name || m.target || m.fact || '') + ' ' + (m.description || m.content || m.value || '')).toLowerCase();
      return text.indexOf(q.toLowerCase()) !== -1;
    });
    renderMemoryList(filtered);
  }
};

window.loadMemoryView = function() {
  var area = document.getElementById('messagesArea');
  if (area && typeof showMemoryView === 'function') showMemoryView(area);
};
