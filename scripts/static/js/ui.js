/* WIDDX Nexus — UI Interactions & Helpers */

// ═══════════════ THEME ═══════════════════

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('widdx-theme', next);
}

(function initTheme() {
  const saved = localStorage.getItem('widdx-theme');
  if (saved) document.documentElement.setAttribute('data-theme', saved);
})();

// ═══════════════ SIDEBAR ═══════════════════

function toggleSidebar() {
  var sb = document.getElementById('sidebar');
  sb.classList.toggle('collapsed');
  document.body.classList.toggle('sidebar-collapsed', sb.classList.contains('collapsed'));
}

function toggleMobileSidebar() {
  var sb = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebarBackdrop');
  sb.classList.add('open');
  if (backdrop) backdrop.classList.add('show');
  document.body.style.overflow = 'hidden';
}

function closeMobileSidebar() {
  var sb = document.getElementById('sidebar');
  var backdrop = document.getElementById('sidebarBackdrop');
  sb.classList.remove('open');
  if (backdrop) backdrop.classList.remove('show');
  document.body.style.overflow = '';
}

// ═══════════════ COMPUTER PANEL ═══════════════════

function toggleComputer() {
  const panel = document.getElementById('computerPanel');
  const isCollapsed = panel.classList.toggle('collapsed');
  // Sync the desktop button in the activity bar
  const btn = document.querySelector('[data-click="toggle-computer"]');
  if (btn) btn.classList.toggle('active', !isCollapsed);
  // Stop process auto-refresh when panel is closed
  if (isCollapsed && typeof _stopProcessAutoRefresh === 'function') {
    _stopProcessAutoRefresh();
  }
  // When opening: always (re)render the active tab content
  if (!isCollapsed && typeof showTerminal === 'function') {
    var activeTab = document.querySelector('.right-panel-tab.active');
    var view = activeTab ? activeTab.getAttribute('data-tab') : 'terminal';
    if (view === 'terminal') showTerminal();
    else if (view === 'browser' && typeof showBrowser === 'function') showBrowser();
    else if (view === 'processes' && typeof showProcessManager === 'function') showProcessManager();
    else if (view === 'screenshot' && typeof showScreenshot === 'function') showScreenshot();
    else showTerminal();
  }
}

// ═══════════════ STEP CARDS ═══════════════════

function toggleStep(head) {
  var isOpen = head.classList.toggle('open');
  var body = head.nextElementSibling;
  if (body) body.classList.toggle('open');
  head.setAttribute('aria-expanded', isOpen);
}

document.addEventListener('click', function(e) {
  var step = e.target.closest('.step-head');
  if (step) toggleStep(step);
  var copyCode = e.target.closest('[data-click="copy-code"]');
  if (copyCode) copyCodeBlock(copyCode);
  var copyCard = e.target.closest('[data-click="copy-card-path"]');
  if (copyCard) copyCardPath(copyCard);
});

document.addEventListener('keydown', function(e) {
  if (e.key === 'Enter' || e.key === ' ') {
    var step = document.activeElement?.closest('.step-head');
    if (step) { e.preventDefault(); toggleStep(step); }
  }
});

// ═══════════════ SEARCH ═══════════════════

var searchTimeout;
var searchInput = document.getElementById('sidebarSearch');
if (searchInput) {
  searchInput.addEventListener('input', function(e) {
    clearTimeout(searchTimeout);
    searchTimeout = setTimeout(function() {
      filterConversations(e.target.value);
    }, 200);
  });
}

function filterConversations(query) {
  query = query.toLowerCase().trim();
  var items = document.querySelectorAll('.chat-item');
  var sections = document.querySelectorAll('.nav-section-label');
  var visibleCount = 0;
  items.forEach(function(item) {
    var title = (item.querySelector('.chat-item-title') || {}).textContent || '';
    if (!query || title.toLowerCase().includes(query)) {
      item.style.display = '';
      visibleCount++;
    } else {
      item.style.display = 'none';
    }
  });
  sections.forEach(function(s) {
    if (s.textContent.trim() === 'Recent') {
      s.style.display = (!query || visibleCount > 0) ? '' : 'none';
    }
  });
}

