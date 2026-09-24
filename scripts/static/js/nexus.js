/* WIDDX Nexus — Complete Backend Integration & WebSocket Streaming */
/* Depends on: ui.js (parseMarkdown, escapeHtml, showToast, copyCodeBlock, scrollToBottom) */

// ═══════════════ APP STATE ═══════════════

/** Shared icon → activity-type mapping (single source of truth) */
const ICON_MAP = {
  'fa-comment': 'message', 'fa-robot': 'agent', 'fa-user': 'message',
  'fa-star': 'system', 'fa-wrench': 'tool', 'fa-gear': 'tool',
  'fa-sliders': 'system', 'fa-play': 'agent', 'fa-check': 'system',
  'fa-tower-broadcast': 'message', 'fa-plug': 'system', 'fa-file-pen': 'tool',
};

/* ── Simple Pub/Sub (decouples state changes from UI updates) ────
 * Usage:
 *   const unsub = Bus.on('chat:new-message', fn);
 *   Bus.emit('chat:new-message', { role: 'user', content: '...' });
 *   unsub(); // cleanup
 */
const Bus = (() => {
  const _handlers = {};
  return {
    on(event, fn) {
      (_handlers[event] = _handlers[event] || []).push(fn);
      return () => { _handlers[event] = (_handlers[event] || []).filter(h => h !== fn); };
    },
    emit(event, data) {
      (_handlers[event] || []).forEach(fn => { try { fn(data); } catch(e) { /* silent */ } });
    },
    off(event, fn) {
      if (fn) _handlers[event] = (_handlers[event] || []).filter(h => h !== fn);
      else delete _handlers[event];
    },
  };
})();

/* ── Delegated click handler (replaces inline onclick) ──────────
 * Usage: add data-click="handler-name" to HTML, then register:
 *   CLICK_HANDLERS['copy-msg'] = (el) => copyMsg(el);
 */
const CLICK_HANDLERS = {};

document.addEventListener('click', function(e) {
  var el = e.target.closest('[data-click]');
  if (!el) return;
  var action = el.getAttribute('data-click');
  var fn = CLICK_HANDLERS[action];
  if (fn) fn(el, e);
});

/* ── HTML Template helpers ───────────────────────────────────────
 * Centralise common UI patterns so show*View functions stay thin.
 * All helpers return raw HTML strings (safe: values are escapeHtml'd). */
const TEMPLATES = {
  /** Standard view wrapper: header + scrollable body. */
  view(icon, title, subtitle, bodyHtml) {
    return '<div class="view-container">'
      + '<div class="view-header"><h2><i class="fa-solid ' + icon + '"></i> ' + escapeHtml(title) + '</h2>'
      + (subtitle ? '<p>' + escapeHtml(subtitle) + '</p>' : '')
      + '</div><div class="view-body">' + (bodyHtml || '') + '</div></div>';
  },

  /** Loading state (spinner + message). */
  loading(msg) {
    return '<div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>' + escapeHtml(msg || 'Loading...') + '</p></div>';
  },

  /** Error state (warning icon + message). */
  error(msg) {
    return '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation text-error"></i><h3>Error</h3><p>' + escapeHtml(msg || 'An error occurred') + '</p></div>';
  },

  /** Empty state (custom icon, title, description). */
  empty(icon, title, desc) {
    return '<div class="empty-state"><i class="fa-solid ' + (icon || 'fa-inbox') + '"></i>'
      + (title ? '<h3>' + escapeHtml(title) + '</h3>' : '')
      + (desc ? '<p>' + escapeHtml(desc) + '</p>' : '')
      + '</div>';
  },

  /** Section card with collapsible header + body. */
  section(icon, title, badge, bodyHtml) {
    return '<div class="section-card"><div class="section-card-header">'
      + '<i class="fa-solid ' + (icon || 'fa-circle') + '"></i> '
      + escapeHtml(title)
      + (badge ? '<span class="section-badge">' + escapeHtml(badge) + '</span>' : '')
      + '</div><div class="section-card-body">' + (bodyHtml || '') + '</div></div>';
  },

  /** Filter / search bar. */
  filterBar(id, placeholder, btnHtml, oninputFn) {
    return '<div class="filter-bar"><div class="filter-icon">'
      + '<i class="fa-solid fa-magnifying-glass"></i>'
      + '<input type="text" id="' + id + '" placeholder="' + escapeHtml(placeholder || 'Search...') + '" oninput="' + (oninputFn || '') + '">'
      + '</div>' + (btnHtml || '') + '</div>';
  },

  /** Two-button row (e.g. refresh + action). */
  buttonRow(buttons) {
    if (!buttons || !buttons.length) return '';
    var html = '<div class="flex-row-wrap gap-8 mt-12">';
    for (var i = 0; i < buttons.length; i++) {
      var b = buttons[i];
      var extraStyle = b.style || '';
      html += '<button class="send-btn w-auto px-8 rounded-sm"' + (extraStyle ? ' style="' + extraStyle + '"' : '') + ' onclick="' + (b.action || '') + '">'
        + escapeHtml(b.label || 'Button') + '</button>';
    }
    return html + '</div>';
  },

  /** Render a list of items with key-value display. */
  itemList(items) {
    if (!items || !items.length) return '<span class="text-muted">No data</span>';
    return items.map(function(item) {
      var left = item.left || '';
      var right = item.right || '';
      return '<div class="flex-row-sb py-8 border-bottom-light">'
        + '<div>' + left + '</div>'
        + '<div>' + right + '</div></div>';
    }).join('');
  },

  /** Skeleton card with configurable lines. */
  skeleton(lines) {
    lines = lines || 4;
    var html = '<div class="skeleton-wrap">';
    for (var i = 0; i < Math.min(lines, 8); i++) {
      var w = ['w-80','w-60','w-40','w-60','w-80','w-20','w-60','w-40'][i % 8];
      if (i === 0) html += '<div class="skeleton-row"><div class="skeleton-block skeleton-avatar"></div><div class="skeleton-block skeleton-line ' + w + '" style="height:14px"></div></div>';
      else html += '<div class="skeleton-block skeleton-line ' + w + '"></div>';
    }
    return html + '</div>';
  },

  /** Refresh button helper. */
  refreshBtn(fn) {
    return '<button class="header-btn" onclick="' + fn + '" title="Refresh"><i class="fa-solid fa-rotate"></i></button>';
  },

  /** Error state with retry button. */
  errorRetry(msg, retryHandler) {
    return '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation text-error" style="opacity:0.6"></i><h3 class="text-primary">Error</h3><p>' + escapeHtml(msg || 'Something went wrong') + '</p>'
      + (retryHandler ? '<button class="dialog-btn primary mt-12" data-click="' + retryHandler + '"><i class="fa-solid fa-rotate"></i> Retry</button>' : '')
      + '</div>';
  },
};

/* ── Centralised Application State (God Object mitigation) ──────────
 * S.* is split into logical domains: S.chat, S.ui, S.stream.
 * Backward-compatible getters on S.* delegate to the sub-objects
 * so existing code continues to work (S.messages → S.chat.messages).
 * New code should use S.chat.*, S.ui.*, S.stream.* directly.
 */
const _S = {
  chat: {
    messages: [],
    model: 'Loading…',
    tokens: 0,
    cost: 0.0,
  },
  ui: {
    activity: 'Ready',
    tool: '—',
    view: 'chat',
    autoMode: false,
    userName: 'You',
  },
  stream: {
    ws: null,
    wsReconnectTimer: null,
    wsRetryCount: 0,
    wsMaxRetries: 10,
    streaming: false,
    _processing: false,
    _activeAIWrapper: null,
    _activeAIBody: null,
    _activeAIContent: null,
    _activeAITextEl: null,
    _activeThinking: null,
    _activeThinkingStrip: null,
    _activeToolCard: null,
    _toolCount: 0,
  },
};

// Backward-compatible S object with proxy getters/setters
const S = new Proxy(_S, {
  get(target, prop, receiver) {
    // Direct sub-object access: S.chat, S.ui, S.stream
    if (prop === 'chat') return target.chat;
    if (prop === 'ui') return target.ui;
    if (prop === 'stream') return target.stream;
    // Legacy flat access → delegate to sub-object
    if (prop in target.chat) return target.chat[prop];
    if (prop in target.ui) return target.ui[prop];
    if (prop in target.stream) return target.stream[prop];
    return undefined;
  },
  set(target, prop, value, receiver) {
    if (prop in target.chat) { target.chat[prop] = value; return true; }
    if (prop in target.ui) { target.ui[prop] = value; return true; }
    if (prop in target.stream) { target.stream[prop] = value; return true; }
    return false;
  },
  has(target, prop) {
    return prop in target.chat || prop in target.ui || prop in target.stream;
  },
});

// ═══════════════ CHAT — REAL API ONLY ═══════════════════

// ── Slash Commands ──

const SLASH_COMMANDS = [
  { cmd: '/help', icon: 'fa-circle-info', desc: 'Show available commands', action: function() { showView('chat'); addMsg('system', '**Commands:** /help, /model, /tools, /mcp, /skills, /memory, /clear, /settings, /theme, /export, /status'); } },
  { cmd: '/model', icon: 'fa-microchip', desc: 'Switch AI model', action: function() { toggleModelDropdown(); } },
  { cmd: '/tools', icon: 'fa-wrench', desc: 'List available tools', action: async function() { try { var r = await fetch('/api/tools'); var d = await r.json(); var list = (d.tools || d).map(function(t) { return '• ' + (t.name || t.function?.name || '?'); }).join('\n'); addMsg('system', '**Available Tools:**\n' + list); } catch(e) { addMsg('system', 'Error: ' + e.message); } } },
  { cmd: '/mcp', icon: 'fa-plug', desc: 'Manage MCP servers', action: function() { showView('mcp'); } },
  { cmd: '/skills', icon: 'fa-toolbox', desc: 'Browse skills', action: function() { showView('skills'); } },
  { cmd: '/memory', icon: 'fa-brain', desc: 'View memory vault', action: function() { showView('memory'); } },
  { cmd: '/clear', icon: 'fa-eraser', desc: 'Clear conversation', action: async function() { if (await showConfirm('Clear conversation?', 'All messages will be permanently removed.', { confirmText: 'Clear', danger: true })) { S.messages = []; document.getElementById('messagesArea').innerHTML = ''; showToast('Cleared', 'info'); } } },
  { cmd: '/settings', icon: 'fa-sliders', desc: 'Open settings', action: function() { showView('settings'); } },
  { cmd: '/theme', icon: 'fa-circle-half-stroke', desc: 'Toggle dark/light', action: async function() {
      toggleTheme();
      var next = document.documentElement.getAttribute('data-theme') || 'dark';
      try {
        await fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({cli_theme: next}) });
      } catch(e) { /* local theme still applied */ }
    } },
  { cmd: '/export', icon: 'fa-file-export', desc: 'Export conversation', action: function() { var txt = S.messages.map(function(m) { return '[' + m.role + '] ' + (m.content || ''); }).join('\n\n---\n\n'); navigator.clipboard.writeText(txt).then(function() { showToast('Exported to clipboard!', 'success'); }); } },
  { cmd: '/status', icon: 'fa-gauge-high', desc: 'System status', action: async function() { try { var r = await fetch('/api/status'); var d = await r.json(); addMsg('system', '**Status:**\n• Provider: ' + (d.provider?.model || '—') + '\n• Mode: ' + (d.mode || '—') + '\n• Model: ' + (d.provider?.model || '—')); } catch(e) { addMsg('system', 'Error: ' + e.message); } } },
  { cmd: '/sessions', icon: 'fa-clock-rotate-left', desc: 'View sessions', action: function() { showView('sessions'); } },
  { cmd: '/dashboard', icon: 'fa-gauge-high', desc: 'Mission Control', action: function() { showView('dashboard'); } },
];

// ── New Session ──

window.newSession = function() {
  S.messages = [];
  S._activeAIWrapper = null;
  S._activeAIBody = null;
  S._activeAITextEl = null;
  S._activeThinking = null;
  S._activeThinkingStrip = null;
  S._activeToolCard = null;
  S._toolCount = 0;
  S.streaming = false;
  S._processing = false;
  // Clear UI
  var area = document.getElementById('messagesArea');
  if (area) { area.innerHTML = ''; restoreOnboarding(); }
  // Tell backend to create new session
  fetch('/api/new-session', {method:'POST'}).catch(function(){});
  showView('chat');
  showToast('New session started', 'info');
  setActivity('Ready', '—');
};

// ── Slash command popup ──

var _slashPopupVisible = false;

window.handleInputKey = function(e) {
  var input = e.target;
  var val = input.value;

  // Slash command handling
  if (val.startsWith('/') && !val.includes(' ')) {
    showSlashPopup(val);
  } else {
    hideSlashPopup();
  }

  // Enter sends
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (_slashPopupVisible) {
      var selected = document.querySelector('.slash-item.active');
      if (selected) { selected.click(); return; }
    }
    sendMessage();
  }

  // Navigate slash items with arrow keys
  if (_slashPopupVisible && (e.key === 'ArrowDown' || e.key === 'ArrowUp')) {
    e.preventDefault();
    var items = document.querySelectorAll('.slash-item');
    var active = document.querySelector('.slash-item.active');
    var idx = Array.from(items).indexOf(active);
    if (e.key === 'ArrowDown') idx = Math.min(idx + 1, items.length - 1);
    else idx = Math.max(idx - 1, 0);
    items.forEach(function(i) { i.classList.remove('active'); });
    if (items[idx]) items[idx].classList.add('active');
  }
};

window.sendMessage = async function() {
  const input = document.getElementById('messageInput');
  const text = input.value.trim();
  if (!text || S.streaming) return;

  hideOnboarding();
  addMsg('user', text);
  input.value = '';
  input.style.height = 'auto';
  localStorage.removeItem('widdx-draft');

  if (S.autoMode) {
    showTyping(true, '🤖 Autonomous Mode — planning, executing, verifying…');
    setActivity('Autonomous', text.slice(0, 40));
  } else {
    showTyping(true, 'WIDDX is analyzing…');
    setActivity('Thinking', text.slice(0, 40));
  }

  // Try WebSocket first, fallback to REST
  if (S.ws && S.ws.readyState === WebSocket.OPEN) {
    await sendViaWS(text);
  } else {
    await sendViaREST(text);
  }
};

// ── REST fallback ──

async function sendViaREST(text) {
  try {
    const hist = S.messages.filter(function(m) { return m.role !== 'system'; }).map(function(m) { return {role: m.role, content: m.content}; }).slice(-1000);
    const r = await fetch('/api/chat', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({message:text, history:hist})
    });
    const d = await r.json();
    showTyping(false);
    if (d.error) addMsg('system', 'Error: ' + d.error);
    else if (d.content) addMsg('assistant', d.content);
    if (d.suggested_skills && d.suggested_skills.length) showSkillSuggestions(d.suggested_skills);
    setActivity('Ready', '—');
  } catch(e) {
    showTyping(false);
    addMsg('system', 'Network error: ' + e.message);
    setActivity('Ready', '—');
  }
}

// ── WebSocket streaming ──

async function sendViaWS(text) {
  S.streaming = true;
  document.getElementById('cancelBtn').classList.add('visible');
  const hist = S.messages.filter(m => m.role !== 'system').map(m => ({role: m.role, content: m.content})).slice(-1000);
  S.ws.send(JSON.stringify({message: text, history: hist}));
}

window.sendAnswer = function(answer) {
  if (!S.ws || S.ws.readyState !== WebSocket.OPEN) return;
  S.ws.send(JSON.stringify({type: 'answer', data: answer}));
  // Remove the question UI after answering
  var qBox = document.getElementById('question-box');
  if (qBox) qBox.remove();
};

function addQuestionUI(question) {
  var area = document.getElementById('messagesArea');
  if (!area) return;
  var qBox = document.createElement('div');
  qBox.id = 'question-box';
  qBox.className = 'message-wrapper system';
  qBox.innerHTML = '<div class="msg msg-system">'
    + '<div class="msg-icon"><i class="fa-solid fa-question-circle"></i></div>'
    + '<div class="msg-content"><div class="question-text" style="font-weight:600;margin-bottom:8px">❓ ' + escapeHtml(question) + '</div>'
    + '<div class="flex-ac gap-8" style="flex-wrap:wrap">'
    + '<input id="question-input" type="text" class="flex-1 h-38 bg-input border-main text-primary text-13" style="min-width:200px;border-radius:var(--radius-md);padding:0 12px" placeholder="Type your answer..." autofocus>'
    + '<button class="send-btn w-auto px-20 rounded-6 h-38" onclick="sendAnswer(document.getElementById(\'question-input\').value)"><i class="fa-solid fa-reply"></i> Answer</button>'
    + '</div></div></div>';
  area.appendChild(qBox);
  area.scrollTop = area.scrollHeight;
  var inp = document.getElementById('question-input');
  if (inp) {
    inp.focus();
    inp.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') sendAnswer(inp.value);
    });
  }
}

function initWebSocket() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const wsUrl = protocol + '//' + location.host + '/ws/chat';

  function connect() {
    try {
      S.ws = new WebSocket(wsUrl);
    } catch(e) {
      console.log('WS init error:', e.message);
      return;
    }

    S.ws.onopen = function() {
      console.log('WebSocket connected');
      S.wsRetryCount = 0;
      if (S.wsReconnectTimer) { clearTimeout(S.wsReconnectTimer); S.wsReconnectTimer = null; }
    };

    S.ws.onmessage = function(event) {
      try {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
      } catch(e) {
        console.log('WS parse error:', e.message);
      }
    };

    S.ws.onclose = function() {
      console.log('WebSocket disconnected');
      S.ws = null;
      S.streaming = false;
      showTyping(false);
      // Reconnect with max retries
      if (!S.wsReconnectTimer && S.wsRetryCount < S.wsMaxRetries) {
        S.wsRetryCount++;
        S.wsReconnectTimer = setTimeout(function() {
          S.wsReconnectTimer = null;
          initWebSocket();
        }, Math.min(5000 * S.wsRetryCount, 30000));  // exponential backoff up to 30s
      } else if (S.wsRetryCount >= S.wsMaxRetries) {
        console.log('WebSocket max retries reached');
      }
    };

    S.ws.onerror = function() {
      console.log('WebSocket error');
      // onclose will fire after this
    };
  }

  connect();
}

// ── Live Event Stream (WebSocket) ──