// ═══════════════ DRAFT AUTO-SAVE ═══════════════════

var draftKey = 'widdx-draft';
var draftInput = document.getElementById('messageInput');
if (draftInput) {
  var saved = localStorage.getItem(draftKey);
  if (saved) {
    draftInput.value = saved;
    draftInput.style.height = 'auto';
    draftInput.style.height = Math.min(draftInput.scrollHeight, 200) + 'px';
  }
  setInterval(function() {
    var val = draftInput.value;
    if (val.trim()) {
      localStorage.setItem(draftKey, val);
    } else {
      localStorage.removeItem(draftKey);
    }
  }, 3000);
}

// ═══════════════ KEYBOARD SHORTCUTS ═══════════════════

document.addEventListener('keydown', (e) => {
  const tag = document.activeElement?.tagName;
  const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable;

  if ((e.ctrlKey || e.metaKey) && e.key === 'b') { e.preventDefault(); toggleSidebar(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'j') { e.preventDefault(); toggleComputer(); }
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    if (!isInput) toggleCommandPalette();
  }
  if ((e.ctrlKey || e.metaKey) && e.key === 'n') { e.preventDefault(); newConversation(); }
  if (e.key === 'Escape') {
    const palette = document.getElementById('cmdPaletteOverlay');
    if (palette && palette.classList.contains('show')) { closeCommandPalette(); return; }
    const panel = document.getElementById('computerPanel');
    if (panel && !panel.classList.contains('collapsed')) { toggleComputer(); if(typeof showToast==='function')showToast('Panel closed', 'info'); }
  }
});

// ═══════════════ SCROLL TO BOTTOM ═══════════════════

(function initScrollBtn() {
  const area = document.getElementById('messagesArea');
  const btn = document.getElementById('scrollBottomBtn');
  if (area && btn) {
    area.addEventListener('scroll', function() {
      var dist = area.scrollHeight - area.scrollTop - area.clientHeight;
      btn.classList.toggle('visible', dist > 200);
    });
  }
})();

// ═══════════════ TEXTAREA AUTO-RESIZE ═══════════════════

const textarea = document.getElementById('messageInput');
if (textarea) {
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  });
}

// ═══════════════ TOAST ═══════════════════

function showToast(message, type) {
  type = type || 'info';
  var container = document.getElementById('toastContainer');
  if (!container) return;
  var toast = document.createElement('div');
  toast.className = 'toast ' + type;
  var icon = type === 'success' ? 'fa-circle-check' : type === 'error' ? 'fa-circle-xmark' : 'fa-circle-info';
  toast.innerHTML = '<i class="fa-solid ' + icon + '"></i> ' + escapeHtml(message);
  container.appendChild(toast);
  setTimeout(function() {
    if (toast.parentNode) toast.parentNode.removeChild(toast);
  }, 4000);  // 4 seconds for readability
}

// ═══════════════ CODE BLOCK COPY ═══════════════════

function copyCodeBlock(btn) {
  var wrapper = btn.closest('.code-block-wrapper');
  var code = wrapper ? wrapper.querySelector('pre') || wrapper.querySelector('code') : null;
  var text = code ? code.textContent : '';
  navigator.clipboard.writeText(text).then(function() {
    btn.classList.add('copied');
    var icon = btn.querySelector('i');
    if (icon) { icon.className = 'fa-solid fa-check'; }
    showToast('Code copied', 'success');
    setTimeout(function() { btn.classList.remove('copied'); if (icon) icon.className = 'fa-solid fa-copy'; }, 2000);
  });
}