function initEventStream() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const url = protocol + '//' + location.host + '/ws/events';
  var ws;
  try { ws = new WebSocket(url); } catch(e) { return; }

  ws.onmessage = function(event) {
    try {
      var evt = JSON.parse(event.data);
      onLiveEvent(evt);
    } catch(e) { /* ignore parse errors */ }
  };

  ws.onclose = function() {
    // Reconnect after 10s
    setTimeout(initEventStream, 10000);
  };

  ws.onerror = function() { /* onclose will fire */ };

  // Keepalive ping every 30s
  setInterval(function() {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send('ping');
    }
  }, 30000);
}

// ── Progress bar helper ──

function updateProgress(pct, label) {
  var fill = document.getElementById('progressFill');
  var count = document.getElementById('progressCount');
  if (fill) fill.style.width = Math.min(pct, 100) + '%';
  if (count) count.textContent = label || '';
}

function onLiveEvent(evt) {
  // If we're on Dashboard or Activity view, prepend the event
  if (S.view === 'dashboard') {
    var feed = document.getElementById('dash-activity');
    if (feed) {
      var type = ICON_MAP[evt.icon] || 'message';
      var item = document.createElement('div');
      item.className = 'activity-item';
      item.style.opacity = '0';
      item.innerHTML = '<div class="activity-icon ' + type + '"><i class="fa-solid ' + (evt.icon || 'fa-circle') + '"></i></div><div class="activity-content"><div class="activity-detail">' + escapeHtml(evt.detail || '') + '</div><div class="activity-meta"><span class="activity-agent">' + escapeHtml(evt.agent || 'system') + '</span><span class="activity-time">just now</span><span class="activity-status ' + (evt.status || 'done') + '">' + (evt.status || 'done') + '</span></div></div>';
      feed.insertBefore(item, feed.firstChild);
      // Limit to 20 items
      while (feed.children.length > 20) { feed.removeChild(feed.lastChild); }
      // Fade in
      requestAnimationFrame(function() { item.style.opacity = '1'; item.style.transition = 'opacity 0.3s'; });

      // Update gateway section if event is gateway-related
      if (evt.type === 'gateway_msg' || evt.type === 'gateway_status') {
        showDashboardView(document.getElementById('messagesArea'));
      }
    }
  } else if (S.view === 'activity') {
    // Auto-refresh the activity view when on it
    if (typeof loadActivityView === 'function') {
      clearTimeout(window._activityRefreshTimer);
      window._activityRefreshTimer = setTimeout(loadActivityView, 2000);
    }
  }
}

/* ═══════════════ PROFESSIONAL MESSAGE RENDERING ═══════════════ */

// Track active streaming blocks
S._activeThinking = null;       // current thinking block element
S._activeToolCard = null;       // current tool card element
S._toolCount = 0;               // tool counter per message

/**
 * Create an assistant message wrapper — the container for all AI content.
 * Used when streaming starts or a complete message arrives.
 */
function createAssistantWrapper(content) {
  const t = new Date().toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  const wrapper = document.createElement('div');
  wrapper.className = 'message-wrapper assistant';
  wrapper.innerHTML =
    '<div class="ai-header">'
    + '<div class="ai-avatar">W</div>'
    + '<div class="ai-identity">'
    + '<span class="ai-name">WIDDX Nexus</span>'
    + '<span class="ai-model">' + escapeHtml(S.model?.slice(0, 16) || 'AI') + '</span>'
    + '</div>'
    + '<span class="ai-time">' + t + '</span>'
    + '</div>'
    + '<div class="ai-body"></div>'
    + '<div class="ai-footer">'
    + '<button class="ai-btn" data-click="copy-msg" title="Copy"><i class="fa-solid fa-copy"></i></button>'
    + '<button class="ai-btn" data-click="toggle-active" title="Good"><i class="fa-solid fa-thumbs-up"></i></button>'
    + '<button class="ai-btn" data-click="toggle-active" title="Bad"><i class="fa-solid fa-thumbs-down"></i></button>'
    + '</div>';
  S._activeAIWrapper = wrapper;
  S._activeAIBody = wrapper.querySelector('.ai-body');
  S._toolCount = 0;
  return wrapper;
}

/**
 * Add a THINKING strip — compact expandable indicator.
 */
function addThinkingBlock(reasoningText) {
  if (!S._activeAIWrapper) {
    createAssistantWrapper('');
    document.getElementById('messagesArea').appendChild(S._activeAIWrapper);
  }
  const body = S._activeAIBody;
  const strip = document.createElement('div');
  strip.className = 'think-strip';
  const tid = 'think-' + Date.now();
  strip.innerHTML =
    '<button class="think-toggle" data-click="think-toggle" data-target="' + tid + '">'
    + '<span class="think-chevron">&#9654;</span>'
    + '<span class="think-icon"><i class="fa-solid fa-brain"></i></span>'
    + '<span class="think-label">Show reasoning</span>'
    + '</button>'
    + '<div class="think-body" id="' + tid + '"><div class="think-content">'
    + '<p>' + escapeHtml(reasoningText || '') + '</p>'
    + '</div></div>';
  body.appendChild(strip);
  S._activeThinking = strip.querySelector('.think-content');
  S._activeThinkingStrip = strip;
  return strip;
}

function appendThinking(chunk) {
  if (!S._activeThinking) addThinkingBlock(chunk);
  else {
    S._activeThinking.innerHTML = '<p>' + escapeHtml((S._activeThinking.textContent || '') + chunk) + '</p>';
  }
  scrollBottom();
}

function finishThinking() {
  if (S._activeThinkingStrip) {
    S._activeThinkingStrip.querySelector('.think-body').style.display = 'none';
    S._activeThinkingStrip.querySelector('.think-label').textContent = 'Show reasoning';
    S._activeThinkingStrip.querySelector('.think-chevron').style.transform = 'rotate(0deg)';
  }
  S._activeThinking = null;
  S._activeThinkingStrip = null;
}

/**
 * Add an ECP Control Plane event — styled decision notification.
 */
function addECPEvent(action, reason, target) {
  var wrapper = createAssistantWrapper('');
  document.getElementById('messagesArea').appendChild(wrapper);
  var body = wrapper.querySelector('.ai-body');
  var el = document.createElement('div');
  el.className = 'ecp-event';

  var icons = {
    'SWITCH_MODEL': 'fa-rotate', 'REPLAN': 'fa-redo', 'ESCALATE': 'fa-rocket',
    'ABORT': 'fa-stop-circle', 'CONTINUE': 'fa-arrow-right'
  };
  var colors = {
    'SWITCH_MODEL': '#f5a623', 'REPLAN': '#4a90d9', 'ESCALATE': '#e040fb',
    'ABORT': '#ff4444', 'CONTINUE': '#00c896'
  };
  var labels = {
    'SWITCH_MODEL': 'Model Switch', 'REPLAN': 'Replan',
    'ESCALATE': 'Expert Team', 'ABORT': 'Abort'
  };
  var icon = icons[action] || 'fa-cog';
  var color = colors[action] || '#888';
  var label = labels[action] || action;
  var targetText = target ? ' → ' + target.split('/').pop() : '';

  el.innerHTML =
    '<div class="ecp-inner" style="border-left:3px solid ' + color + '">'
    + '<i class="fa-solid ' + icon + '" style="color:' + color + '"></i>'
    + '<span class="ecp-label" style="color:' + color + ';font-weight:bold">' + label + targetText + '</span>'
    + (reason ? '<span class="ecp-reason" style="font-size:0.8em;color:#888;margin-left:8px">' + escapeHtml(reason) + '</span>' : '')
    + '</div>';
  body.appendChild(el);
  // Auto-fade ECP events after 4 seconds
  setTimeout(function() {
    el.style.opacity = '0.3';
    el.style.transition = 'opacity 1s';
  }, 4000);
  scrollBottom();
}

/**
 * Add a TOOL PILL — compact inline status indicator.
 */
function addToolCard(toolName, toolArgs) {
  if (!S._activeAIWrapper) {
    createAssistantWrapper('');
    document.getElementById('messagesArea').appendChild(S._activeAIWrapper);
  }
  S._toolCount++;
  const body = S._activeAIBody;
  const pill = document.createElement('div');
  pill.className = 'tool-pill running';
  pill.setAttribute('data-tool', toolName);
  var argStr = '';
  if (toolArgs) {
    var vals = Object.values(toolArgs).filter(function(v) { return typeof v === 'string'; });
    argStr = escapeHtml(vals.join(', ').slice(0, 80));
  }
  pill.innerHTML =
    '<span class="tool-pill-status"><span class="tp-spinner"></span></span>'
    + '<span class="tool-pill-name">' + escapeHtml(toolName) + '</span>'
    + (argStr ? '<span class="tool-pill-args">' + argStr + '</span>' : '');
  body.appendChild(pill);
  S._activeToolCard = pill;

  // Auto-collapse previous completed tools
  var prevTools = body.querySelectorAll('.tool-pill.completed');
  prevTools.forEach(function(t) { t.classList.add('collapsed'); });

  scrollBottom();
  return pill;
}

function updateToolCard(success, result) {
  if (!S._activeToolCard) return;
  const pill = S._activeToolCard;
  pill.classList.remove('running');
  pill.classList.add(success ? 'success' : 'failed');
  pill.classList.add('completed');
  var icon = pill.querySelector('.tp-spinner');
  if (icon) icon.outerHTML = success
    ? '<i class="fa-solid fa-check" style="color:#4caf50"></i>'
    : '<i class="fa-solid fa-xmark" style="color:#f44336"></i>';
  
  // Auto-collapse after 2 seconds
  var p = pill;
  setTimeout(function() {
    p.classList.add('collapsed');
  }, 2000);

  S._activeToolCard = null;
  scrollBottom();
}

/**
 * Add the FINAL RESPONSE text block.
 * Rendered with full markdown support.
 */
function addResponseBlock(markdown) {
  if (!S._activeAIWrapper) {
    createAssistantWrapper('');
    document.getElementById('messagesArea').appendChild(S._activeAIWrapper);
  }
  const body = S._activeAIBody;
  // Remove any existing response block
  const existing = body.querySelector('.response-block');
  if (existing) existing.remove();
  const block = document.createElement('div');
  block.className = 'response-block';
  block.innerHTML = '<div class="response-content">' + parseMarkdown(markdown || '') + '</div>';
  body.appendChild(block);
  S._activeAITextEl = block.querySelector('.response-content');
  if (S._activeAITextEl) S._activeAITextEl.dataset.raw = markdown || '';
  scrollBottom();
  return block;
}

function appendResponseChunk(chunk) {
  if (!S._activeAITextEl) {
    addResponseBlock(chunk);
  } else {
    const raw = (S._activeAITextEl.dataset.raw || '') + chunk;
    S._activeAITextEl.dataset.raw = raw;
    S._activeAITextEl.innerHTML = parseMarkdown(raw);
  }
  // Ensure streaming cursor is present
  var rc = S._activeAITextEl;
  if (rc && !rc.querySelector('.streaming-cursor')) {
    var cursor = document.createElement('span');
    cursor.className = 'streaming-cursor';
    rc.appendChild(cursor);
  }
  scrollBottom();
}

/* ═══════════════════════════════════════════════════════════════════ */

function handleWSMessage(msg) {
  switch (msg.type) {
    case 'reasoning':
      if (!S._activeThinking) {
        setActivity('Thinking', msg.data?.slice(0, 40) || 'Analyzing...');
        addThinkingBlock(msg.data || '');
      } else {
        appendThinking(msg.data || '');
      }
      break;

    case 'tool':
      {
        const name = msg.data?.name || 'Tool';
        const args = msg.data?.args || {};
        setActivity('Running ' + name, JSON.stringify(args).slice(0, 40));
        addToolCard(name, args);
      }
      break;

    case 'tool_result':
      updateToolCard(msg.data?.success !== false, msg.data?.result || msg.data);
      break;

    case 'agent':
      {
        // Sub-agent event — show inline in chat
        var goal = msg.data?.goal || msg.data?.id || 'Sub-agent';
        var status = msg.data?.status || 'running';
        var agentId = msg.data?.id || '';
        if (!S._activeAIWrapper) {
          createAssistantWrapper('');
          document.getElementById('messagesArea').appendChild(S._activeAIWrapper);
        }
        var body = S._activeAIBody;
        var existing = body ? body.querySelector('[data-agent="' + agentId + '"]') : null;
        if (existing) {
          var s = existing.querySelector('.agent-pill-status');
          if (s) s.textContent = status;
          existing.className = 'agent-pill ' + status;
        } else {
          var pill = document.createElement('div');
          pill.className = 'agent-pill ' + status;
          pill.setAttribute('data-agent', agentId);
          pill.innerHTML = '<i class="fa-solid fa-robot status-icon"></i><span class="agent-pill-goal">' + escapeHtml(goal.slice(0, 60)) + '</span><span class="agent-pill-status">' + status + '</span>';
          if (body) body.appendChild(pill);
        }
        scrollBottom();
      }
      break;

    case 'ecp':
      // ECP Control Plane decision — styled system event
      addECPEvent(msg.data?.action || 'DECISION', msg.data?.reason || '', msg.data?.target || '');
      break;

    case 'text':
      // Streaming response text — auto-collapse thinking after response starts
      if (!S._activeAITextEl && S._activeThinking) {
        finishThinking();
      }
      appendResponseChunk(msg.data || msg.content || '');
      setActivity('Responding', (msg.data || '').slice(0, 40));
      break;

    case 'done':
      showTyping(false);
      S.streaming = false;
      S._processing = false;
      // Remove streaming cursor
      if (S._activeAITextEl) {
        var cur = S._activeAITextEl.querySelector('.streaming-cursor');
        if (cur) cur.remove();
      }
      // Save the completed assistant message to S.messages BEFORE clearing state
      if (S._activeAITextEl && S._activeAITextEl.dataset.raw) {
        var finalContent = S._activeAITextEl.dataset.raw.trim();
        if (finalContent) {
          S.messages.push({role: 'assistant', content: finalContent, raw: finalContent, canvas: null});
        }
      }
      // Trigger Canvas render while _activeAITextEl is still valid
      _tryCanvasRender();
      S._activeAIWrapper = null;
      S._activeAIBody = null;
      S._activeToolCard = null;
      S._toolCount = 0;
      S._activeAITextEl = null;
      S._activeThinking = null;
      S._activeThinkingStrip = null;
      updateProgress(100, 'Complete');
      setActivity('Ready', '—');
      resetSendUI();
      break;

    case 'error':
      showTyping(false);
      S.streaming = false;
      S._processing = false;
      // Remove streaming cursor
      if (S._activeAITextEl) {
        var cur = S._activeAITextEl.querySelector('.streaming-cursor');
        if (cur) cur.remove();
      }
      S._activeAIWrapper = null;
      S._activeAIBody = null;
      S._activeAITextEl = null;
      S._activeThinking = null;
      S._activeThinkingStrip = null;
      S._activeToolCard = null;
      S._toolCount = 0;
      updateProgress(0, 'Error');
      setActivity('Ready', '—');
      resetSendUI();
      addMsg('system', '⚠ ' + (msg.data || 'Unknown error'));
      break;

    case 'status':
      {
        var phase = msg.data?.phase || '';
        var label = msg.data?.label || '';
        var detail = msg.data?.detail || '';
        setActivity(phase.charAt(0).toUpperCase() + phase.slice(1), label.slice(0, 50));
        // Show a small inline status pill before the response
        if (!S._activeAIWrapper && !S._streamingDone && !S._processing) {
          S._streamingDone = false;
          S._processing = true;
          showTyping(true);
        }
      }
      break;

    case 'question':
      {
        var q = msg.data || '...';
        addQuestionUI(q);
      }
      break;

    default:
      if (msg.content) {
        addMsg('assistant', msg.content);
        showTyping(false);
        S.streaming = false;
        setActivity('Ready', '—');
      }
  }
}

// ═══════════════ MESSAGE RENDER ═══════════════════

function renderMsg(role, content, canvasMeta) {
  const area = document.getElementById('messagesArea');
  if (!area) return;
  const d = document.createElement('div');
  d.className = 'message-wrapper ' + role;

  if (role === 'user') {
    const t = new Date().toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
    // Render user content with basic markdown
    var renderedContent;
    try {
      renderedContent = parseMarkdown(content);
    } catch(e) {
      renderedContent = escapeHtml(content);
    }
    // If no markdown applied (plain text), use escapeHtml for safety
    if (renderedContent === escapeHtml(content)) {
      renderedContent = content.replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
    }
    d.innerHTML =
      '<div class="user-meta">'
      + '<div class="user-avatar-sm">' + escapeHtml((S.ui.userName || 'You').charAt(0).toUpperCase()) + '</div>'
      + '<span class="user-name-sm">' + escapeHtml(S.ui.userName || 'You') + '</span>'
      + '<span class="user-time">' + t + '</span>'
      + '</div>'
      + '<div class="user-bubble">' + renderedContent + '</div>'
      + '<div class="user-check"><i class="fa-solid fa-check"></i></div>';
  } else if (role === 'assistant') {
    const t = new Date().toLocaleTimeString('en-US', {hour:'2-digit', minute:'2-digit'});
    var body;
    // If message has stored canvas metadata, use canvas renderer
    if (canvasMeta && canvasMeta.type) {
      var canvasType = __canvasTypes.find(function(ct) { return ct.name === canvasMeta.type; });
      if (canvasType) {
        try { body = canvasType.render(canvasMeta.data, content); } catch(e) { body = parseMarkdown(content); }
      } else {
        body = parseMarkdown(content);
      }
      d.dataset.canvasType = canvasMeta.type;
    } else {
      try { body = parseMarkdown(content); } catch(e) { body = '<pre>' + escapeHtml(content) + '</pre>'; }
    }
    d.innerHTML =
      '<div class="ai-header">'
      + '<div class="ai-avatar">W</div>'
      + '<div class="ai-identity">'
      + '<span class="ai-name">WIDDX Nexus</span>'
      + '<span class="ai-model">' + escapeHtml((S.model || 'AI').slice(0, 16)) + '</span>'
      + '</div>'
      + '<span class="ai-time">' + t + '</span>'
      + '</div>'
      + '<div class="ai-body"><div class="response-block"><div class="response-content">' + body + '</div></div></div>'
      + '<div class="ai-footer">'
      + '<button class="ai-btn" data-click="copy-msg" title="Copy"><i class="fa-solid fa-copy"></i></button>'
      + '<button class="ai-btn" data-click="toggle-active" title="Good"><i class="fa-solid fa-thumbs-up"></i></button>'
      + '<button class="ai-btn" data-click="toggle-active" title="Bad"><i class="fa-solid fa-thumbs-down"></i></button>'
      + '</div>';
  } else {
    d.innerHTML = '<div class="system-msg"><i class="fa-solid fa-circle-info"></i> ' + escapeHtml(content) + '</div>';
  }
  area.appendChild(d);
  scrollBottom();
}

function addMsg(role, content, rawContent) {
  S.messages.push({role, content, raw: rawContent || content, canvas: null});
  renderMsg(role, content, null);
}

function addWSToolCard(name, details) {
  const area = document.getElementById('messagesArea');
  const lastMsg = area.lastElementChild;
  if (lastMsg && lastMsg.classList.contains('assistant')) {
    const content = lastMsg.querySelector('.ai-content');
    if (content) {
      const card = document.createElement('div');
      card.className = 'step-card';
      card.innerHTML = '<div class="step-head open" tabindex="0" role="button" aria-expanded="true"><span class="step-check"><i class="fa-solid fa-spinner fa-spin"></i></span><i class="fa-solid fa-wrench step-icon"></i><span class="step-title">' + escapeHtml(name) + '</span><span class="step-time">running</span><i class="fa-solid fa-chevron-down step-chevron"></i></div><div class="step-body open"><div class="step-body-inner"><div class="step-description font-mono text-xs">' + escapeHtml(details) + '</div></div></div>';
      content.appendChild(card);
      scrollBottom();
    }
  }
}

CLICK_HANDLERS['copy-msg'] = function(el) { copyMsg(el); };
CLICK_HANDLERS['toggle-active'] = function(el) { el.classList.toggle('active'); };
CLICK_HANDLERS['fill-input'] = function(el) {
  var inp = document.getElementById('messageInput');
  if (!inp) return;
  inp.value = el.getAttribute('data-value');
  inp.focus();
};
CLICK_HANDLERS['clear-upload'] = function() { clearUploadPreview(); };
CLICK_HANDLERS['load-session'] = function(el) {
  showView('chat');
  loadSession(el.getAttribute('data-session'));
};
CLICK_HANDLERS['editor-back'] = function() { showView('chat'); };
CLICK_HANDLERS['editor-run'] = function() { _editorRun(); };
CLICK_HANDLERS['editor-save'] = function() { _editorSave(); };
CLICK_HANDLERS['proc-refresh'] = function() { showProcessManager(); };
CLICK_HANDLERS['proc-kill'] = function(el) { _killProcess(el.getAttribute('data-pid')); };
CLICK_HANDLERS['take-screenshot'] = function() { takeScreenshot(); };
CLICK_HANDLERS['browser-go'] = function() {
  var bf = document.getElementById('bf');
  var bu = document.getElementById('bu');
  if (bf && bu) bf.src = bu.value;
};
CLICK_HANDLERS['run-term-cmd'] = function(el) {
  runTermCmd(el.getAttribute('data-cmd'));
};
CLICK_HANDLERS['exec-slash'] = function(el) {
  var idx = parseInt(el.getAttribute('data-idx'), 10);
  execSlashCommand(idx);
  hideSlashPopup();
};
CLICK_HANDLERS['fill-skill'] = function(el) {
  var name = el.getAttribute('data-skill');
  var inp = document.getElementById('messageInput');
  if (!inp) return;
  inp.value = '/skill ' + name;
  inp.focus();
  inp.dispatchEvent(new Event('input'));
};
CLICK_HANDLERS['think-toggle'] = function(el) {
  var tid = el.getAttribute('data-target');
  var s = document.getElementById(tid);
  if (!s) return;
  var opened = s.style.display !== 'block';
  s.style.display = opened ? 'block' : 'none';
  el.querySelector('.think-label').textContent = opened ? 'Hide reasoning' : 'Show reasoning';
  el.querySelector('.think-chevron').style.transform = opened ? 'rotate(90deg)' : 'rotate(0deg)';
};

// ── View-level CLICK_HANDLERS ──
CLICK_HANDLERS['scan-manifest'] = function() { scanManifest(); };
CLICK_HANDLERS['toggle-plugin'] = function(el) { togglePlugin(el.getAttribute('data-plugin'), el.getAttribute('data-enabled') === 'true'); };
CLICK_HANDLERS['select-platform'] = function(el) { selectPlatform(el.getAttribute('data-platform')); };
CLICK_HANDLERS['start-gateway'] = function(el) { startGateway(el.getAttribute('data-platform')); };
CLICK_HANDLERS['stop-gateway'] = function(el) { stopGateway(el.getAttribute('data-platform')); };
CLICK_HANDLERS['load-skills-view'] = function() { loadSkillsView(); };
CLICK_HANDLERS['set-permission'] = function(el) { setPermission(el.getAttribute('data-level')); };
CLICK_HANDLERS['refresh-git'] = function() { if (typeof refreshGitView === 'function') refreshGitView(); };
CLICK_HANDLERS['create-workflow'] = function() { createWorkflow(); };
CLICK_HANDLERS['run-workflow'] = function(el) { runWorkflow(el.getAttribute('data-workflow')); };
CLICK_HANDLERS['create-checkpoint'] = function() { createCheckpoint(); };
CLICK_HANDLERS['restore-checkpoint'] = function(el) { restoreCheckpoint(el.getAttribute('data-checkpoint')); };
CLICK_HANDLERS['del-checkpoint'] = function(el) { delCheckpoint(el.getAttribute('data-checkpoint')); };
CLICK_HANDLERS['add-cron'] = function() { addCronJob(); };
CLICK_HANDLERS['toggle-cron'] = function(el) { toggleCron(el.getAttribute('data-cron')); };
CLICK_HANDLERS['del-cron'] = function(el) { delCron(el.getAttribute('data-cron')); };
CLICK_HANDLERS['retry-cron-view'] = function() { showCronView(document.getElementById('messagesArea')); };
CLICK_HANDLERS['load-session-btn'] = function(el) { loadSession(el.getAttribute('data-session')); };
CLICK_HANDLERS['export-session'] = function(el) { exportSession(el.getAttribute('data-session')); };
CLICK_HANDLERS['del-session'] = function(el) { delSession(el.getAttribute('data-session')); };
CLICK_HANDLERS['sidebar-load-session'] = function(el) {
  var sid = el.getAttribute('data-sid');
  if (sid && typeof loadSession === 'function') loadSession(sid);
  else showView('chat');
};
CLICK_HANDLERS['save-general-settings'] = function() { saveGeneralSettings(); };
CLICK_HANDLERS['save-all-providers'] = function() { saveAllProviders(); };
CLICK_HANDLERS['refresh-provider-models'] = function() { refreshProviderModels(); };
CLICK_HANDLERS['save-proxy-settings'] = function() { saveProxySettings(); };
CLICK_HANDLERS['load-gguf-settings'] = function() { loadGGUFSettings(); };
CLICK_HANDLERS['switch-settings-tab'] = function(el) { switchSettingsTab(el.getAttribute('data-tab')); };
CLICK_HANDLERS['switch-settings-tab-connections'] = function(el) { switchSettingsTab(el.getAttribute('data-tab')); loadConnectionsTab(); };
CLICK_HANDLERS['switch-settings-tab-mcp'] = function(el) { switchSettingsTab(el.getAttribute('data-tab')); loadMCPTab(); };
CLICK_HANDLERS['set-perm-level'] = function(el) { setPermLevel(el.getAttribute('data-level')); };
CLICK_HANDLERS['reset-token-budget-settings'] = function() { resetTokenBudgetSettings(); };
CLICK_HANDLERS['toggle-autocommit-settings'] = function() { toggleAutoCommitSettings(); };
CLICK_HANDLERS['unload-gguf-settings'] = function() { unloadGGUFSettings(); };
CLICK_HANDLERS['add-mcp-settings'] = function() { addMCPServerFromSettings(); };
CLICK_HANDLERS['restart-mcp-settings'] = function(el) { restartMCPFromSettings(el.getAttribute('data-mcp')); };
CLICK_HANDLERS['del-mcp-settings'] = function(el) { delMCPFromSettings(el.getAttribute('data-mcp')); };
CLICK_HANDLERS['connect-gateway-settings'] = function(el) { connectGateway(el.getAttribute('data-gw-platform')); };
CLICK_HANDLERS['disconnect-gateway-settings'] = function(el) { disconnectGateway(el.getAttribute('data-gw-platform')); };
CLICK_HANDLERS['toggle-autocommit'] = function() { toggleAutoCommit(); };
CLICK_HANDLERS['reset-token-budget'] = function() { resetTokenBudget(); };
CLICK_HANDLERS['run-doctor'] = function() { showDoctorView(document.getElementById('messagesArea')); };
CLICK_HANDLERS['save-proxy'] = function() { saveProxy(); };
CLICK_HANDLERS['load-gguf'] = function() { loadGGUF(); };
CLICK_HANDLERS['unload-gguf'] = function() { unloadGGUF(); };
CLICK_HANDLERS['add-memory'] = function() { addMemory(); };
CLICK_HANDLERS['load-memory-view'] = function() { loadMemoryView(); };
CLICK_HANDLERS['del-memory'] = function(el) { delMemory(el.getAttribute('data-memory')); };
CLICK_HANDLERS['load-activity-view'] = function() { loadActivityView(); };
CLICK_HANDLERS['add-mcp'] = function() { addMCPServer(); };
CLICK_HANDLERS['restart-mcp'] = function(el) { restartMCPServer(el.getAttribute('data-mcp')); };
CLICK_HANDLERS['del-mcp'] = function(el) { delMCPServer(el.getAttribute('data-mcp')); };
CLICK_HANDLERS['refresh-debug'] = function() { showDebugView(document.getElementById('messagesArea')); };

// ── Index-level CLICK_HANDLERS ──
CLICK_HANDLERS['export-chat'] = function() {
  _showExportDialog();
};
CLICK_HANDLERS['export-markdown'] = function() { _exportChat('markdown', false); };
CLICK_HANDLERS['export-markdown-dl'] = function() { _exportChat('markdown', true); };
CLICK_HANDLERS['export-json'] = function() { _exportChat('json', true); };
CLICK_HANDLERS['close-export-dialog'] = function() {
  var d = document.getElementById('export-dialog');
  if (d) d.remove();
};
CLICK_HANDLERS['open-command-palette'] = function() { openCommandPalette(); };
CLICK_HANDLERS['toggle-auto-mode'] = function() { toggleAutoMode(); };
CLICK_HANDLERS['lang-toggle'] = function() { if (typeof Lang !== 'undefined') Lang.toggle(); };
CLICK_HANDLERS['toggle-theme'] = function() { toggleTheme(); };
CLICK_HANDLERS['send-onboarding'] = function(el) { sendOnboardingMsg(el.getAttribute('data-msg')); };
CLICK_HANDLERS['toggle-computer'] = function() { toggleComputer(); };
CLICK_HANDLERS['toggle-voice-input'] = function() { toggleVoiceInput(); };
CLICK_HANDLERS['switch-right-tab'] = function(el) { switchTab(el, el.getAttribute('data-tab')); };
CLICK_HANDLERS['close-palette-overlay'] = function(el, e) {
  if (e && e.target === el) closeCommandPalette();
};
CLICK_HANDLERS['exec-palette'] = function(el) {
  if (typeof execPaletteAction === 'function') execPaletteAction(el.getAttribute('data-action'));
};

window.copyMsg = function(btn) {
  const text = btn.closest('.ai-content')?.querySelector('.ai-text')?.textContent
    || btn.closest('.message-wrapper')?.querySelector('.response-content')?.textContent
    || btn.closest('.message-wrapper')?.textContent || '';
  navigator.clipboard.writeText(text).then(function() {
    btn.classList.add('copied');
    showToast('Copied!', 'success');
    setTimeout(function() { btn.classList.remove('copied'); }, 1500);
  });
};

window.showTyping = function(on, label) {
  var ti = document.getElementById('typingIndicator');
  if (!ti) return;
  ti.classList.toggle('show', on);
  if (on && label) {
    var lbl = ti.querySelector('.typing-label');
    if (lbl) lbl.textContent = label;
  }
};

function resetSendUI() {
  var stopBtn = document.getElementById('cancelBtn');
  var sendBtn = document.getElementById('sendBtn');
  var input = document.getElementById('messageInput');
  // Use only the CSS class — never set inline style.display which overrides it
  if (stopBtn) stopBtn.classList.remove('visible');
  if (sendBtn) sendBtn.style.display = '';
  if (input) input.disabled = false;
}

function cancelAgent() {
  if (S.ws && S.ws.readyState === WebSocket.OPEN) {
    S.ws.send(JSON.stringify({type: 'cancel'}));
  }
  showTyping(false);
  S.streaming = false;
  S._processing = false;
  resetSendUI();
  setActivity('Cancelled', '—');
  showToast('Task cancelled', 'info');
}


function showSkillSuggestions(skills) {
  var container = document.getElementById('skill-suggestions');
  if (!container) return;
  var html = skills.map(function(s) {
    return '<span class="skill-chip" data-click="fill-skill" data-skill="' + escapeHtml(s.name) + '" title="' + escapeHtml(s.description || '') + '">' + (s.icon || '') + ' ' + escapeHtml(s.name) + '</span>';
  }).join('');
  container.innerHTML = html;
  container.style.display = 'block';
}

function scrollBottom() {
  const area = document.getElementById('messagesArea');
  if (area) {
    area.scrollTop = area.scrollHeight;
    const btn = document.getElementById('scrollBottomBtn');
    if (btn) btn.classList.remove('visible');
  }
}

// Scroll monitor — IntersectionObserver
var _scrollSentinel = document.createElement('div');
_scrollSentinel.className = 'scroll-sentinel';
var _messagesArea = document.getElementById('messagesArea');
if (_messagesArea) {
  _messagesArea.appendChild(_scrollSentinel);
  var _scrollObserver = new IntersectionObserver(function(entries) {
    var btn = document.getElementById('scrollBottomBtn');
    if (!btn) return;
    btn.classList.toggle('visible', !entries[0].isIntersecting);
  }, { root: _messagesArea, threshold: 1.0 });
  _scrollObserver.observe(_scrollSentinel);
}
// Tool pill timeout — check every 10s
var _pillMonitor = setInterval(function() {
  var pills = document.querySelectorAll('.tool-pill.running');
  pills.forEach(function(p) {
    var start = parseInt(p.dataset.start || '0');
    if (!start) { p.dataset.start = Date.now(); return; }
    if (Date.now() - start > 30000) { p.classList.add('stuck'); }
  });
}, 10000);

// ═══════════════ ACTIVITY ═══════════════════

function setActivity(label, tool) {
  S.activity = label; S.tool = tool;
  const l = document.getElementById('activityLabel');
  const t = document.getElementById('activityTool');
  if (l) l.textContent = label;
  if (t) t.textContent = tool;
}

// ═══════════════ STATUS & MODEL ═══════════════════

// ── Slash popup helpers ──

function showSlashPopup(val) {
  var existing = document.getElementById('slashPopup');
  if (!existing) {
    var div = document.createElement('div');
    div.id = 'slashPopup';
    div.className = 'slash-popup';
    document.querySelector('.input-container').appendChild(div);
  }
  var popup = document.getElementById('slashPopup');
  var query = val.slice(1).toLowerCase();
  var matches = SLASH_COMMANDS.filter(function(c) { return c.cmd.slice(1).startsWith(query); });
  if (!matches.length) { popup.style.display = 'none'; _slashPopupVisible = false; return; }
  popup.style.display = 'block';
  _slashPopupVisible = true;
  popup.innerHTML = matches.map(function(c, i) {
    return '<div class="slash-item' + (i === 0 ? ' active' : '') + '" data-click="exec-slash" data-idx="' + SLASH_COMMANDS.indexOf(c) + '"><i class="fa-solid ' + c.icon + '"></i><span class="slash-cmd">' + c.cmd + '</span><span class="slash-desc">' + c.desc + '</span></div>';
  }).join('');
}

function hideSlashPopup() {
  var popup = document.getElementById('slashPopup');
  if (popup) popup.style.display = 'none';
  _slashPopupVisible = false;
}

window.execSlashCommand = function(idx) {
  var cmd = SLASH_COMMANDS[idx];
  if (!cmd) return;
  var input = document.getElementById('messageInput');
  if (input) { input.value = ''; input.style.height = 'auto'; }
  hideSlashPopup();
  cmd.action();
};

// Send a pre-written onboarding message
window.sendOnboardingMsg = function(text) {
  var input = document.getElementById('messageInput');
  if (input) { input.value = text; }
  sendMessage();
  hideOnboarding();
};

function hideOnboarding() {
  var ob = document.getElementById('onboarding');
  if (ob) ob.style.display = 'none';
}

var ONBOARDING_HTML = '';

function restoreOnboarding() {
  if (S.messages.length) return;
  var area = document.getElementById('messagesArea');
  if (!area) return;
  if (ONBOARDING_HTML) {
    area.innerHTML = ONBOARDING_HTML;
  }
}

// ── Inline model switcher ──

window.toggleModelDropdown = function(e) {
  e = e || window.event;
  if (!e) return;
  e.stopPropagation();
  var dd = document.getElementById('modelDropdown');
  if (!dd) return;
  var shown = dd.style.display !== 'none';
  dd.style.display = shown ? 'none' : 'block';
  if (!shown) {
    populateModelDropdown();
    var chevron = document.querySelector('.model-chevron');
    if (chevron) chevron.style.transform = 'rotate(180deg)';
  } else {
    var chevron = document.querySelector('.model-chevron');
    if (chevron) chevron.style.transform = '';
  }
};

// Close dropdown on outside click
document.addEventListener('click', function(e) {
  var dd = document.getElementById('modelDropdown');
  var sel = document.getElementById('modelSelector');
  if (dd && dd.style.display !== 'none' && !dd.contains(e.target) && !sel.contains(e.target)) {
    dd.style.display = 'none';
    var chevron = document.querySelector('.model-chevron');
    if (chevron) chevron.style.transform = '';
  }
});

async function populateModelDropdown() {
  var list = document.getElementById('modelDropdownList');
  if (!list) return;
  list.innerHTML = '<div class="p-8 px-14 text-muted text-xs">Loading...</div>';
  try {
    var r = await fetch('/api/settings');
    var data = await r.json();
    var prov = data.provider || {};
    var providers = data.available_providers || [];
    var currentProvider = providers.find(function(p) { return p.id === prov.name; }) || providers[0] || {models:[]};
    var models = currentProvider.models || [];
    list.innerHTML = '';
    // Show provider name as section header
    var ph = document.createElement('div');
    ph.className = 'text-xs text-tertiary';
    ph.style.padding = '4px 14px';
    ph.textContent = currentProvider.name || prov.name || 'Models';
    list.appendChild(ph);
    models.forEach(function(m) {
      var item = document.createElement('div');
      item.className = 'model-dropdown-item' + (m === prov.model ? ' active' : '');
      item.textContent = m;
      item.addEventListener('click', async function() {
        // Save model change immediately
        showToast('Switching to ' + m + '...', 'info');
        var saveR = await fetch('/api/settings', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({provider:{name:prov.name, model:m}}),
        });
        var saveD = await saveR.json();
        if (saveD.status === 'ok') {
          document.getElementById('modelName').textContent = m;
          if (typeof refreshChat === 'function') refreshChat();
          else showToast('Model: ' + m, 'success');
        } else {
          showToast('Error: ' + (saveD.message || 'Failed'), 'error');
        }
        document.getElementById('modelDropdown').style.display = 'none';
        var ch = document.querySelector('.model-chevron');
        if (ch) ch.style.transform = '';
      });
      list.appendChild(item);
    });
  } catch(e) {
    list.innerHTML = '<div class="p-8 px-14 text-error text-xs">' + escapeHtml(e.message) + '</div>';
  }
}