function copyCardPath(btn) {
  var card = btn.closest('.tool-card');
  var pathEl = card ? card.querySelector('.tool-card-path') : null;
  var text = pathEl ? pathEl.textContent : '';
  navigator.clipboard.writeText(text).then(function() {
    btn.classList.add('copied');
    showToast('Path copied', 'success');
    setTimeout(function() { btn.classList.remove('copied'); }, 2000);
  });
}

// ═══════════════ HELPERS ═══════════════════

function escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

// ═══════════════ MARKDOWN ═══════════════════
// Canonical markdown parser — used by both ui.js and nexus.js
// NOTE: Every regex callback MUST escape captured groups before inserting into HTML.

/** Tag-stripping sanitizer — removes script, style, event handlers, and XSS vectors */
function _sanitizeHtml(html) {
  return html
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
    .replace(/<style\b[^<]*(?:(?!<\/style>)<[^<]*)*<\/style>/gi, '')
    // Event handlers: onfocus, onerror, onload, onmouseover, onclick, etc.
    .replace(/\bon\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    // javascript: URI — handles line breaks and HTML entities between 'java' and 'script'
    .replace(/j[\s\n]*a[\s\n]*v[\s\n]*a[\s\n]*s[\s\n]*c[\s\n]*r[\s\n]*i[\s\n]*p[\s\n]*t\s*:/gi, 'blocked:')
    // data: URIs that could execute (e.g. data:text/html)
    .replace(/data\s*:\s*text\/html/gi, 'blocked:');
}

// ── Table renderer ──
function _renderTables(h) {
  var lines = h.split('\n'), out = [], rows = [], inTbl = false;
  for (var i = 0; i < lines.length; i++) {
    var l = lines[i].trim();
    if (l.startsWith('|') && l.endsWith('|')) {
      if (!inTbl) { inTbl = true; rows = []; }
      rows.push(l);
    } else {
      if (inTbl) { out.push(_buildTable(rows)); rows = []; inTbl = false; }
      out.push(lines[i]);
    }
  }
  if (inTbl) out.push(_buildTable(rows));
  return out.join('\n');
}
function _buildTable(rows) {
  if (rows.length < 2) return rows.join('\n');
  var h = '<table class="md-table"><thead><tr>';
  var hc = rows[0].split('|').filter(function(c) { return c.trim(); });
  h += hc.map(function(c) { return '<th>' + escapeHtml(c.trim()) + '</th>'; }).join('') + '</tr></thead><tbody>';
  for (var i = 1; i < rows.length; i++) {
    if (rows[i].match(/^\|[-: |]+\|$/)) continue;
    var c = rows[i].split('|').filter(function(x) { return x.trim(); });
    h += '<tr>' + c.map(function(x) { return '<td>' + escapeHtml(x.trim()) + '</td>'; }).join('') + '</tr>';
  }
  return h + '</tbody></table>';
}
// ── Collapsible sections ──
function _renderCollapsibleSections(h) {
  return h.replace(/(<h[34]>)(.+?)(<\/h[34]>)([\s\S]*?)(?=<h[34]>|$)/g, function(_, ot, title, ct, body) {
    if (!body.trim() || body.length < 100) return ot + title + ct + body;
    var id = 'sec-' + Math.random().toString(36).substr(2, 9);
    return ot + title + ct + '<details class="collapsible-section" open><summary class="section-summary">' + escapeHtml(title.replace(/<[^>]+>/g,'')) + '</summary><div class="section-body">' + body + '</div></details>';
  });
}

function parseMarkdown(text) {
  if (!text) return '';
  // Decode common HTML entities so markdown patterns can match.
  // Order matters: &amp; first so &amp;lt; becomes &lt; then <
  var html = String(text)
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
  // Strip raw dangerous HTML before anything else
  html = _sanitizeHtml(html);

  // Strip thinking tags (both bracketed and XML literal/escaped forms)
  html = html.replace(/\[?\/?thinking\]?/gi, '');
  html = html.replace(/<thinking>/gi, '').replace(/<\/thinking>/gi, '');
  html = html.replace(/&lt;thinking&gt;/gi, '').replace(/&lt;\/thinking&gt;/gi, '');

  // Fenced code blocks — escape captured groups in callback for safety
  html = html.replace(/```(\w*)\n?([\s\S]*?)```/g, function(match, lang, code) {
    var escaped = escapeHtml(code.trimEnd());
    var langLabel = lang ? '<span class="code-lang-label">' + escapeHtml(lang) + '</span>' : '';
    return '<div class="code-block-wrapper">' + langLabel + '<button class="copy-code-btn" data-click="copy-code" title="Copy code"><i class="fa-solid fa-copy"></i></button><pre><code>' + escaped + '</code></pre></div>';
  });

  // Inline code
  html = html.replace(/`([^`]+)`/g, function(_, c) { return '<code>' + escapeHtml(c) + '</code>'; });

  // Bold & italic — escape captured content
  html = html.replace(/\*\*(.+?)\*\*/g, function(_, t) { return '<strong>' + escapeHtml(t) + '</strong>'; });
  html = html.replace(/\*(.+?)\*/g, function(_, t) { return '<em>' + escapeHtml(t) + '</em>'; });

  // Headings — escape captured content
  html = html.replace(/^### (.+)$/gm, function(_, t) { return '<h4>' + escapeHtml(t) + '</h4>'; });
  html = html.replace(/^## (.+)$/gm, function(_, t) { return '<h3>' + escapeHtml(t) + '</h3>'; });
  html = html.replace(/^# (.+)$/gm, function(_, t) { return '<h2>' + escapeHtml(t) + '</h2>'; });

  // Blockquote — handle both literal > and already-escaped &gt;
  html = html.replace(/^&gt; (.+)$/gm, function(_, t) { return '<blockquote>' + escapeHtml(t) + '</blockquote>'; });
  html = html.replace(/^> (.+)$/gm, function(_, t) { return '<blockquote>' + escapeHtml(t) + '</blockquote>'; });

  // Tables (pipe format)
  html = _renderTables(html);

  // Collapsible sections
  html = _renderCollapsibleSections(html);

  // Horizontal rule
  html = html.replace(/^---$/gm, '<hr>');

  // Unordered lists
  html = html.replace(/^[\*\-] (.+)$/gm, function(_, t) { return '<li>' + escapeHtml(t) + '</li>'; });
  html = html.replace(/(<li>[\s\S]*?<\/li>)/g, function(match) {
    if (match.indexOf('</li>') !== -1 && match.indexOf('<li>') === 0) {
      return '<ul>' + match + '</ul>';
    }
    return match;
  });

  // Ordered lists
  html = html.replace(/^\d+\. (.+)$/gm, function(_, t) { return '<li>' + escapeHtml(t) + '</li>'; });

  // Links — both label and URL are passed through escapeHtml in callback for safety
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(_, label, url) {
    var safeLabel = escapeHtml(label);
    var safeUrl = escapeHtml(url);
    return '<a href="' + safeUrl + '" target="_blank" rel="noopener">' + safeLabel + '</a>';
  });

  // Paragraphs: double newline
  var parts = html.split(/\n\n+/);
  html = parts.map(function(p) {
    p = p.trim();
    if (!p) return '';
    if (p.startsWith('<h') || p.startsWith('<ul') || p.startsWith('<ol') ||
        p.startsWith('<pre') || p.startsWith('<blockquote') || p.startsWith('<hr') ||
        p.startsWith('<table') || p.startsWith('<div')) return p;
    return '<p>' + p + '</p>';
  }).join('\n');

  // Single newlines to <br>
  html = html.replace(/\n/g, '<br>');

  // Convert ⚙ tool calls into step cards
  html = html.replace(/⚙ (\w+):(.+?)(?=<br>|$)/g, function(_, name, detail) {
    return '<div class="step-card"><div class="step-head open" tabindex="0" role="button" aria-expanded="true"><span class="step-check done"><i class="fa-solid fa-check"></i></span><i class="fa-solid fa-wrench step-icon"></i><span class="step-title">' + escapeHtml(name) + '</span><span class="step-time">done</span><i class="fa-solid fa-chevron-down step-chevron"></i></div><div class="step-body open"><div class="step-body-inner"><div class="step-description">' + escapeHtml(detail) + '</div></div></div></div>';
  });

  // Clean up empty paragraphs
  html = html.replace(/<p><br><\/p>/g, '');
  html = html.replace(/<p>\s*<\/p>/g, '');

  // Final XSS sanitization via DOMPurify (CDN loaded in index.html)
  if (typeof DOMPurify !== 'undefined') {
    html = DOMPurify.sanitize(html, {
      ALLOWED_TAGS: ['p','br','strong','em','h2','h3','h4','ul','ol','li','pre','code','blockquote','hr','a','table','thead','tbody','tr','th','td','div','span','img','details','summary'],
      ALLOWED_ATTR: ['href','target','rel','class','id','style','src','alt','width','height','open','tabindex','role','aria-expanded','data-raw','data-start'],
      ALLOW_DATA_ATTR: true,
    });
  }

  return html;
}

// Tool call renderer — kept for external use, delegates to parseMarkdown
function parseToolCalls(text) {
  return parseMarkdown(text);
}

// ═══════════════ COMMAND PALETTE ═══════════════════

function toggleCommandPalette() {
  var overlay = document.getElementById('cmdPaletteOverlay');
  if (!overlay) return;
  var isOpen = overlay.classList.contains('show');
  if (isOpen) { closeCommandPalette(); return; }
  overlay.classList.add('show');
  var input = document.getElementById('cmdPaletteInput');
  if (input) { input.value = ''; input.focus(); }
  filterPalette('');
}

(function initCommandPaletteInput() {
  var input = document.getElementById('cmdPaletteInput');
  if (!input) return;
  input.addEventListener('input', function() {
    filterPalette(input.value);
  });
  input.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      e.preventDefault();
      closeCommandPalette();
      return;
    }
    if (e.key === 'Enter') {
      e.preventDefault();
      var items = document.querySelectorAll('.cmd-palette-item');
      for (var i = 0; i < items.length; i++) {
        if (items[i].style.display !== 'none') {
          items[i].click();
          break;
        }
      }
    }
  });
})();

window.openCommandPalette = toggleCommandPalette;

function closeCommandPalette() {
  const overlay = document.getElementById('cmdPaletteOverlay');
  if (overlay) overlay.classList.remove('show');
}

function filterPalette(query) {
  const container = document.getElementById('cmdPaletteResults');
  if (!container) return;
  const q = query.toLowerCase().trim();
  const items = container.querySelectorAll('.cmd-palette-item');
  items.forEach(function(item) {
    const text = item.textContent.toLowerCase();
    item.style.display = (!q || text.indexOf(q) !== -1) ? '' : 'none';
  });
  container.querySelectorAll('.cmd-palette-section').forEach(function(s) {
    let hasVisible = false;
    let next = s.nextElementSibling;
    while (next && !next.classList.contains('cmd-palette-section')) {
      if (next.style.display !== 'none') hasVisible = true;
      next = next.nextElementSibling;
    }
    s.style.display = hasVisible ? '' : 'none';
  });
}

// ═══════════════ COMMAND PALETTE ═══════════════════

const PALETTE_ACTIONS = {
  'new-task': function() { if (typeof newConversation === 'function') newConversation(); else if (typeof showView === 'function') showView('chat'); },
  'toggle-sidebar': function() { toggleSidebar(); },
  'toggle-panel': function() { toggleComputer(); },
  'toggle-theme': function() { toggleTheme(); },
  'search': function() { document.getElementById('sidebarSearch')?.focus(); },
  'view-chat': function() { if (typeof showView === 'function') showView('chat'); },
  'view-dashboard': function() { if (typeof showView === 'function') showView('dashboard'); },
  'view-scheduled': function() { if (typeof showView === 'function') showView('scheduler'); },
  'view-tasks': function() { if (typeof showView === 'function') showView('delegation'); },
  'view-gateway': function() { if (typeof showView === 'function') showView('gateway'); },
  'view-memory': function() { if (typeof showView === 'function') showView('memory'); },
  'view-skills': function() { if (typeof showView === 'function') showView('skills'); },
  'view-activity': function() { if (typeof showView === 'function') showView('activity'); },
  'view-settings': function() { if (typeof showView === 'function') showView('settings'); },
  'view-sessions': function() { if (typeof showView === 'function') showView('sessions'); },
  'view-mcp': function() { if (typeof showView === 'function') showView('mcp'); },
  'view-git': function() { if (typeof showView === 'function') showView('git'); },
  'view-checkpoints': function() { if (typeof showView === 'function') showView('checkpoints'); },
  'view-doctor': function() { if (typeof showView === 'function') showView('doctor'); },
  'view-debug': function() { if (typeof showView === 'function') showView('debug'); },
  'view-permissions': function() { if (typeof showView === 'function') showView('permissions'); },
  'view-plugins': function() { if (typeof showView === 'function') showView('plugins'); },
  'view-workflows': function() { if (typeof showView === 'function') showView('workflows'); },
  'view-proxy': function() { if (typeof showView === 'function') showView('proxy'); },
  'view-gguf': function() { if (typeof showView === 'function') showView('gguf'); },
  'view-manifest': function() { if (typeof showView === 'function') showView('manifest'); },
  'view-tokenbudget': function() { if (typeof showView === 'function') showView('tokenbudget'); },
  'view-autocommit': function() { if (typeof showView === 'function') showView('autocommit'); },
  'view-apikeys': function() { if (typeof showView === 'function') showView('apikeys'); },
  'clear-chat': function() { clearConversation(); },
  'export': function() { if (typeof _showExportDialog === 'function') _showExportDialog(); },
  'shortcuts': function() { if (typeof showToast === 'function') showToast('Ctrl+B Sidebar · Ctrl+J Panel · Ctrl+K Command · Ctrl+N New · Esc Close', 'info'); },
};

function execPaletteAction(action) {
  closeCommandPalette();
  var fn = PALETTE_ACTIONS[action];
  if (fn) fn();
}

// ═══════════════ CONVERSATION MANAGEMENT ═══════════════════

function newConversation() {
  if (typeof S !== 'undefined') S.messages = [];
  const area = document.getElementById('messagesArea');
  if (!area) return;
  area.innerHTML = '<div class="onboarding" id="onboarding">'
    + '<div class="onboarding-badge">NEW</div>'
    + '<div class="onboarding-logo"><svg width="48" height="48" viewBox="0 0 48 48"><rect width="48" height="48" rx="12" fill="var(--accent)"/><text x="24" y="32" text-anchor="middle" font-size="28" font-weight="700" fill="#fff">W</text></svg></div>'
    + '<h1 class="onboarding-title">Welcome to WIDDX</h1>'
    + '<p class="onboarding-subtitle" style="font-size:var(--font-size-base);color:var(--text-secondary);">Your AI-powered workspace for code & automation</p>'
    + '<div class="onboarding-actions">'
    + '<div class="onboarding-card" data-click="send-onboarding" data-msg="Hello! What can you do?"><i class="fa-solid fa-wand-magic-sparkles"></i><div><strong>Introduce yourself</strong><span>Learn about WIDDX capabilities</span></div></div>'
    + '<div class="onboarding-card" data-click="send-onboarding" data-msg="Write a Python script to analyze text files in a folder"><i class="fa-solid fa-code"></i><div><strong>Write code</strong><span>Generate and run Python scripts</span></div></div>'
    + '<div class="onboarding-card" data-click="send-onboarding" data-msg="Research the latest AI agent frameworks"><i class="fa-solid fa-compass"></i><div><strong>Research</strong><span>Explore topics in depth</span></div></div>'
    + '<div class="onboarding-card" data-click="send-onboarding" data-msg="Explain how the UIL pipeline works in WIDDX"><i class="fa-solid fa-brain"></i><div><strong>How WIDDX works</strong><span>Understand the architecture</span></div></div>'
    + '</div>'
    + '<div class="onboarding-shortcuts"><span><kbd>Ctrl+K</kbd> Commands</span><span><kbd>Ctrl+B</kbd> Sidebar</span><span><kbd>Ctrl+J</kbd> Tools</span></div>'
    + '</div>';
  if (typeof setActivity === 'function') setActivity('Ready', '\u2014');
  document.querySelectorAll('.chat-item').forEach(function(i) { i.classList.remove('active'); });
  if (typeof showToast === 'function') showToast('New conversation started', 'success');
}

function clearConversation() {
  if (typeof S !== 'undefined') S.messages = [];
  const area = document.getElementById('messagesArea');
  if (area) area.innerHTML = '';
  newConversation();
  if (typeof showToast === 'function') showToast('Conversation cleared', 'info');
}

// ═══════════════ STEP CARD BUILDERS (for agent simulation) ═══════════════════

function createStepCard(title, icon, status) {
  const card = document.createElement('div');
  card.className = 'step-card';
  var statusIcon = status === 'done' ? '<i class="fa-solid fa-check"></i>' :
    status === 'running' ? '<i class="fa-solid fa-spinner fa-spin-pulse"></i>' :
    status === 'error' ? '<i class="fa-solid fa-circle-exclamation text-warning text-12"></i>' :
    '<i class="fa-solid fa-circle text-muted" style="font-size:8px;"></i>';
  var checkClass = status === 'done' ? ' done' : '';
  var checkStyle = status === 'running' ? ' style="border-color:var(--accent);"' : status === 'error' ? ' style="border-color:var(--warning);"' : '';
  card.innerHTML = '<div class="step-head" tabindex="0" role="button" aria-expanded="false"><span class="step-check' + checkClass + '"' + checkStyle + '>' + statusIcon + '</span><i class="fa-solid ' + icon + ' step-icon"></i><span class="step-title">' + escapeHtml(title) + '</span><span class="step-time"></span><i class="fa-solid fa-chevron-down step-chevron"></i></div><div class="step-body"><div class="step-body-inner"></div></div>';
  return card;
}

function addToolCard(stepCard, type, path) {
  var inner = stepCard.querySelector('.step-body-inner');
  var tc = document.createElement('div');
  tc.className = 'tool-card';
  var iconMap = { 'Read': 'fa-file-lines', 'Glob': 'fa-folder', 'Edit': 'fa-pen', 'Write': 'fa-pen-to-square', 'Bash': 'fa-terminal', 'Grep': 'fa-magnifying-glass', 'WebFetch': 'fa-globe' };
  tc.innerHTML = '<i class="fa-solid ' + (iconMap[type] || 'fa-file-lines') + ' tool-card-icon"></i><div class="tool-card-info"><div class="tool-card-name">' + type + '</div><div class="tool-card-path">' + escapeHtml(path) + '</div></div><button class="copy-card-btn" data-click="copy-card-path" title="Copy path"><i class="fa-solid fa-copy"></i></button>';
  inner.appendChild(tc);
}

function addFindingsList(stepCard, items) {
  var inner = stepCard.querySelector('.step-body-inner');
  var ul = document.createElement('ul');
  ul.className = 'summary-list';
  items.forEach(function(item) {
    var li = document.createElement('li');
    li.textContent = item;
    ul.appendChild(li);
  });
  inner.appendChild(ul);
}

function updateStepStatus(stepCard, status, timeText) {
  var head = stepCard.querySelector('.step-head');
  var check = head.querySelector('.step-check');
  var timeEl = head.querySelector('.step-time');
  if (timeText) timeEl.textContent = timeText;
  check.className = 'step-check';
  if (status === 'done') {
    check.classList.add('done');
    check.innerHTML = '<i class="fa-solid fa-check"></i>';
  } else if (status === 'running') {
    check.style.borderColor = 'var(--accent)';
    check.innerHTML = '<i class="fa-solid fa-spinner fa-spin-pulse text-12" style="color:var(--accent);"></i>';
  } else if (status === 'error') {
    check.style.borderColor = 'var(--warning)';
    check.innerHTML = '<i class="fa-solid fa-circle-exclamation text-12" style="color:var(--warning);"></i>';
  }
}

function openStep(head) {
  head.classList.add('open');
  if (head.nextElementSibling) head.nextElementSibling.classList.add('open');
  head.setAttribute('aria-expanded', 'true');
}

// ═══════════════ STREAMING TEXT ═══════════════════

async function streamText(container, fullText, speed) {
  speed = speed || 12;
  container.textContent = '';
  for (var i = 0; i < fullText.length; i++) {
    container.textContent += fullText[i];
    if (i % 3 === 0) {
      var area = document.getElementById('messagesArea');
      if (area) area.scrollTop = area.scrollHeight;
    }
    await new Promise(function(r) { setTimeout(r, speed + Math.random() * 8); });
  }
}

// ═══════════════ CONFIRM DIALOG ═══════════════════

var _dialogResolve = null;

function showConfirm(title, desc, opts) {
  opts = opts || {};
  var overlay = document.getElementById('confirmDialog');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.className = 'dialog-overlay';
    overlay.id = 'confirmDialog';
    overlay.addEventListener('click', function(e) { if (e.target === overlay) closeConfirm(false); });
    document.body.appendChild(overlay);
  }
  var iconType = opts.type || 'warning';
  var iconMap = { warning: 'fa-triangle-exclamation', error: 'fa-circle-xmark', info: 'fa-circle-info' };
  var confirmText = opts.confirmText || 'Confirm';
  var cancelText = opts.cancelText || 'Cancel';
  var confirmClass = opts.danger ? 'dialog-btn danger' : 'dialog-btn primary';
  overlay.innerHTML = '<div class="dialog-box"><div class="dialog-icon ' + iconType + '"><i class="fa-solid ' + (iconMap[iconType] || 'fa-triangle-exclamation') + '"></i></div><div class="dialog-title">' + escapeHtml(title) + '</div><div class="dialog-desc">' + escapeHtml(desc) + '</div><div class="dialog-actions"><button class="dialog-btn secondary" id="confirmCancel">' + cancelText + '</button><button class="' + confirmClass + '" id="confirmOk">' + confirmText + '</button></div></div>';
  overlay.classList.add('open');
  document.getElementById('confirmOk').addEventListener('click', function() { closeConfirm(true); });
  document.getElementById('confirmCancel').addEventListener('click', function() { closeConfirm(false); });
  document.getElementById('confirmOk').focus();
  return new Promise(function(resolve) { _dialogResolve = resolve; });
}

function closeConfirm(result) {
  var overlay = document.getElementById('confirmDialog');
  if (overlay) overlay.classList.remove('open');
  if (_dialogResolve) _dialogResolve(result);
  _dialogResolve = null;
}

// ═══════════════ RANDOM HELPERS ═══════════════════

function rand(min, max) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function nowTime() { return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }); }

// ═══════════════ LOCALIZATION INIT ═══════════════════

// When lang.js fires a 'langchange' event, update dynamic-only elements
// (static [data-i18n] elements are already handled by Lang._translateDOM)
document.addEventListener('langchange', function(e) {
  var lang = e.detail && e.detail.lang;

  // Update document title
  document.title = (lang === 'ar') ? 'ويدكس نيكسس — منصة الذكاء الاصطناعي' : 'WIDDX Nexus — AI Agent Platform';

  // The lang-btn text content is managed by data-i18n="header_toggle_lang"
  // which Lang._translateDOM already handles, so nothing extra needed there.
});