async function loadStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const prov = d.provider || {};
    S.model = prov.name && prov.model ? (prov.name + '/' + prov.model) : (prov.model || S.model);
    const n = document.getElementById('modelName');
    if (n) n.textContent = prov.model || S.model;
    const b = document.getElementById('plan-badge');
    if (b) b.textContent = '🟢 ' + (d.sandbox?.mode || 'ready');
    const p = document.getElementById('progressCount');
    if (p) p.textContent = (d.sandbox?.mode || 'ready') + ' sandbox';
  } catch(e) { console.log('Status:', e.message); }
}

async function loadProjectSession() {
  try {
    const r = await fetch('/api/project/session');
    if (!r.ok) return;
    const data = await r.json();
    const msgs = (data.messages || []).filter(function(m) {
      return m.role === 'user' || m.role === 'assistant' || m.role === 'system';
    });
    if (!msgs.length) return;
    S.messages = msgs.map(function(m) {
      return { role: m.role, content: m.content || '', raw: m.content || '', canvas: m.canvas || null };
    });
    hideOnboarding();
    const area = document.getElementById('messagesArea');
    if (area) {
      area.innerHTML = '';
      S.messages.forEach(function(m) { renderMsg(m.role, m.content, m.canvas); });
    }
    if (data.state && data.state.model) {
      S.model = data.state.model;
      const n = document.getElementById('modelName');
      if (n) n.textContent = data.state.model.split('/').pop() || data.state.model;
    }
  } catch(e) { console.log('Project session:', e.message); }
}

async function loadAppTheme() {
  try {
    const r = await fetch('/api/settings');
    const d = await r.json();
    const theme = (d.cli_theme || d.theme || 'dark').toLowerCase();
    if (theme === 'light' || theme === 'dark') {
      document.documentElement.setAttribute('data-theme', theme);
      localStorage.setItem('widdx-theme', theme);
    }
  } catch(e) { /* keep localStorage theme */ }
}

/* ═══════════════ VIEW REGISTRY (#17-DRY: replaces 25+ if/else chain) ═══════════════════ */

/**
 * View Registry — maps view names to their render functions.
 * Replaces the 25+ if/else chain in showView() with a simple lookup.
 * Each entry: 'view-name': function(area) { ... }
 * Add new views here instead of adding another else-if.
 */
const VIEWS = {
  chat: function(area) {
    if (S.messages.length) {
      area.innerHTML = '';
      S.messages.forEach(function(m) { renderMsg(m.role, m.content, m.canvas); });
    } else {
      restoreOnboarding();
    }
    setActivity('Ready', '—');
  },
  files: function(area) {
    // Show file explorer in the main area
    _fileExplorerMainPath = '.';
    area.innerHTML = '<div id="fe-main" class="file-explorer" style="height:100%;display:flex;flex-direction:column"></div>';
    _renderFileExplorerMain('.');
  },
  scheduler: function(area) { showCronView(area); },
  dashboard: function(area) { showDashboardView(area); },
  delegation: function(area) { showDelegationView(area); },
  gateway: function(area) { showGatewayView(area); },
  skills: function(area) { showSkillsView(area); },
  activity: function(area) { showActivityView(area); },
  settings: function(area) { showModelSetupView(area); },
  'model-setup': function(area) { showModelSetupView(area); },
  memory: function(area) { showMemoryView(area); },
  mcp: function(area) { showMCPView(area); },
  sessions: function(area) { showSessionsView(area); },
  checkpoints: function(area) { showCheckpointsView(area); },
  git: function(area) { showGitView(area); },
  doctor: function(area) { showDoctorView(area); },
  debug: function(area) { showDebugView(area); },
  permissions: function(area) { showPermissionsView(area); },
  plugins: function(area) { showPluginsView(area); },
  workflows: function(area) { showWorkflowsView(area); },
  proxy: function(area) { showProxyView(area); },
  gguf: function(area) { showGGUFView(area); },
  manifest: function(area) { showManifestView(area); },
  tokenbudget: function(area) { showTokenBudgetView(area); },
  autocommit: function(area) { showAutoCommitView(area); },
  apikeys: function(area) { showApiKeysView(area); },
  docs: function(area) { if (window.showProjectDocsView) window.showProjectDocsView(area); },
  search: function(area) { if (window.showSearchView) window.showSearchView(area); },
  plan: function(area) { if (window.showPlanView) window.showPlanView(area); },
};

// ═══════════════ NAVIGATION ═══════════════════

function showView(view) {
  S.view = view;
  const area = document.getElementById('messagesArea');
  if (!area) return;

  // Hide Stop button in non-Chat views
  var stopBtn = document.getElementById('cancelBtn');
  if (stopBtn && view !== 'chat') stopBtn.classList.remove('visible');

  // Update active nav item
  document.querySelectorAll('.nav-item').forEach(function(i) {
    i.classList.toggle('active', i.dataset.view === view);
  });

  // View Registry lookup — single dispatch instead of 25+ if/else
  if (VIEWS[view]) {
    VIEWS[view](area);
  }
}

/* ═══════════════ VIEW LOADER (DRY: avoids try/catch + error template duplication) ═══════════════════ */

/**
 * Generic view loader: fetches a URL, calls a render function, and
 * handles errors with a consistent error template + activity update.
 * Replaces the duplicated try/catch + TEMPLATES.error pattern (#17).
 *
 * @param {string} url - API endpoint to fetch
 * @param {function} renderFn - Receives (data, area) and returns HTML or manipulates area directly
 * @param {HTMLElement} area - The messagesArea element
 * @param {object} [opts] - Options
 * @param {string} [opts.loadingMsg] - Loading message
 * @param {function} [opts.onSuccess] - Called after successful render
 */
async function loadView(url, renderFn, area, opts) {
  opts = opts || {};
  area.innerHTML = TEMPLATES.loading(opts.loadingMsg || 'Loading...');
  setActivity('Loading', url);
  try {
    const r = await fetch(url);
    if (!r.ok) {
      area.innerHTML = TEMPLATES.error('HTTP ' + r.status + ': ' + r.statusText);
      setActivity('Ready', '—');
      return;
    }
    const data = await r.json();
    await renderFn(data, area);
    if (opts.onSuccess) opts.onSuccess(data);
    setActivity('Ready', '—');
  } catch(e) {
    area.innerHTML = TEMPLATES.error(e.message || 'Request failed');
    setActivity('Ready', '—');
  }
}

// ═══════════════ COMPUTER PANEL ═══════════════════

window.switchTab = function(el, view) {
  // Stop process auto-refresh when leaving the processes tab
  if (view !== 'processes' && typeof _stopProcessAutoRefresh === 'function') {
    _stopProcessAutoRefresh();
  }
  el.parentElement.querySelectorAll('.right-panel-tab').forEach(function(t) { t.classList.remove('active'); });
  el.classList.add('active');
  if (view === 'terminal') showTerminal();
  else if (view === 'browser') showBrowser();
  else if (view === 'processes') showProcessManager();
  else if (view === 'screenshot') showScreenshot();
};

async function showDesktop() {
  const body = document.getElementById('panelBody');
  body.innerHTML = '<div class="panel-desktop-view"><i class="fa-solid fa-display"></i><div class="panel-desktop-text">Loading...</div></div>';
  try {
    const r = await fetch('/api/computer/info');
    const d = await r.json();
    body.innerHTML = '<div class="panel-desktop-view panel-desktop-content">'
      + '<div><strong>Platform:</strong> ' + escapeHtml(d.system?.platform || '—') + '</div>'
      + '<div><strong>Python:</strong> ' + escapeHtml(d.system?.python || '—') + '</div>'
      + '<div><strong>CPU:</strong> ' + (d.system?.cpu_count || 0) + ' cores</div>'
      + '<div><strong>Sandbox:</strong> ' + escapeHtml(d.mode || 'auto') + '</div>'
      + '<div class="mt-8 pt-8 border-top-light"><strong>Stats:</strong> ' + (d.cron?.length || 0) + ' cron · ' + (d.background?.length || 0) + ' bg · ' + (d.agents?.length || 0) + ' agents · ' + (d.skills || 0) + ' skills</div>'
      + '</div>';
    var p = document.getElementById('progressCount');
    if (p) p.textContent = (d.agents?.length || 0) + ' agents · ' + (d.background?.length || 0) + ' tasks';
    var e = document.getElementById('elapsedTime');
    if (e) e.textContent = 'Sandbox: ' + (d.mode || 'auto');
  } catch(e) {
    body.innerHTML = '<div class="panel-desktop-view"><span class="text-error">' + escapeHtml(e.message) + '</span></div>';
  }
}

var _termHistory = [];
var _termIdx = -1;

window.runTermCmd = function(cmd) {
  var inp = document.getElementById('ti');
  if (!inp) return;
  // Execute directly if terminal is visible, otherwise fill input
  var o = document.getElementById('to');
  if (o) {
    execTermCmd(cmd, o);
  } else {
    // Fill the chat input instead
    var msgInp = document.getElementById('messageInput');
    if (msgInp) { msgInp.value = cmd; sendMessage(); }
  }
};

function execTermCmd(cmd, o) {
  _termHistory.push(cmd);
  _termIdx = _termHistory.length;
  // Show prompt + command
  o.innerHTML += '<span style="color:#4ade80;font-weight:600">$ </span><span style="color:#fff">' + escapeHtml(cmd) + '</span>\n';
  o.scrollTop = o.scrollHeight;
  setActivity('Running', cmd);
  fetch('/api/computer/exec', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({command:cmd})})
    .then(function(r) { return r.json(); })
    .then(function(d) {
      if (d.stdout) o.innerHTML += '<span style="color:#e2e8f0">' + escapeHtml(d.stdout) + '</span>';
      if (d.stderr) o.innerHTML += '<span style="color:#f87171">' + escapeHtml(d.stderr) + '</span>\n';
      if (!d.stdout && !d.stderr) o.innerHTML += '\n';
      o.innerHTML += '<span style="color:rgba(255,255,255,0.2);font-size:10px">↳ exit ' + (d.exit_code || 0) + ' [' + (d.mode || 'auto') + ']</span>\n\n';
      o.scrollTop = o.scrollHeight;
      setActivity('Ready', '—');
    })
    .catch(function(e) {
      o.innerHTML += '<span style="color:#f87171">' + escapeHtml(e.message) + '</span>\n\n';
      o.scrollTop = o.scrollHeight;
      setActivity('Ready', '—');
    });
}

function showTerminal() {
  const body = document.getElementById('panelBody');
  body.innerHTML = '<div id="tc" class="terminal-container">'
    + '<div id="to" class="terminal-output">'
    + '<span class="text-muted text-xs" style="color:rgba(74,222,128,0.5)">WIDDX Terminal — cgroups sandbox active</span>\n'
    + '<span class="text-muted text-xs" style="color:rgba(255,255,255,0.2)">Type a command and press Enter, or click a quick button below.</span>\n\n'
    + '</div>'
    + '<div class="terminal-input-bar">'
    + '<span class="terminal-prompt">$</span>'
    + '<input id="ti" class="terminal-input" placeholder="e.g. python app.py, ls, npm start..."></div>'
    + '<div class="terminal-footer">'
    + '<span class="text-xs" style="color:rgba(255,255,255,0.25);padding:0 2px">Quick run:</span>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="python --version">python</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="node --version">node</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="ls -la">ls</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="pwd">pwd</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="python -m http.server 8080">serve :8080</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="npm start">npm start</button>'
    + '<button class="quick-port-btn" data-click="run-term-cmd" data-cmd="pip list">pip list</button>'
    + '</div></div>';
  var ti = document.getElementById('ti');
  if (ti) ti.focus();
  document.getElementById('ti').onkeydown = function(e) {
    if (e.key === 'Enter') {
      var cmd = e.target.value.trim();
      if (!cmd) return;
      var o = document.getElementById('to');
      execTermCmd(cmd, o);
      e.target.value = '';
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (_termIdx > 0) { _termIdx--; e.target.value = _termHistory[_termIdx]; }
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (_termIdx < _termHistory.length - 1) { _termIdx++; e.target.value = _termHistory[_termIdx]; }
      else { _termIdx = _termHistory.length; e.target.value = ''; }
    }
  };
}

function showBrowser() {
  // Determine a sensible default URL: same host on port 8000
  var defaultUrl = location.protocol + '//' + location.hostname + ':8000';
  const body = document.getElementById('panelBody');
  body.innerHTML = '<div class="browser-container">'
    + '<div class="browser-urlbar">'
    + '<input id="bu" class="browser-url-input" placeholder="https://" value="' + escapeHtml(defaultUrl) + '">'
    + '<button class="browser-go-btn" data-click="browser-go">Go</button>'
    + '<button class="browser-go-btn" data-click="browser-refresh" title="Refresh"><i class="fa-solid fa-rotate"></i></button>'
    + '<button class="browser-go-btn" data-click="browser-toggle-live" id="browser-live-btn" title="Auto-refresh">●</button>'
    + '</div>'
    + '<iframe id="bf" class="browser-iframe" src="' + escapeHtml(defaultUrl) + '" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"></iframe></div>';
}

var _browserRefreshTimer = null;

CLICK_HANDLERS['browser-refresh'] = function() {
  var bf = document.getElementById('bf');
  if (bf) bf.src = bf.src;
};

CLICK_HANDLERS['browser-toggle-live'] = function() {
  var btn = document.getElementById('browser-live-btn');
  if (_browserRefreshTimer) {
    clearInterval(_browserRefreshTimer);
    _browserRefreshTimer = null;
    if (btn) btn.style.opacity = '0.5';
  } else {
    _browserRefreshTimer = setInterval(function() {
      var bf = document.getElementById('bf');
      if (bf && bf.src && bf.src !== 'about:blank' && !bf.src.startsWith('blob:')) {
        bf.src = bf.src;
      }
    }, 3000);
    if (btn) btn.style.opacity = '1';
  }
};

/* ═══════════════ FILE EXPLORER ═══════════════════ */

/* ── Main area file explorer (for VIEWS['files']) ── */
var _fileExplorerMainPath = '.';

async function _renderFileExplorerMain(dir) {
  _fileExplorerMainPath = dir || '.';
  var body = document.getElementById('fe-main');
  if (!body) return;
  body.innerHTML = '<div class="px-16 py-12 flex-row-sb"><span class="text-muted text-xs font-mono" id="fe-main-path">' + escapeHtml(_fileExplorerMainPath) + '</span><div class="flex-row gap-4"><button class="quick-port-btn" id="fe-main-up">↑</button><button class="quick-port-btn" id="fe-main-refresh">↻</button></div></div><div id="fe-main-body" class="flex-1 overflow-y-auto px-8" style="min-height:0"></div>';
  document.getElementById('fe-main-up')?.addEventListener('click', function() {
    var parts = _fileExplorerMainPath.replace(/^\/+/, '').split('/').filter(Boolean);
    if (parts.length <= 1) return;
    parts.pop();
    _renderFileExplorerMain('/' + parts.join('/'));
  });
  document.getElementById('fe-main-refresh')?.addEventListener('click', function() {
    _renderFileExplorerMain(_fileExplorerMainPath);
  });
  try {
    var r = await fetch('/api/sandbox/files?path=' + encodeURIComponent(_fileExplorerMainPath));
    var d = await r.json();
    var feBody = document.getElementById('fe-main-body');
    if (!feBody) return;
    if (d.error) { feBody.innerHTML = '<div class="text-error p-16">' + escapeHtml(d.error) + '</div>'; return; }
    var files = d.files || [];
    if (!files.length) { feBody.innerHTML = '<div class="text-muted p-16">Empty directory</div>'; return; }
    var html = '';
    files.forEach(function(f) {
      var fullPath = f.path || _fileExplorerMainPath + '/' + f.name;
      if (f.type === 'directory') {
        html += '<div class="file-explorer-item directory px-8 py-6 flex-row gap-8 cursor-pointer rounded-sm" style="min-height:32px"><span>📁</span><span class="text-sm">' + escapeHtml(f.name) + '</span></div>';
      } else {
        html += '<div class="file-explorer-item px-8 py-6 flex-row gap-8 cursor-pointer rounded-sm" style="min-height:32px"><span>📄</span><span class="text-sm">' + escapeHtml(f.name) + '</span></div>';
      }
    });
    feBody.innerHTML = html;
    // Add click handlers for each item
    feBody.querySelectorAll('.file-explorer-item').forEach(function(el, idx) {
      el.addEventListener('click', function() {
        var f = files[idx];
        if (!f) return;
        var fullPath = f.path || _fileExplorerMainPath + '/' + f.name;
        if (f.type === 'directory') {
          _renderFileExplorerMain(fullPath);
        } else {
          showFileEditor(fullPath);
        }
      });
    });
  } catch(e) {
    var feBody = document.getElementById('fe-main-body');
    if (feBody) feBody.innerHTML = '<div class="text-error p-16">' + escapeHtml(e.message) + '</div>';
  }
}

/* ── End of dead code cleanup ── */

/* ═══════════════ PHASE 2: FILE EDITOR ═══════════════════ */

var _editorCurrentPath = '';
var _editorOriginalContent = '';

async function showFileEditor(filePath) {
  _editorCurrentPath = filePath;
  const body = document.getElementById('messagesArea');
  // Destroy previous CM instance if any before clearing body
  if (window._editorCM) {
    window._editorCM.toTextArea();
    window._editorCM = null;
  }
  body.innerHTML = '<div class="file-editor file-editor-full">'
    + '<div class="file-editor-header">'
    + '<button class="editor-back-btn" data-click="editor-back"><i class="fa-solid fa-arrow-left"></i> Back to Chat</button>'
    + '<span class="editor-filename" id="editor-filename">' + escapeHtml(filePath.split('/').pop() || filePath) + '</span>'
    + '<span class="editor-path">' + escapeHtml(filePath) + '</span>'
    + '</div>'
    + '<div class="file-editor-body"><textarea id="editor-textarea" spellcheck="false"></textarea></div>'
    + '<div class="file-editor-footer">'
    + '<span class="editor-status" id="editor-status">Loading...</span>'
    + '<button class="editor-save-btn" id="editor-run-btn" data-click="editor-run" title="Run this file"><i class="fa-solid fa-play"></i> Run</button>'
    + '<button class="editor-save-btn" id="editor-save-btn" data-click="editor-save"><i class="fa-solid fa-floppy-disk"></i> Save</button>'
    + '</div>'
    + '</div>';

  try {
    var r = await fetch('/api/sandbox/file?path=' + encodeURIComponent(filePath));
    var d = await r.json();
    if (d.error) {
      document.getElementById('editor-status').textContent = 'Error: ' + d.error;
      return;
    }
    var content = d.content || '';
    _editorOriginalContent = content;

    // Detect CodeMirror mode from extension
    var ext = filePath.split('.').pop().toLowerCase();
    var mode = _codeMirrorMode(ext);

    // Create CodeMirror
    var ta = document.getElementById('editor-textarea');
    if (ta && typeof CodeMirror !== 'undefined') {
      ta.value = content;
      window._editorCM = CodeMirror.fromTextArea(ta, {
        mode: mode,
        theme: 'monokai',
        lineNumbers: true,
        indentUnit: 2,
        tabSize: 2,
        lineWrapping: true,
        matchBrackets: true,
        autoCloseBrackets: true,
        extraKeys: {'Ctrl-S': function() { _editorSave(); }}
      });
      window._editorCM.focus();
    } else if (ta) {
      ta.value = content;
      ta.focus();
    }

    var status = document.getElementById('editor-status');
    if (status) status.textContent = (d.size || 0) + ' bytes | ' + (content.split('\n').length + ' lines');

    // Auto-save on change (debounced 2s)
    if (window._editorCM) {
      window._editorAutoSaveTimer = null;
      window._editorCM.on('change', function() {
        if (window._editorAutoSaveTimer) clearTimeout(window._editorAutoSaveTimer);
        window._editorAutoSaveTimer = setTimeout(function() {
          if (window._editorCM && window._editorCM.getValue() !== _editorOriginalContent) {
            _editorSave(true);
          }
        }, 2000);
      });
    }

    // Auto-preview HTML
    if (filePath.endsWith('.html') || filePath.endsWith('.htm')) {
      _autoPreviewHtml(filePath, content);
    }
  } catch(e) {
    var status = document.getElementById('editor-status');
    if (status) status.textContent = 'Error: ' + e.message;
  }
}

function _codeMirrorMode(ext) {
  var map = {
    js: 'javascript', ts: 'javascript', jsx: 'javascript', tsx: 'javascript',
    py: 'python', rb: 'python',
    html: 'htmlmixed', htm: 'htmlmixed',
    css: 'css', scss: 'css', less: 'css',
    json: 'javascript',
    md: 'markdown', mkd: 'markdown',
    yml: 'yaml', yaml: 'yaml',
    sh: 'shell', bash: 'shell', zsh: 'shell',
    sql: 'sql',
    xml: 'xml', svg: 'xml',
  };
  return map[ext] || 'textile';
}

async function _editorSave(silent) {
  var content;
  if (window._editorCM) {
    content = window._editorCM.getValue();
  } else {
    var ta = document.getElementById('editor-textarea');
    if (!ta) return;
    content = ta.value;
  }
  var btn = document.getElementById('editor-save-btn');
  if (!silent && btn) {
    btn.disabled = true;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Saving...';
  }

  try {
    var r = await fetch('/api/sandbox/file', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({path: _editorCurrentPath, content: content})
    });
    var d = await r.json();
    if (d.status === 'ok') {
      _editorOriginalContent = content;
      if (!silent) showToast('Saved', 'success');
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save'; }
      if (_editorCurrentPath.endsWith('.html') || _editorCurrentPath.endsWith('.htm')) {
        _autoPreviewHtml(_editorCurrentPath, content);
      }
    } else {
      if (!silent) showToast('Save failed: ' + (d.error || 'Unknown'), 'error');
      if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save'; }
    }
  } catch(e) {
    if (!silent) showToast('Save error: ' + e.message, 'error');
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-floppy-disk"></i> Save'; }
  }
}

window._editorSave = _editorSave;

async function _editorRun() {
  var btn = document.getElementById('editor-run-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Running...'; }

  var content;
  if (window._editorCM) {
    content = window._editorCM.getValue();
  } else {
    var ta = document.getElementById('editor-textarea');
    if (!ta) return;
    content = ta.value;
  }

  // Save first
  await _editorSave(true);

  // Detect command based on file extension
  var ext = _editorCurrentPath.split('.').pop().toLowerCase();
  var cmdMap = { py: 'python3', js: 'node', ts: 'npx ts-node', sh: 'bash', bash: 'bash', go: 'go run', rb: 'ruby', php: 'php', pl: 'perl', lua: 'lua', r: 'Rscript' };
  var runner = cmdMap[ext];
  if (!runner) {
    if (ext === 'html' || ext === 'htm') { _autoPreviewHtml(_editorCurrentPath, content); if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Run'; } return; }
    showToast('No runner for .' + ext + ' files', 'info');
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Run'; }
    return;
  }

  // Show terminal
  var tabs = document.querySelectorAll('.right-panel-tab');
  for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].textContent.toLowerCase().indexOf('terminal') !== -1) { switchTab(tabs[i], 'terminal'); break; }
  }

  // Execute in terminal
  var cmd = runner + ' ' + _editorCurrentPath;
  var o = document.getElementById('to');
  if (o) {
    o.innerHTML += '\n<span class="text-accent">$ ' + escapeHtml(cmd) + '</span>\n';
    execTermCmd(cmd, o);
  } else {
    showTerminal();
    setTimeout(function() {
      var o2 = document.getElementById('to');
      if (o2) { o2.innerHTML += '\n<span class="text-accent">$ ' + escapeHtml(cmd) + '</span>\n'; execTermCmd(cmd, o2); }
    }, 200);
  }

  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-play"></i> Run'; }
}

/* ═══════════════ PHASE 2: AUTO PREVIEW ═══════════════════ */

function _autoPreviewHtml(filePath, content) {
  // If browser tab exists, preview the generated HTML
  var bf = document.getElementById('bf');
  var bu = document.getElementById('bu');
  if (bf && bu) {
    // Write to a temp file and load in iframe
    // Or use blob URL for instant preview
    var blob = new Blob([content], {type: 'text/html'});
    var url = URL.createObjectURL(blob);
    bf.src = url;
    bu.value = 'file://' + filePath;
    // Find browser tab by text content
    var tabs = document.querySelectorAll('.right-panel-tab');
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].textContent.toLowerCase().indexOf('browser') !== -1) {
        switchTab(tabs[i], 'browser');
        break;
      }
    }
  }
}

/* ═══════════════ PHASE 2: PROCESS MANAGER ═══════════════════ */

async function showProcessManager() {
  const body = document.getElementById('panelBody');
  body.innerHTML = '<div class="process-manager">'
    + '<div class="process-header">'
    + '<span class="proc-title"><i class="fa-solid fa-microchip"></i> Process Manager</span>'
    + '<button class="file-explorer-btn" data-click="proc-refresh" title="Refresh"><i class="fa-solid fa-rotate"></i></button>'
    + '<button class="file-explorer-btn" id="proc-live-btn" data-click="proc-toggle-live" title="Toggle live refresh">● Live</button>'
    + '</div>'
    + '<div class="process-body" id="proc-body">'
    + '<div class="process-empty"><i class="fa-solid fa-spinner fa-spin"></i><span>Loading processes...</span></div>'
    + '</div>'
    + '</div>';
  await _loadProcesses();
  _startProcessAutoRefresh();
}

var _procRefreshTimer = null;

function _startProcessAutoRefresh() {
  if (_procRefreshTimer) clearInterval(_procRefreshTimer);
  _procRefreshTimer = setInterval(function() {
    _loadProcesses(true);
  }, 5000);
}

function _stopProcessAutoRefresh() {
  if (_procRefreshTimer) {
    clearInterval(_procRefreshTimer);
    _procRefreshTimer = null;
  }
}

CLICK_HANDLERS['proc-toggle-live'] = function() {
  var btn = document.getElementById('proc-live-btn');
  if (_procRefreshTimer) {
    _stopProcessAutoRefresh();
    if (btn) btn.style.opacity = '0.5';
  } else {
    _startProcessAutoRefresh();
    if (btn) btn.style.opacity = '1';
  }
};

async function _loadProcesses(silent) {
  var body = document.getElementById('proc-body');
  if (!body) return;
  if (!silent) body.innerHTML = '<div class="process-empty"><i class="fa-solid fa-spinner fa-spin"></i><span>Loading processes...</span></div>';
  try {
    var r = await fetch('/api/sandbox/processes');
    var d = await r.json();
    if (d.error || !d.processes || !d.processes.length) {
      body.innerHTML = '<div class="process-empty"><i class="fa-solid fa-inbox"></i><span>No processes found</span></div>';
      return;
    }
    var html = '';
    d.processes.forEach(function(proc) {
      var status = proc.status || 'running';
      var statusDot = status === 'running' ? '🟢' : status === 'sleeping' ? '🟡' : '⚪';
      html += '<div class="process-item">'
        + '<span class="proc-pid">' + escapeHtml(proc.pid) + '</span>'
        + '<span class="proc-name">' + escapeHtml(proc.command || proc.name || '?') + '</span>'
        + '<span class="proc-cpu">' + (proc.cpu != null ? proc.cpu + '%' : '') + '</span>'
        + '<span class="proc-mem">' + (proc.mem != null ? proc.mem : '') + '</span>'
        + '<span class="proc-status">' + statusDot + '</span>'
        + '<button class="proc-kill-btn" data-click="proc-kill" data-pid="' + escapeHtml(proc.pid) + '" title="Kill"><i class="fa-solid fa-xmark"></i></button>'
        + '</div>';
    });
    body.innerHTML = html;
  } catch(e) {
    if (!silent) body.innerHTML = '<div class="process-empty text-error"><i class="fa-solid fa-triangle-exclamation"></i><span>' + escapeHtml(e.message) + '</span></div>';
  }
}

async function _killProcess(pid) {
  try {
    var r = await fetch('/api/sandbox/processes/' + encodeURIComponent(pid) + '/kill', {method: 'POST'});
    var d = await r.json();
    if (d.status === 'ok') {
      showToast('Process ' + pid + ' killed', 'success');
      showProcessManager();
    } else {
      showToast('Failed: ' + (d.error || 'Unknown'), 'error');
    }
  } catch(e) {
    showToast('Error: ' + e.message, 'error');
  }
}

// ── Helper: escapeJs for single-quoted strings ──
function escapeJs(str) {
  if (!str) return '';
  return String(str).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

// ═══════════════ PHASE 4: EXPORT SYSTEM ═══════════════════

function _showExportDialog() {
  var existing = document.getElementById('export-dialog');
  if (existing) { existing.remove(); return; }

  var overlay = document.createElement('div');
  overlay.id = 'export-dialog';
  overlay.className = 'dialog-overlay open';
  overlay.innerHTML = '<div class="dialog-box" style="max-width:420px"><div class="dialog-icon info"><i class="fa-solid fa-file-export"></i></div>'
    + '<div class="dialog-title">Export Conversation</div><div class="dialog-desc text-sm text-muted" style="margin-bottom:16px">'
    + (S.messages?.length || 0) + ' messages in this session</div>'
    + '<div style="display:flex;flex-direction:column;gap:8px">'
    + '<button class="send-btn w-full" data-click="export-markdown"><i class="fa-solid fa-clipboard"></i> Copy as Markdown</button>'
    + '<button class="send-btn w-full" data-click="export-markdown-dl"><i class="fa-solid fa-download"></i> Download as .md</button>'
    + '<button class="send-btn w-full" data-click="export-json"><i class="fa-solid fa-code"></i> Download as .json</button>'
    + '</div>'
    + '<div class="dialog-actions" style="margin-top:16px"><button class="dialog-btn secondary" data-click="close-export-dialog">Cancel</button></div></div>';
  document.body.appendChild(overlay);
}

function _exportChat(format, download) {
  var ext = format === 'json' ? 'json' : 'md';
  var ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
  var filename = 'widdx-export-' + ts + '.' + ext;

  var messages = S.messages || [];
  var content = '';

  if (format === 'json') {
    content = JSON.stringify({
      exportedAt: new Date().toISOString(),
      model: S.model || '—',
      messageCount: messages.length,
      messages: messages.map(function(m) { return { role: m.role, content: m.content, canvas: m.canvas || null, timestamp: m.timestamp || null }; })
    }, null, 2);
  } else {
    content = messages.map(function(m) {
      var role = m.role === 'user' ? '👤 **You**' : m.role === 'assistant' ? '🤖 **WIDDX**' : 'ℹ️ **System**';
      return role + '\n\n' + (m.content || '') + '\n\n---\n';
    }).join('\n');
    content = '# WIDDX Nexus — Conversation Export\n\n_Exported: ' + new Date().toLocaleString() + '_\n\n' + content;
  }

  if (download) {
    var blob = new Blob([content], { type: format === 'json' ? 'application/json' : 'text/markdown' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
    showToast('Downloaded: ' + filename, 'success');
  } else {
    navigator.clipboard.writeText(content).then(function() {
      showToast('Copied to clipboard!', 'success');
    }).catch(function() {
      showToast('Failed to copy', 'error');
    });
  }

  var dialog = document.getElementById('export-dialog');
  if (dialog) dialog.remove();
}

async function showScreenshot() {
  const body = document.getElementById('panelBody');
  body.innerHTML = '<div class="screenshot-container">'
    + '<button id="ss-btn" class="screenshot-btn" data-click="take-screenshot"><i class="fa-solid fa-camera"></i> Take Screenshot</button>'
    + '<div id="ss-result" class="screenshot-result">Click the button to capture a browser screenshot.</div></div>';
}

window.takeScreenshot = async function() {
  var btn = document.getElementById('ss-btn');
  var res = document.getElementById('ss-result');
  if (btn) { btn.disabled = true; btn.textContent = 'Capturing...'; }
  if (res) res.innerHTML = '<span class="text-muted"><i class="fa-solid fa-spinner fa-spin"></i> Taking screenshot...</span>';
  try {
    const r = await fetch('/api/sandbox/screenshot', { method:'POST' });
    const d = await r.json();
    if (d.success && d.data) {
      var imgUrl = typeof d.data === 'string' && d.data.startsWith('data:') ? d.data : (d.data.image_url || d.data.url || '');
      if (imgUrl) {
        if (res) res.innerHTML = '<img src="' + escapeHtml(imgUrl) + '" class="screenshot-img">';
      } else {
        if (res) res.innerHTML = '<pre class="text-xs text-muted max-h-screen overflow-auto">' + escapeHtml(JSON.stringify(d.data, null, 2)) + '</pre>';
      }
    } else {
      if (res) res.innerHTML = '<span class="text-error">' + escapeHtml(d.error || 'Screenshot failed') + '</span>';
    }
  } catch(e) {
    if (res) res.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  }
  if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-camera"></i> Take Screenshot'; }
};

function previewFileInBrowser(path) {
  if (path.endsWith('.html') || path.endsWith('.htm')) {
    document.getElementById('bu').value = path;
    document.getElementById('bf').src = path;
    // Find browser tab by querying its text content
    var tabs = document.querySelectorAll('.right-panel-tab');
    for (var i = 0; i < tabs.length; i++) {
      if (tabs[i].textContent.toLowerCase().indexOf('browser') !== -1) {
        switchTab(tabs[i], 'browser');
        break;
      }
    }
  }
}

// ═══════════════ INIT ═══════════════════

document.addEventListener('DOMContentLoaded', function() {
  var ob = document.getElementById('onboarding');
  if (ob) ONBOARDING_HTML = ob.outerHTML;

  // Nav clicks are handled via addEventListener below — setupNavClicks() removed (P1 duplicate fix)
  var _bootReady = Promise.allSettled([
    loadAppTheme(),
    loadStatus(),
    loadProjectSession(),
  ]);
  loadSidebar();    // #4: Event listeners — sidebar, header, input
    document.getElementById('sidebarNewTask').addEventListener('click', function() {
      if (typeof newSession === 'function') newSession();
      else showView('chat');
      if (window.innerWidth < 820) toggleSidebar();
    });
    document.getElementById('hamburgerBtn').addEventListener('click', function() { toggleSidebar(); });
    document.getElementById('sidebarFloatingToggle').addEventListener('click', function() { toggleSidebar(); });
    document.getElementById('sidebarBackdrop').addEventListener('click', function() {
      if (window.innerWidth < 820) toggleSidebar();
    });
    document.getElementById('scrollBottomBtn').addEventListener('click', function() { scrollBottom(); });
    document.getElementById('cancelBtn').addEventListener('click', function() { cancelAgent(); });
    document.getElementById('sendBtn').addEventListener('click', function() { sendMessage(); });
    document.getElementById('langToggleBtn').addEventListener('click', function() { Lang.toggle(); });
    document.getElementById('starBtn').addEventListener('click', function() { this.classList.toggle('active'); });
    document.getElementById('modelSelector').addEventListener('click', function(e) { toggleModelDropdown(e); });
    document.getElementById('modelDropdownFooter').addEventListener('click', function() { showView('settings'); });

    // Event delegation for all .nav-item[data-view] elements
    document.querySelectorAll('.nav-item[data-view]').forEach(function(item) {
      item.addEventListener('click', function() {
        showView(this.dataset.view);
      });
    });

    showTerminal();

    // Activity Bar — navigation to views
    document.querySelectorAll('.act-icon[data-panel]').forEach(function(icon) {
      icon.addEventListener('click', function() {
        var panel = this.getAttribute('data-panel');
        document.querySelectorAll('.act-icon').forEach(function(i) { i.classList.remove('active'); });
        this.classList.add('active');
        if (panel === 'chat') { showView('chat'); }
        else if (panel === 'dashboard') { showView('dashboard'); }
        else if (panel === 'settings') { showView('settings'); }
      });
    });

    // Nav Category accordion toggles
    document.querySelectorAll('.nav-category-header').forEach(function(header) {
      header.addEventListener('click', function() {
        var body = this.nextElementSibling;
        if (!body || !body.classList.contains('nav-category-body')) return;
        var opened = body.classList.toggle('open');
        this.classList.toggle('open', opened);
      });
    });

    initWebSocket();
  initEventStream();

  // Periodic refresh
  setInterval(loadStatus, 30000);
  setInterval(loadSidebar, 60000);

  // ── Voice input ──────────────────────────────────────
  var _voiceListening = false;
  var _recognition = null;
  window.toggleVoiceInput = function() {
    var micBtn = document.getElementById('micBtn');
    if (!window.webkitSpeechRecognition && !window.SpeechRecognition) {
      showToast('🎤 Voice input not supported in this browser', 'error');
      return;
    }
    if (_voiceListening) { stopVoice(); return; }
    var SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    _recognition = new SR();
    _recognition.lang = document.documentElement.lang === 'ar' ? 'ar-SA' : 'en-US';
    _recognition.interimResults = false;
    _recognition.onresult = function(e) {
      var input = document.getElementById('messageInput');
      input.value = e.results[0][0].transcript;
      _voiceListening = false;
      if (micBtn) { micBtn.style.color = ''; micBtn.classList.remove('listening'); }
      showToast('🎤 Voice captured!', 'success');
      sendMessage();
    };
    _recognition.onerror = function(e) {
      stopVoice();
      var msgs = {'not-allowed': 'Microphone access denied', 'no-speech': 'No speech detected', 'audio-capture': 'No microphone found', 'network': 'Network error'};
      showToast('🎤 ' + (msgs[e.error] || e.error || 'Voice error'), 'error');
    };
    _recognition.start();
    _voiceListening = true;
    if (micBtn) { micBtn.style.color = '#f04848'; micBtn.classList.add('listening'); }
    showToast('🎤 Listening...', 'info');
  };
  function stopVoice() {
    _voiceListening = false;
    if (_recognition) { try { _recognition.stop(); } catch(e) {} _recognition = null; }
    var micBtn = document.getElementById('micBtn');
    if (micBtn) { micBtn.style.color = ''; micBtn.classList.remove('listening'); }
  }

  // ── Image upload (vision) ────────────────────────────
  window.handleImageUpload = function(e) {
    var file = e.target.files[0];
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { showToast('Image too large (max 5MB)', 'error'); return; }
    showUploadPreview(file.name, '🖼️');
    var reader = new FileReader();
    reader.onload = function(ev) {
      var base64 = ev.target.result.split(',')[1];
      var userMsg = { role: 'user', content: '[Image attached: ' + file.name + ']', image: base64 };
      S.messages.push(userMsg);
      renderMsg('user', '<i class=\"fa-solid fa-image\"></i> ' + file.name);
      clearUploadPreview();
      fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: 'Describe this image in detail.', history: S.messages })
      }).then(function(r) { return r.json(); })
        .then(function(d) { if (d.reply) renderMsg('assistant', d.reply); })
        .catch(function(err) { showToast('Vision failed: ' + err.message, 'error'); });
    };
    reader.readAsDataURL(file);
    e.target.value = '';
  };

  // ── File upload ──────────────────────────────────────
  window.handleFileUpload = function(e) {
    var file = e.target.files[0];
    if (!file) return;
    if (file.size > 2 * 1024 * 1024) { showToast('File too large (max 2MB)', 'error'); return; }
    showUploadPreview(file.name, '📎');
    var reader = new FileReader();
    reader.onload = function(ev) {
      var content = ev.target.result;
      var preview = content.length > 2000 ? content.substring(0, 2000) + '\n... (truncated)' : content;
      var userMsg = { role: 'user', content: 'Uploaded file: ' + file.name + '\n\n```\n' + preview + '\n```' };
      S.messages.push(userMsg);
      renderMsg('user', '<i class=\"fa-solid fa-file\"></i> ' + file.name + ' (' + (file.size / 1024).toFixed(1) + ' KB)');
      clearUploadPreview();
      var input = document.getElementById('messageInput');
      input.value = 'Review the attached file: ' + file.name;
      sendMessage();
    };
    reader.readAsText(file);
    e.target.value = '';
  };

  function showUploadPreview(name, icon) {
    var existing = document.getElementById('uploadPreview');
    if (existing) existing.remove();
    var div = document.createElement('div');
    div.id = 'uploadPreview';
    div.className = 'upload-preview';
    div.innerHTML = icon + ' ' + escapeHtml(name) + ' <span class=\"upload-preview-close\" data-click=\"clear-upload\">✕</span>';
    var toolbar = document.querySelector('.input-toolbar');
    if (toolbar) toolbar.parentNode.insertBefore(div, toolbar);
  }

  window.clearUploadPreview = function() {
    var el = document.getElementById('uploadPreview');
    if (el) el.remove();
  };

  // ── Project Docs viewer ──────────────────────────────
  window.showProjectDocsView = function(area) {
    area.innerHTML = '<div class=\"p-24 max-w-900 mx-auto\">'
      + '<h2 class=\"mb-16\"><i class=\"fa-solid fa-book\"></i> Project Documentation</h2>'
      + '<div class=\"docs-grid\" id=\"docsGrid\">Loading…</div>'
      + '</div>';
    var docs = ['PLAN.md', 'DESIGN.md', 'TASKS.md', 'ROADMAP.md'];
    var loaded = 0;
    var html = '';
    docs.forEach(function(doc) {
      fetch('/api/project/docs/' + doc).then(function(r) { return r.json(); })
        .then(function(data) {
          loaded++;
          var content = (data.content || '').replace(/</g, '&lt;').replace(/>/g, '&gt;').substring(0, 3000);
          html += '<div class=\"bg-card border-main rounded-lg p-16\">'
            + '<h3 class=\"mb-8 text-accent\" style=\"margin-top:0\">' + doc + '</h3>'
            + '<pre class=\"text-pre-wrap text-sm text-secondary max-h-300 overflow-y-auto\">' + (content || '(empty)') + '</pre>'
            + '</div>';
          if (loaded === docs.length) {
            document.getElementById('docsGrid').innerHTML = html || '<p>No project docs found. Start a chat to auto-create them.</p>';
          }
        }).catch(function() { loaded++; });
    });
  }

  // ── Session search ───────────────────────────────────
  window.showSearchView = function(area) {
    area.innerHTML = '<div class=\"p-24 max-w-900 mx-auto\">'
      + '<h2 class=\"mb-16\"><i class=\"fa-solid fa-magnifying-glass\"></i> Search Sessions</h2>'
      + '<input id=\"searchInput\" class=\"search-input\" placeholder=\"Search messages, sessions, memories…\" oninput=\"doSearch(this.value)\">'
      + '<div id=\"searchResults\" class=\"flex-col gap-8\"></div>'
      + '</div>';
  }

  window.doSearch = function(q) {
    var container = document.getElementById('searchResults');
    if (!container) return;
    if (!q || q.length < 2) { container.innerHTML = ''; return; }
    fetch('/api/dashboard/sessions?q=' + encodeURIComponent(q))
      .then(function(r) { return r.json(); })
      .then(function(sessions) {
        if (!sessions || !sessions.length) {
          container.innerHTML = '<p class=\"text-muted\">No results for \"' + escapeHtml(q) + '\"</p>';
          return;
        }
        container.innerHTML = sessions.slice(0, 20).map(function(s) {
          return '<div class=\"bg-card border-main rounded-lg cursor-pointer\" style=\"padding:12px 16px\" data-click=\"load-session\" data-session=\"' + (s.id || '') + '\">'
            + '<strong>' + escapeHtml(s.name || 'Untitled') + '</strong>'
            + '<span class=\"text-muted text-xs\" style=\"float:right\">' + (s.branch || 'main') + '</span>'
            + '<br><span class=\"text-muted text-sm\">' + (s.created || '') + ' · ' + (s.msg_count || 0) + ' messages</span>'
            + '</div>';
        }).join('');
      }).catch(function() {
        container.innerHTML = '<p class=\"text-muted\">Search failed. Try again.</p>';
      });
  };

  // ── Plan view — project status + task progress ───────
  window.showPlanView = function(area) {
    area.innerHTML = '<div class="p-24 max-w-900 mx-auto"><h2><i class="fa-solid fa-list-check"></i> Project Plan</h2><div id="planContent">Loading…</div></div>';
    var docs = ['PLAN.md', 'TASKS.md', 'ROADMAP.md'];
    var loaded = 0;
    var html = '';
    docs.forEach(function(doc) {
      fetch('/api/project/docs/' + doc).then(function(r){return r.json()})
        .then(function(d){
          loaded++;
          var content = (d.content || '');
          var tasks = [];
          if (doc === 'TASKS.md') {
            // Parse task statuses
            var done = (content.match(/\[x\]|✅|done|completed/gi) || []).length;
            var pending = (content.match(/\[ \]|todo|in-progress/gi) || []).length;
            tasks.push('<span class="text-success">✅ ' + done + ' done</span>');
            tasks.push('<span class="text-warning">⏳ ' + pending + ' pending</span>');
            document.getElementById('planBadge').textContent = done + '/' + (done + pending);
            document.getElementById('planBadge').style.display = '';
          }
          html += '<div class="bg-card border-main rounded-lg p-16 mb-12">'
            + '<h3 class="text-accent" style="margin:0 0 4px">' + doc + (tasks.length ? ' <span style="font-size:14px">' + tasks.join(' · ') + '</span>' : '') + '</h3>'
            + '<pre class="text-pre-wrap text-sm text-secondary max-h-400 overflow-y-auto line-height-1_5">' + (content || '(empty — start a chat to auto-create)') + '</pre>'
            + '</div>';
          if (loaded === docs.length) {
            document.getElementById('planContent').innerHTML = html || '<p>No plan docs yet. Start a chat to auto-create them.</p>';
          }
        }).catch(function(){ loaded++; });
    });
  };

  // ── Autonomous Mode toggle ───────────────────────────
  S.autoMode = false;
  window.toggleAutoMode = function() {
    S.autoMode = !S.autoMode;
    var btn = document.getElementById('autoModeBtn');
    var label = document.getElementById('autoModeLabel');
    if (S.autoMode) {
      if (btn) btn.style.background = 'var(--accent-primary)';
      if (label) { label.textContent = 'ON'; label.style.color = '#fff'; }
      showToast('🤖 Autonomous Mode ON — AI will plan, execute, verify, fix, and learn automatically', 'success');
    } else {
      if (btn) btn.style.background = '';
      if (label) { label.textContent = 'AUTO'; label.style.color = ''; }
      showToast('Autonomous Mode OFF — Manual control', 'info');
    }
  };

  // ── Diff preview helper ──────────────────────────────
  window.showDiffPreview = function(original, modified) {
    var area = document.getElementById('messagesArea');
    if (!area) return;
    var diffHtml = '<div class=\"diff-container\">'
      + '<h4 style=\"margin:0 0 8px\">Diff Preview</h4>'
      + '<pre class=\"diff-preview\">';
    var lines1 = original.split('\n');
    var lines2 = modified.split('\n');
    var maxLen = Math.max(lines1.length, lines2.length);
    for (var i = 0; i < maxLen; i++) {
      var l1 = lines1[i] || '';
      var l2 = lines2[i] || '';
      if (l1 !== l2) {
        if (l1) diffHtml += '<span class=\"diff-line-removed\">- ' + escapeHtml(l1) + '</span>\n';
        if (l2) diffHtml += '<span class=\"diff-line-added\">+ ' + escapeHtml(l2) + '</span>\n';
      } else {
        diffHtml += '<span class=\"diff-line-unchanged\">  ' + escapeHtml(l1) + '</span>\n';
      }
    }
    diffHtml += '</pre></div>';
    area.insertAdjacentHTML('beforeend', diffHtml);
  };

  // ── Hide boot screen after all init calls complete ──
  _bootReady.then(function() {
    var bootScreen = document.getElementById('bootScreen');
    if (!bootScreen) return;
    var bootStatus = document.getElementById('bootStatus');
    if (bootStatus) bootStatus.textContent = 'Ready';
    bootScreen.classList.add('hidden');
    setTimeout(function() {
      if (bootScreen.parentNode) bootScreen.parentNode.removeChild(bootScreen);
    }, 700);
  });
});

// ═══════════════ PHASE 3: ULTRA-SMART CANVAS SYSTEM ═══════════════════

// ── Analysis Engine: deep content understanding ──
function __analyzeContent(c) {
  if (!c || typeof c !== 'string' || c.trim().length < 20) return null;
  var a = {
    headings: [], headWords: [], tableCount: 0, codeCount: 0, listCount: 0,
    wordCount: 0, charCount: 0, avgWordLen: 0, codeRatio: 0, tableRatio: 0,
    hasFAQ: false, hasChangelog: false, hasRecipe: false, hasAPIDoc: false,
    hasTutorial: false, hasDataReport: false, hasTimeline: false,
    hasComparison: false, hasTravel: false, hasGlossary: false,
    hasTaskList: false, hasArchitecture: false, isStructured: false,
    sections: [], sigStrength: 0,
  };
  a.wordCount = c.split(/\s+/).length;
  a.charCount = c.length;
  a.avgWordLen = a.wordCount ? Math.round(a.charCount / a.wordCount) : 0;

  var h = c.match(/^#{2,4}\s+.+/gm);
  if (h) a.headings = h.map(function(v) { return { level: v.match(/^#+/)[0].length, text: v.replace(/^#+\s*/, '') }; });
  a.headWords = (c.match(/\b(?:introduction|overview|conclusion|summary|setup|installation|usage|configuration|api|examples?|faq|troubleshooting|license)\b/gi) || []);

  a.tableCount = (c.match(/^\|.+\|[\s\S]*?^\|.+\|$/gm) || []).length;
  a.codeCount = (c.match(/```[\s\S]*?```/g) || []).length;
  a.listCount = (c.match(/^[*-]\s/gm) || []).length;

  a.codeRatio = a.wordCount ? a.codeCount / (a.wordCount / 50) : 0;
  a.tableRatio = a.wordCount ? a.tableCount / (a.wordCount / 100) : 0;

  // FAQ detection: Q: / A: or Question: / Answer: patterns
  var qaLines = c.match(/^(?:[-*]\s*)?(?:\*\*)?[QAqa][^:]*:{1,2}\s+/gm);
  a.hasFAQ = (qaLines || []).length >= 4;

  // Changelog: version numbers + dates
  a.hasChangelog = (c.match(/^#{1,3}\s+v?\d+\.\d+/gm) || []).length >= 2
    || (c.match(/^##?\s*\[\d+\.\d+/) || []).length >= 1;

  // Recipe: ingredients + steps + time
  a.hasRecipe = /\b(ingredients?|instructions?|steps?|prep[ .]time|cook[ .]time|servings?)\b/i.test(c)
    && (c.match(/^[*-]\s/gm) || []).length >= 3;

  // API Doc: endpoints + methods + parameters
  a.hasAPIDoc = /\b(GET|POST|PUT|DELETE|PATCH|endpoint|API|request|response|parameter)\b/i.test(c)
    && a.headWords.indexOf('api') !== -1 || (c.match(/\b(GET|POST|PUT|DELETE)\s+\/\S+/g) || []).length >= 1;

  // Tutorial: prerequisites + step-by-step + examples
  a.hasTutorial = /\b(prerequisites?|getting started|step[\s-]by[\s-]step|tutorial|guide|walkthrough)\b/i.test(c)
    && a.headings.length >= 2 && a.codeCount >= 1;

  // Data Report: numbers, percentages, trends
  a.hasDataReport = (c.match(/\d+\.?\d*\s*(?:%|GB|MB|KB|ms|sec|users|requests|growing|declining|increased|decreased)/g) || []).length >= 4
    && a.tableCount >= 1;

  // Travel itinerary: Day N, times, locations
  a.hasTravel = /\b(Day\s+\d+|itinerary|hotel|flight|check-in|depart|arrive)\b/im.test(c)
    && a.headings.length >= 2;

  // Comparison: vs, versus, pros/cons
  a.hasComparison = /\b(vs\.?|versus|alternatives?|pros?|cons?|advantages?|disadvantages?)\b/i.test(c)
    && (a.tableCount >= 1 || a.listCount >= 4);

  // Glossary: **term**: definition
  var gm = c.match(/^\*\*[^*]+\*\*\s*[:—\-]/gm);
  a.hasGlossary = (gm || []).length >= 3;

  // Timeline: Year at start of list items
  a.hasTimeline = (c.match(/^[*-]\s+\d{4}[\s:]/gm) || []).length >= 2;

  // Task list: - [ ] or - [x]
  a.hasTaskList = /^\s*[*-]\s*\[[\sxX]\]/m.test(c);

  // Architecture/system design
  a.hasArchitecture = /\b(?:architecture|system design|components?|layers?|pipeline|infrastructure)\b/i.test(c)
    && a.headings.length >= 2;

  // Signal strength: number of positive detections
  var signals = [
    a.headings.length >= 2, a.tableCount >= 1, a.codeCount >= 1,
    a.hasFAQ, a.hasChangelog, a.hasRecipe, a.hasAPIDoc, a.hasTutorial,
    a.hasDataReport, a.hasTravel, a.hasComparison, a.hasGlossary,
    a.hasTimeline, a.hasTaskList, a.hasArchitecture
  ];
  a.sigStrength = signals.filter(function(s) { return s; }).length;

  a.isStructured = a.sigStrength >= 2 || a.headings.length >= 2 || a.tableCount >= 1;

  // Sections by h2
  var lines = c.split('\n');
  var cur = { heading: null, body: [] };
  for (var i = 0; i < lines.length; i++) {
    if (/^##\s/.test(lines[i])) {
      if (cur.heading || cur.body.length) a.sections.push(cur);
      cur = { heading: lines[i].replace(/^##\s*/, ''), body: [] };
    } else cur.body.push(lines[i]);
  }
  if (cur.heading || cur.body.length) a.sections.push(cur);

  return a;
}

// ── Canvas Registry ──
var __canvasTypes = [];
function __registerCanvas(c) { __canvasTypes.push(c); }

// ── Smart Dispatcher ──
function canvasDispatcher(content) {
  var a = __analyzeContent(content);
  if (!a || a.wordCount < 30) return null;

  var best = null, bestScore = -1;
  for (var i = 0; i < __canvasTypes.length; i++) {
    var r = __canvasTypes[i].detect(a, content);
    if (r && r.score > bestScore) {
      best = { name: __canvasTypes[i].name, data: r.data, render: __canvasTypes[i].render, score: r.score };
      bestScore = r.score;
    }
  }
  // Fallback: always render with at least base enhancements
  if (!best || bestScore < 20) {
    var fbData = { headings: a.headings, sections: a.sections };
    best = { name: 'fallback', data: fbData, render: function(d, c) { return __smartFallback(c, d); }, score: 10 };
  }
  return best;
}

// ── Length factor: short content → lower score ──
function __lenFactor(wc) {
  if (wc < 80) return 0.3;
  if (wc < 150) return 0.6;
  if (wc < 300) return 0.9;
  if (wc > 1500) return 0.85;
  return 1.0;
}

// ── Document Canvas: structured docs, guides, reports ──
__registerCanvas({
  name: 'document',
  detect: function(a) {
    if (a.headings.length < 2 || a.wordCount < 100) return null;
    var base = a.headings.length >= 4 ? 80 : a.headings.length >= 3 ? 70 : 50;
    if (a.hasTutorial) base += 15;
    if (a.hasDataReport) base += 10;
    if (a.headWords.length >= 2) base += 5;
    return { score: base * __lenFactor(a.wordCount), data: { headings: a.headings } };
  },
  render: function(d, c) {
    var tocHTML = '<div class="can-toc-hdr">📑 Contents (' + d.headings.length + ')</div>'
      + d.headings.map(function(h) {
        var id = h.text.replace(/[^\w\u0600-\u06FF\s-]/g, '').replace(/\s+/g, '-').toLowerCase();
        return '<a href="#can-s-' + id + '" class="can-toc-i" style="padding-left:' + ((h.level - 2) * 14 + 4) + 'px">' + escapeHtml(h.text) + '</a>';
      }).join('');
    var html = parseMarkdown(c);
    d.headings.forEach(function(h) {
      var id = h.text.replace(/[^\w\u0600-\u06FF\s-]/g, '').replace(/\s+/g, '-').toLowerCase();
      var esc = escapeHtml(h.text).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
      html = html.replace(new RegExp('<h' + h.level + '>' + esc + '</h' + h.level + '>'), '<h' + h.level + ' id="can-s-' + id + '">' + escapeHtml(h.text) + '</h' + h.level + '>');
    });
    return '<div class="can-doc"><div class="can-toc">' + tocHTML + '</div><div class="can-body">' + html + '</div></div>';
  }
});

// ── Table Canvas: data tables ──
__registerCanvas({
  name: 'table',
  detect: function(a) {
    if (!a.tableCount) return null;
    var base = 50 + a.tableCount * 12;
    if (a.hasDataReport) base += 15;
    if (a.hasComparison) base += 10;
    if (a.tableRatio > 0.3) base += 10;
    return { score: base * __lenFactor(a.wordCount), data: { count: a.tableCount } };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<table>/g, '<table class="can-tbl">');
    html = html.replace(/<th>/g, '<th class="can-tbl-h">');
    return '<div class="can-tables">' + html + '</div>';
  }
});

// ── Code Canvas: tutorials, code-heavy docs ──
__registerCanvas({
  name: 'code',
  detect: function(a) {
    if (!a.codeCount || a.codeRatio < 0.2) return null;
    var base = 40 + Math.min(a.codeCount * 20, 60);
    if (a.hasAPIDoc) base += 15;
    if (a.hasTutorial) base += 10;
    if (a.codeRatio > 0.6) base += 15;
    return { score: base * __lenFactor(a.wordCount), data: { count: a.codeCount } };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    var idx = 0;
    html = html.replace(/<pre><code class="language-(\w+)">/g, function(m, l) {
      idx++;
      return '<div class="can-cd"><div class="can-cd-h"><span class="can-cd-l">' + l + '</span><span class="can-cd-n">#' + idx + '</span></div><pre><code class="language-' + l + '">';
    });
    html = html.replace(/<pre><code>/g, function() {
      idx++;
      return '<div class="can-cd"><div class="can-cd-h"><span class="can-cd-l">code</span><span class="can-cd-n">#' + idx + '</span></div><pre><code>';
    });
    html = html.replace(/<\/code><\/pre>/g, '</code></pre></div>');
    return '<div class="can-codes">' + html + '</div>';
  }
});

// ── Travel Canvas ──
__registerCanvas({
  name: 'travel',
  detect: function(a) {
    if (!a.hasTravel) return null;
    return { score: 85 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<strong>(Day\s+\d+[^<]*)<\/strong>/gi, '<span class="can-day">📅 $1</span>');
    html = html.replace(/<h3>([^<]+)<\/h3>/g, function(m, t) {
      if (/(hotel|flight|loc|activity|meal|transport)/i.test(t)) return '<h3 class="can-trv-h">📍 ' + t + '</h3>';
      return m;
    });
    return '<div class="can-trv">' + html + '</div>';
  }
});

// ── Comparison Canvas ──
__registerCanvas({
  name: 'comparison',
  detect: function(a) {
    if (!a.hasComparison) return null;
    return { score: 75 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<table>/g, '<table class="can-tbl can-cmp">');
    html = html.replace(/(✅|Pros?|Advantages?):/gi, '<span class="can-pro">✅ $1</span>');
    html = html.replace(/(❌|Cons?|Disadvantages?):/gi, '<span class="can-con">❌ $1</span>');
    return '<div class="can-cmp-w">' + html + '</div>';
  }
});

// ── Glossary Canvas ──
__registerCanvas({
  name: 'glossary',
  detect: function(a) {
    if (!a.hasGlossary) return null;
    return { score: 70 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var items = [];
    c.split('\n').forEach(function(l) {
      var m = l.match(/^\*\*([^*]+)\*\*\s*[:—\-]\s*(.+)/);
      if (m) items.push({ term: m[1], def: m[2] });
    });
    // Show rest of content + glossary
    var nonGlossary = c.split('\n').filter(function(l) { return !l.match(/^\*\*[^*]+\*\*\s*[:—\-]/); }).join('\n');
    var rest = nonGlossary.trim() ? parseMarkdown(nonGlossary) : '';
    var glHTML = items.length ? '<div class="can-gloss"><div class="can-gloss-h">📖 ' + items.length + ' terms</div>'
      + items.map(function(i) {
        return '<div class="can-gloss-r"><span class="can-gloss-t">' + escapeHtml(i.term) + '</span><span class="can-gloss-d">' + parseMarkdown(i.def) + '</span></div>';
      }).join('') + '</div>' : '';
    return '<div class="can-gloss-w">' + rest + glHTML + '</div>';
  }
});

// ── Timeline Canvas ──
__registerCanvas({
  name: 'timeline',
  detect: function(a) {
    if (!a.hasTimeline) return null;
    return { score: 70 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<ul>/g, '<ul class="can-tl">');
    html = html.replace(/<li>/g, '<li class="can-tl-i">');
    return '<div class="can-tl-w">' + html + '</div>';
  }
});

// ── Task List Canvas ──
__registerCanvas({
  name: 'tasks',
  detect: function(a) {
    if (!a.hasTaskList) return null;
    return { score: 60 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<input[^>]*checked[^>]*>/g, '<span class="can-chk done">✅</span>');
    html = html.replace(/<input[^>]*>/g, '<span class="can-chk">⬜</span>');
    html = html.replace(/<li>/g, '<li class="can-task-i">');
    return '<div class="can-tasks">' + html + '</div>';
  }
});

// ── Architecture Canvas ──
__registerCanvas({
  name: 'architecture',
  detect: function(a) {
    if (!a.hasArchitecture) return null;
    return { score: 80 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<pre><code class="language-(\w+)">/g, function(m, l) {
      return '<div class="can-arc-c"><div class="can-arc-l">⚙ ' + l + '</div><pre><code class="language-' + l + '">';
    });
    html = html.replace(/<\/code><\/pre>/g, '</code></pre></div>');
    return '<div class="can-arc">' + html + '</div>';
  }
});

// ── FAQ Canvas ──
__registerCanvas({
  name: 'faq',
  detect: function(a) {
    if (!a.hasFAQ) return null;
    return { score: 65 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    // Style Q/A pairs
    html = html.replace(/^<p><strong>(Q|Question)[^:]*:<\/strong>/gm, '<p class="can-faq-q">❓ $1:</p>');
    html = html.replace(/^<p><strong>(A|Answer)[^:]*:<\/strong>/gm, '<p class="can-faq-a">💡 $1:</p>');
    return '<div class="can-faq-w">' + html + '</div>';
  }
});

// ── Changelog Canvas ──
__registerCanvas({
  name: 'changelog',
  detect: function(a) {
    if (!a.hasChangelog) return null;
    return { score: 75 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<h2>v?(\d+\.\d+)/g, '<h2 class="can-cl-h">🚀 v$1');
    html = html.replace(/<h3>v?(\d+\.\d+)/g, '<h3 class="can-cl-h">🔹 v$1');
    html = html.replace(/<li>(added|new|feat):/gi, '<li class="can-cl-add">✨ $1:');
    html = html.replace(/<li>(fixed|bugfix|fix):/gi, '<li class="can-cl-fix">🐛 $1:');
    html = html.replace(/<li>(changed|updated|improve):/gi, '<li class="can-cl-chg">🔄 $1:');
    html = html.replace(/<li>(removed|deprecated):/gi, '<li class="can-cl-rm">🗑️ $1:');
    return '<div class="can-cl-w">' + html + '</div>';
  }
});

// ── Recipe Canvas ──
__registerCanvas({
  name: 'recipe',
  detect: function(a) {
    if (!a.hasRecipe) return null;
    return { score: 75 * __lenFactor(a.wordCount), data: {} };
  },
  render: function(d, c) {
    var html = parseMarkdown(c);
    html = html.replace(/<h2>/g, '<h2 class="can-rec-h">👨‍🍳 ');
    html = html.replace(/<li>(ingredients?):/gi, '<li class="can-rec-ing">🛒 $1:');
    html = html.replace(/<li>(steps?|instructions?):/gi, '<li class="can-rec-st">📋 $1:');
    return '<div class="can-rec-w">' + html + '</div>';
  }
});


// ── Chart Canvas: bar, pie, line charts from numeric data ──
__registerCanvas({
  name: 'chart',
  detect: function(a) {
    var hasDataTable = a.tableCount > 0 && /\b\d+(\.\d+)?%?\b/g.test(a.raw || '');
    var hasChartWords = /(chart|graph|plot|distribution|trend|data|statistics?|percentage|compare|breakdown|overview|summary of|metrics)/i.test(a.raw || '');
    var hasNumericList = a.wordCount > 30 && (a.raw || '').split('\n').filter(function(l) {
      return /^[\s]*[-*]\s+.+\d+/.test(l) || /^[\s]*\|.*\d+.*\|/.test(l);
    }).length >= 2;
    if (hasDataTable || hasChartWords || hasNumericList) {
      var score = 65 + (hasDataTable ? 15 : 0) + (hasChartWords ? 10 : 0);
      var data = __parseChartData(a.raw || '');
      return { score: Math.min(score, 100) * __lenFactor(a.wordCount), data: data };
    }
    return null;
  },
  render: function(d, c) {
    if (!d || !d.labels || !d.labels.length) {
      return __smartFallback(c, { headings: d?.headings, sections: d?.sections });
    }
    var chartType = d.type || 'bar';
    var labels = d.labels || [];
    var datasets = d.datasets || [{ data: d.values || [], label: 'Values' }];
    var maxVal = 0;
    for (var ds = 0; ds < datasets.length; ds++) {
      for (var v = 0; v < datasets[ds].data.length; v++) {
        if (datasets[ds].data[v] > maxVal) maxVal = datasets[ds].data[v];
      }
    }
    if (maxVal === 0) maxVal = 100;
    var colors = ['#3182f6','#34d399','#fbbf24','#f87171','#a78bfa','#f472b6','#2dd4bf','#fb923c'];
    var svgW = 600, svgH = 320, padL = 60, padR = 20, padT = 30, padB = 50;
    var chartW = svgW - padL - padR, chartH = svgH - padT - padB;
    var html = '<div class="can-chart-w">';
    html += '<div class="can-chart-ctrls">';
    var types = ['bar', 'pie', 'line'];
    for (var t = 0; t < types.length; t++) {
      html += '<button class="can-chart-btn' + (types[t] === chartType ? ' active' : '') + '" data-click="switch-chart" data-chart="' + types[t] + '">' + types[t].charAt(0).toUpperCase() + types[t].slice(1) + '</button>';
    }
    html += '</div><div class="can-chart-svg-wrap">';
    if (chartType === 'pie') {
      var total = 0;
      for (var v = 0; v < datasets[0].data.length; v++) total += datasets[0].data[v];
      if (total === 0) total = 1;
      var cx = 200, cy = 160, r = 140;
      var startAngle = -Math.PI / 2;
      html += '<svg viewBox="0 0 400 320" class="can-chart-svg">';
      for (var v = 0; v < datasets[0].data.length; v++) {
        var val = datasets[0].data[v];
        var angle = (val / total) * 2 * Math.PI;
        var endAngle = startAngle + angle;
        var x1 = cx + r * Math.cos(startAngle);
        var y1 = cy + r * Math.sin(startAngle);
        var x2 = cx + r * Math.cos(endAngle);
        var y2 = cy + r * Math.sin(endAngle);
        var large = angle > Math.PI ? 1 : 0;
        html += '<path d="M' + cx + ',' + cy + ' L' + x1 + ',' + y1 + ' A' + r + ',' + r + ' 0 ' + large + ',1 ' + x2 + ',' + y2 + ' Z" fill="' + colors[v % colors.length] + '" opacity="0.85" class="can-chart-seg"><title>' + escapeHtml(labels[v] || '') + ': ' + val + ' (' + Math.round(val / total * 100) + '%)</title></path>';
        startAngle = endAngle;
      }
      html += '</svg><div class="can-chart-legend">';
      for (var v = 0; v < datasets[0].data.length; v++) {
        var pct = Math.round(datasets[0].data[v] / total * 100);
        html += '<div class="can-chart-legend-i"><span class="can-chart-legend-dot" style="background:' + colors[v % colors.length] + '"></span>' + escapeHtml(labels[v] || '') + ' <strong>' + datasets[0].data[v] + '</strong> <span class="can-chart-legend-pct">(' + pct + '%)</span></div>';
      }
      html += '</div>';
    } else if (chartType === 'line') {
      html += '<svg viewBox="0 0 ' + svgW + ' ' + svgH + '" class="can-chart-svg">';
      var gridLines = 5;
      for (var g = 0; g <= gridLines; g++) {
        var y = padT + (chartH / gridLines) * g;
        var val = maxVal - (maxVal / gridLines) * g;
        html += '<line x1="' + padL + '" y1="' + y + '" x2="' + (svgW - padR) + '" y2="' + y + '" stroke="var(--border-light)" stroke-width="1" stroke-dasharray="4,4"/>';
        html += '<text x="' + (padL - 8) + '" y="' + (y + 4) + '" text-anchor="end" class="can-chart-axis-label">' + (val >= 1000 ? (val / 1000).toFixed(1) + 'k' : Math.round(val)) + '</text>';
      }
      for (var ds = 0; ds < datasets.length; ds++) {
        var dset = datasets[ds];
        var points = [];
        for (var v = 0; v < dset.data.length; v++) {
          var x = padL + (chartW / (Math.max(dset.data.length - 1, 1))) * v;
          var yVal = dset.data[v];
          var y = padT + chartH - (yVal / maxVal) * chartH;
          points.push(x + ',' + y);
          html += '<circle cx="' + x + '" cy="' + y + '" r="4" fill="' + colors[ds % colors.length] + '" class="can-chart-point"><title>' + escapeHtml(labels[v] || '') + ': ' + yVal + '</title></circle>';
        }
        html += '<polyline points="' + points.join(' ') + '" fill="none" stroke="' + colors[ds % colors.length] + '" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" opacity="0.8"/>';
      }
      for (var v = 0; v < labels.length; v++) {
        var x = padL + (chartW / (Math.max(labels.length - 1, 1))) * v;
        html += '<text x="' + x + '" y="' + (svgH - 12) + '" text-anchor="' + (v === 0 ? 'start' : v === labels.length - 1 ? 'end' : 'middle') + '" class="can-chart-axis-label">' + escapeHtml((labels[v] || '').slice(0, 12)) + '</text>';
      }
      html += '</svg>';
    } else {
      html += '<svg viewBox="0 0 ' + svgW + ' ' + svgH + '" class="can-chart-svg">';
      var gridLines = 5;
      for (var g = 0; g <= gridLines; g++) {
        var y = padT + (chartH / gridLines) * g;
        var val = maxVal - (maxVal / gridLines) * g;
        html += '<line x1="' + padL + '" y1="' + y + '" x2="' + (svgW - padR) + '" y2="' + y + '" stroke="var(--border-light)" stroke-width="1" stroke-dasharray="4,4"/>';
        html += '<text x="' + (padL - 8) + '" y="' + (y + 4) + '" text-anchor="end" class="can-chart-axis-label">' + (val >= 1000 ? (val / 1000).toFixed(1) + 'k' : Math.round(val)) + '</text>';
      }
      var barCount = labels.length;
      var dsCount = datasets.length;
      var groupW = chartW / barCount;
      var barW = Math.min((groupW * 0.7) / dsCount, 40);
      var gap = dsCount > 1 ? (groupW - barW * dsCount) / 2 : (groupW - barW) / 2;
      for (var v = 0; v < barCount; v++) {
        for (var ds = 0; ds < dsCount; ds++) {
          var dset = datasets[ds];
          var yVal = dset.data[v] || 0;
          var x = padL + groupW * v + gap + barW * ds;
          var barH = (yVal / maxVal) * chartH;
          var y = padT + chartH - barH;
          html += '<rect x="' + x + '" y="' + y + '" width="' + barW + '" height="' + Math.max(barH, 1) + '" rx="2" fill="' + colors[ds % colors.length] + '" opacity="0.85" class="can-chart-bar"><title>' + escapeHtml(labels[v] || '') + ': ' + yVal + '</title></rect>';
        }
        var xLabel = padL + groupW * v + groupW / 2;
        html += '<text x="' + xLabel + '" y="' + (svgH - 12) + '" text-anchor="middle" class="can-chart-axis-label">' + escapeHtml((labels[v] || '').slice(0, 12)) + '</text>';
      }
      html += '</svg>';
      if (dsCount > 1) {
        html += '<div class="can-chart-legend can-chart-legend-h">';
        for (var ds = 0; ds < dsCount; ds++) {
          html += '<div class="can-chart-legend-i"><span class="can-chart-legend-dot" style="background:' + colors[ds % colors.length] + '"></span>' + escapeHtml(datasets[ds].label || '') + '</div>';
        }
        html += '</div>';
      }
    }
    html += '</div></div>';
    return html;
  }
});

// ── Chart Data Parser: extracts labels & values from content ──
function __parseChartData(content) {
  var result = { labels: [], values: [], datasets: [], type: 'bar' };
  if (!content) return result;
  var lines = content.split('\n');
  if (/pie\s*chart|distribution|proportion|percentage|share|breakdown\b/i.test(content)) {
    result.type = 'pie';
  } else if (/line\s*chart|trend|over\s*time|growth|timeline|progress/i.test(content)) {
    result.type = 'line';
  }
  var inTable = false, headers = [], rows = [];
  for (var i = 0; i < lines.length; i++) {
    var l = lines[i].trim();
    if (l.startsWith('|') && l.endsWith('|')) {
      if (!inTable) { inTable = true; headers = []; rows = []; }
      var cells = l.split('|').filter(function(c) { return c.trim(); });
      if (cells.length && /^[-:. ]+$/.test(cells[0].trim())) continue;
      if (headers.length === 0) {
        headers = cells.map(function(c) { return c.trim(); });
      } else {
        rows.push(cells.map(function(c) { return c.trim(); }));
      }
    } else {
      if (inTable) break;
    }
  }
  if (headers.length >= 2 && rows.length >= 1) {
    result.labels = [];
    result.datasets = [];
    var firstLabels = [];
    for (var r = 0; r < rows.length; r++) {
      firstLabels.push(rows[r][0] || '');
    }
    result.labels = firstLabels;
    for (var c = 1; c < headers.length; c++) {
      var vals = [];
      for (var r = 0; r < rows.length; r++) {
        var num = parseFloat(rows[r][c]?.replace(/[$,%\s]/g, '') || '0');
        vals.push(isNaN(num) ? 0 : num);
      }
      if (vals.some(function(v) { return v !== 0; })) {
        result.datasets.push({ label: headers[c], data: vals });
      }
    }
    result.values = result.datasets[0] ? result.datasets[0].data : [];
    return result;
  }
  var listLabels = [], listVals = [];
  for (var i = 0; i < lines.length; i++) {
    var m = lines[i].match(/^\s*[-*]\s+(.+?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*(?:%|items|users|count|total)?\s*$/);
    if (m) {
      listLabels.push(m[1].trim());
      listVals.push(parseFloat(m[2]));
    }
  }
  if (listLabels.length >= 2) {
    result.labels = listLabels;
    result.values = listVals;
    result.datasets = [{ label: 'Values', data: listVals }];
  }
  return result;
}

// ── Chart click handler: switch chart types interactively ──
CLICK_HANDLERS['switch-chart'] = function(el) {
  var chartType = el.getAttribute('data-chart');
  if (!chartType) return;
  var wrapper = el.closest('.can-chart-w');
  if (!wrapper) return;
  var canvasEl = wrapper.closest('[data-raw]') || wrapper.closest('.response-content');
  if (!canvasEl) return;
  var raw = canvasEl.dataset?.raw || canvasEl.textContent || '';
  if (!raw) return;
  var data = __parseChartData(raw);
  data.type = chartType;
  var chartCanvas = null;
  for (var i = 0; i < __canvasTypes.length; i++) {
    if (__canvasTypes[i].name === 'chart') { chartCanvas = __canvasTypes[i]; break; }
  }
  if (chartCanvas) {
    var result = chartCanvas.detect({ tableCount: raw.indexOf('|') !== -1 ? 1 : 0, wordCount: raw.split(' ').length, raw: raw }, raw);
    if (result) {
      wrapper.outerHTML = chartCanvas.render(result.data, raw);
    }
  }
};


// ── Mind Map Canvas: hierarchical tree diagrams ──
__registerCanvas({
  name: 'mindmap',
  priority: 30,
  detect: function(a) {
    var raw = a.raw || '';
    var hasDepth = /[\t ]{2,}[-*]|^[\t ]*[-*].*\n[\t ]+[-*]/.test(raw);
    var hasTreeWords = /(mind.?map|tree|hierarch|branch|node|parent|child|sub.?topic|root|leaf|diagram|flow)/i.test(raw);
    var hasNestedLists = (raw.match(/^[\t ]*[-*].*$/gm) || []).length >= 4;
    var hasOutline = /^[\t ]*\d+\./.test(raw) && /^[\t ]+\d+\./.test(raw);
    if (hasDepth || hasTreeWords || hasNestedLists || hasOutline) {
      var score = 50 + (hasDepth ? 20 : 0) + (hasTreeWords ? 15 : 0) + (hasNestedLists ? 10 : 0);
      score = Math.min(score, 95);
      var data = __parseMindMap(a.raw || '');
      return { score: score, data: data };
    }
    return null;
  },
  render: function(d, content) {
    if (!d || !d.nodes || !d.nodes.length) return parseMarkdown(content);
    var nodes = d.nodes;
    var colors = ['#6366f1','#8b5cf6','#ec4899','#f43f5e','#f97316','#eab308','#22c55e','#14b8a6','#06b6d4','#3b82f6'];
    var colorIdx = 0;
    function renderBranch(node, depth) {
      depth = depth || 0;
      var padLeft = 20 + depth * 28;
      var color = colors[(depth) % colors.length];
      var dotSize = Math.max(8, 16 - depth * 1.5);
      var label = escapeHtml(node.label || node.name || '');
      var childrenHtml = '';
      if (node.children && node.children.length) {
        childrenHtml = '<div class="can-mm-children">' + node.children.map(function(c) { return renderBranch(c, depth + 1); }).join('') + '</div>';
      }
      return '<div class="can-mm-node" style="padding-left:' + padLeft + 'px">'
        + '<div class="can-mm-row">'
        + '<span class="can-mm-dot" style="background:' + color + ';width:' + dotSize + 'px;height:' + dotSize + 'px"></span>'
        + '<span class="can-mm-label">' + label + '</span>'
        + (node.desc ? '<span class="can-mm-desc">' + escapeHtml(node.desc) + '</span>' : '')
        + (node.value ? '<span class="can-mm-value">' + escapeHtml(String(node.value)) + '</span>' : '')
        + '</div>'
        + childrenHtml + '</div>';
    }
    var rootNodes = nodes.filter(function(n) { return !n.parent; });
    if (!rootNodes.length) rootNodes = [nodes[0]];
    var html = '<div class="can-mm-w">';
    for (var i = 0; i < rootNodes.length; i++) {
      html += '<div class="can-mm-tree">' + renderBranch(rootNodes[i], 0) + '</div>';
    }
    html += '</div>';
    return html;
  }
});

function __parseMindMap(raw) {
  if (!raw) return { nodes: [] };
  var lines = raw.split('\n');
  var root = { label: 'Root', children: [] };
  var stack = [{ node: root, indent: -1 }];
  // Try to detect first heading as root label
  var firstHeading = raw.match(/^#{1,3}\s+(.+)/m);
  if (firstHeading) {
    root.label = firstHeading[1].trim();
  }
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    var trimmed = line.trim();
    if (!trimmed || /^[-]{3,}$/.test(trimmed) || /^[|]/.test(trimmed)) continue;
    // Match list items: - item, * item, 1. item
    var match = trimmed.match(/^[-*]\s+(.+)/) || trimmed.match(/^\d+\.\s+(.+)/);
    if (!match) continue;
    var text = match[1].trim();
    // Compute indent level based on leading whitespace
    var indent = line.length - line.replace(/^\s+/, '').length;
    if (indent === 0 && (trimmed.startsWith('-') || trimmed.startsWith('*'))) {
      indent = 2;
    }
    // Parse optional description with :: or — separator
    var label = text;
    var desc = '';
    var sep = text.match(/\s*(::|—|:|―)\s*/);
    if (sep) {
      label = text.slice(0, sep.index).trim();
      desc = text.slice(sep.index + sep[0].length).trim();
    }
    // Pop stack to correct level
    while (stack.length > 1 && indent <= stack[stack.length - 1].indent) {
      stack.pop();
    }
    var parent = stack[stack.length - 1].node;
    var child = { label: label, children: [], desc: desc };
    if (!parent.children) parent.children = [];
    parent.children.push(child);
    stack.push({ node: child, indent: indent });
  }
  // Return nested tree: root's children are the top-level branches
  return { nodes: root.children || [], rootLabel: root.label };
}


// ── Smart Fallback: enhances ALL content ──
function __smartFallback(content, data) {
  var html = parseMarkdown(content);
  // Numbered headings
  var idx = 0;
  html = html.replace(/<h([23])>/g, function(m, l) {
    idx++;
    return '<h' + l + ' id="can-fb-' + idx + '" class="can-fb-h">' + idx + '. ';
  });
  // Enhance tables
  html = html.replace(/<table>/g, '<table class="can-tbl">');
  // Enhance single code blocks
  html = html.replace(/<pre><code>/g, '<div class="can-cd can-fb"><pre><code>');
  html = html.replace(/<\/code><\/pre>/g, '</code></pre></div>');
  // Checkboxes
  html = html.replace(/\[ \]/g, '<span class="can-chk">⬜</span>');
  html = html.replace(/\[x\]/gi, '<span class="can-chk done">✅</span>');
  return '<div class="can-fb-w">' + html + '</div>';
}

// ── Main integration ──
function _tryCanvasRender() {
  var el = S._activeAITextEl;
  if (!el) return;
  // Use raw markdown from dataset (preserves formatting), fallback to text
  var content = el.dataset?.raw || el.textContent || el.innerText || '';
  if (!content.trim() || content.trim().length < 20) return;

  var canvas = canvasDispatcher(content);
  if (canvas && canvas.render) {
    el.innerHTML = canvas.render(canvas.data, content);
    el.classList.add('can-active');
    // Save canvas metadata to the last message for session persistence
    var msgs = S.messages;
    if (msgs && msgs.length) {
      var last = msgs[msgs.length - 1];
      if (last && last.role === 'assistant') {
        last.canvas = { type: canvas.name, data: canvas.data };
      }
    }
    // Add canvas badge
    var badge = document.createElement('div');
    badge.className = 'can-badge';
    var labels = { document: '📑 Document', table: '📊 Table', code: '💻 Code', travel: '✈️ Travel',
      comparison: '⚖️ Comparison', glossary: '📖 Glossary', timeline: '📅 Timeline',
      tasks: '✅ Tasks', architecture: '🏗️ Architecture', faq: '❓ FAQ', changelog: '📋 Changelog', recipe: '👨‍🍳 Recipe', chart: '📈 Chart', mindmap: '🧠 Mind Map' };
    badge.textContent = labels[canvas.name] || '🎨 Canvas';
    el.parentElement?.insertBefore(badge, el);
  }
}

// ── Dynamic Canvas CSS ──
var _canCSS = document.createElement('style');
_canCSS.textContent = ''
  // Document
  + '.can-doc{display:flex;gap:20px;position:relative}'
  + '.can-toc{flex:0 0 180px;position:sticky;top:8px;max-height:calc(100vh-250px);overflow-y:auto;padding:8px 4px;border-right:1px solid var(--border-light)}'
  + '.can-toc-hdr{font-weight:700;color:var(--text-primary);margin-bottom:10px;font-size:11px;letter-spacing:.5px;padding-bottom:6px;border-bottom:1px solid var(--border-light)}'
  + '.can-toc-i{display:block;padding:4px 6px;color:var(--text-muted);text-decoration:none;border-radius:4px;transition:all .12s;font-size:12px;line-height:1.4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}'
  + '.can-toc-i:hover{color:var(--accent);background:var(--fill-hover)}'
  + '.can-body{flex:1;min-width:0}'
  + '.can-body h2{margin-top:4px}'
  // Tables
  + '.can-tbl{width:100%;border-collapse:collapse;margin:16px 0;font-size:13px}'
  + '.can-tbl-h,.can-tbl th{background:var(--accent-dim);color:var(--accent);padding:10px 14px;text-align:left;font-weight:600;border:1px solid var(--border-main);font-size:12px}'
  + '.can-tbl td{padding:8px 14px;border:1px solid var(--border-main);color:var(--text-secondary)}'
  + '.can-tbl tr:nth-child(even){background:var(--bg-input)}'
  + '.can-tbl tr:hover{background:var(--fill-hover)}'
  + '.can-cmp th:first-child{background:var(--success-dim);color:var(--success)}'
  + '.can-cmp th:last-child{background:var(--error-dim);color:var(--error)}'
  // Code
  + '.can-cd{position:relative;margin:16px 0;border-radius:8px;overflow:hidden;border:1px solid var(--border-main)}'
  + '.can-cd-h{display:flex;justify-content:space-between;padding:4px 12px;background:var(--bg-input);border-bottom:1px solid var(--border-light);font-size:10px}'
  + '.can-cd-l{color:var(--accent);font-weight:600;text-transform:uppercase}'
  + '.can-cd-n{color:var(--text-muted)}'
  + '.can-cd pre{margin:0;padding:12px;background:var(--bg-canvas)}'
  // Travel
  + '.can-day{background:var(--accent-dim);color:var(--accent);padding:4px 14px;border-radius:var(--radius-full);font-weight:600;font-size:12px;margin:8px 0;display:inline-block}'
  + '.can-trv-h{color:var(--text-primary);font-size:14px;margin:8px 0 4px}'
  // Comparison
  + '.can-cmp-w{padding:4px 0}'
  + '.can-pro{color:var(--success);font-weight:600}'
  + '.can-con{color:var(--error);font-weight:600}'
  // Glossary
  + '.can-gloss{border:1px solid var(--border-main);border-radius:10px;overflow:hidden;margin:12px 0}'
  + '.can-gloss-h{padding:8px 14px;background:var(--bg-input);font-weight:600;font-size:12px;color:var(--text-primary);border-bottom:1px solid var(--border-light)}'
  + '.can-gloss-r{display:flex;padding:8px 14px;border-bottom:1px solid var(--border-light);gap:12px;font-size:13px}'
  + '.can-gloss-r:last-child{border-bottom:none}'
  + '.can-gloss-t{flex:0 0 120px;font-weight:600;color:var(--accent)}'
  + '.can-gloss-d{flex:1;color:var(--text-secondary)}'
  + '.can-gloss-d p{margin:0}'
  // Timeline
  + '.can-tl-w{padding:4px 0 4px 16px;border-left:2px solid var(--accent-dim);margin:8px 0}'
  + '.can-tl{padding:0;list-style:none}'
  + '.can-tl-i{padding:6px 0 6px 12px;position:relative;font-size:13px;color:var(--text-secondary)}'
  + '.can-tl-i::before{content:"";position:absolute;left:-21px;top:12px;width:8px;height:8px;border-radius:50%;background:var(--accent)}'
  // Tasks
  + '.can-tasks{padding:4px 0}'
  + '.can-task-i{list-style:none;padding:4px 0;font-size:13px;color:var(--text-secondary)}'
  + '.can-chk{margin-right:6px;font-size:14px}'
  // Architecture
  + '.can-arc-c{margin:12px 0;border:1px solid var(--border-main);border-radius:8px;overflow:hidden}'
  + '.can-arc-l{padding:4px 12px;background:var(--bg-input);font-size:11px;color:var(--text-secondary);border-bottom:1px solid var(--border-light)}'
  // FAQ
  + '.can-faq-q{background:var(--bg-input);padding:8px 12px;border-radius:6px;margin:8px 0 4px;font-weight:500;color:var(--text-primary)}'
  + '.can-faq-a{padding:4px 12px 8px;color:var(--text-secondary);border-left:2px solid var(--accent);margin:0 0 12px}'
  // Changelog
  + '.can-cl-h{color:var(--accent)}'
  + '.can-cl-add{color:var(--success)}'
  + '.can-cl-fix{color:var(--warning)}'
  + '.can-cl-chg{color:var(--text-primary)}'
  + '.can-cl-rm{color:var(--error)}'
  // Recipe
  + '.can-rec-h{color:var(--accent)}'
  + '.can-rec-ing{list-style:none;font-weight:500;color:var(--text-secondary)}'
  + '.can-rec-st{list-style:none;font-weight:500;color:var(--text-secondary)}'
  // Chart
  + '.can-chart-w{background:var(--bg-canvas);border-radius:10px;border:1px solid var(--border-main);padding:16px;margin:8px 0}'
  + '.can-chart-ctrls{display:flex;gap:4px;margin-bottom:12px;flex-wrap:wrap}'
  + '.can-chart-btn{padding:4px 14px;border-radius:999px;border:1px solid var(--border-main);background:transparent;color:var(--text-tertiary);font-size:11px;font-weight:500;cursor:pointer;transition:all .12s}'
  + '.can-chart-btn:hover{background:var(--fill-hover);color:var(--text-primary)}'
  + '.can-chart-btn.active{background:var(--accent-dim);color:var(--accent);border-color:var(--border-accent)}'
  + '.can-chart-svg-wrap{overflow-x:auto}'
  + '.can-chart-svg{width:100%;height:auto;min-height:280px;display:block}'
  + '.can-chart-bar{cursor:pointer;transition:opacity .15s}'
  + '.can-chart-bar:hover,.can-chart-seg:hover{opacity:1!important}'
  + '.can-chart-point{cursor:pointer;transition:r .15s}'
  + '.can-chart-point:hover{r:6}'
  + '.can-chart-seg{cursor:pointer;transition:opacity .15s;stroke:#fff;stroke-width:1}'
  + '.can-chart-axis-label{font-size:11px;fill:var(--text-muted);font-family:var(--font-sans)}'
  + '.can-chart-legend{display:flex;flex-direction:column;gap:4px;margin-top:10px;padding:8px 12px;background:var(--bg-input);border-radius:8px;border:1px solid var(--border-light)}'
  + '.can-chart-legend-h{flex-direction:row;flex-wrap:wrap;gap:8px}'
  + '.can-chart-legend-i{font-size:12px;color:var(--text-secondary);display:flex;align-items:center;gap:6px}'
  + '.can-chart-legend-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;display:inline-block}'
  + '.can-chart-legend-pct{color:var(--text-muted);font-size:11px}'

  // Fallback
  + '.can-fb-w{padding:2px 0}'
  + '.can-fb-h{cursor:pointer;color:var(--text-primary)}'
  + '.can-fb-h:hover{color:var(--accent)}'
  // Active state
  + '.can-active .ai-footer{margin-top:12px;padding-top:8px;border-top:1px solid var(--border-light)}'
  + '.can-badge{display:inline-block;padding:2px 10px;font-size:10px;border-radius:999px;background:var(--accent-dim);color:var(--accent);margin:4px 0 0;font-weight:600;letter-spacing:.3px}'
  // Responsive
  + '@media(max-width:820px){.can-doc{flex-direction:column}.can-toc{flex:none;position:static;max-height:none;border-right:none;border-bottom:1px solid var(--border-light);margin-bottom:8px;display:flex;flex-wrap:wrap;gap:4px;padding:4px 0}.can-toc-hdr{width:100%}.can-toc-i{display:inline-block;padding:2px 8px;border:1px solid var(--border-light);border-radius:999px;font-size:11px}}'
  + '@media(max-width:820px){.can-gloss-r{flex-direction:column;gap:4px}.can-gloss-t{flex:none}}';
document.head.appendChild(_canCSS);

// ── Hook into streaming completion ──
var _origFinishThinking = window.finishThinking;
window.finishThinking = function() {
  if (_origFinishThinking) _origFinishThinking();
  _tryCanvasRender();
};
