/* WIDDX Nexus — Settings View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast, S) */

async function showModelSetupView(area) {
  setActivity('Loading', 'settings');

  var [settingsR, proxyR, permsR, tokenR, acR, ggufR, apikeysR, mcpR, gwR] = await Promise.all([
    fetch('/api/settings'),
    fetch('/api/proxy'),
    fetch('/api/permissions'),
    fetch('/api/token-budget'),
    fetch('/api/autocommit'),
    fetch('/api/gguf'),
    fetch('/api/apikeys'),
    fetch('/api/mcp'),
    fetch('/api/dashboard/gateway'),
  ]);
  var settings, proxy, perms, tokens, ac, gguf, apikeys, mcp, gateway;
  try { settings = await settingsR.json(); } catch(e) { settings = {}; }
  try { proxy = await proxyR.json(); } catch(e) { proxy = {enabled:false, http:'', https:''}; }
  try { perms = await permsR.json(); } catch(e) { perms = {level:'normal', levels:['permissive','normal','strict','silent']}; }
  try { tokens = await tokenR.json(); } catch(e) { tokens = {used:0, limit:0, remaining:0, percentage:0}; }
  try { ac = await acR.json(); } catch(e) { ac = {enabled:false, interval:0, last_commit:null}; }
  try { gguf = await ggufR.json(); } catch(e) { gguf = []; }
  try { apikeys = await apikeysR.json(); } catch(e) { apikeys = {}; }
  try { mcp = await mcpR.json(); } catch(e) { mcp = []; }
  try { gateway = await gwR.json(); } catch(e) { gateway = {channels: []}; }

  var prov = settings.provider || {};
  var providers = settings.available_providers || [];
  var provOpts = providers.map(function(p) {
    return '<option value="' + escapeHtml(p.id) + '"' + (p.id === (prov.name || 'opencode-zen') ? ' selected' : '') + '>' + escapeHtml(p.name) + '</option>';
  }).join('');

  var tabGeneral = ''
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-microchip"></i> Active Provider</div>'
    +   '<select id="ms-provider" class="settings-select" onchange="onMSProviderChange(this.value)">' + provOpts + '</select></div>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-thermometer-half"></i> Temperature: <span id="ms-temp-value" class="text-semibold" style="color:var(--accent)">' + (settings.temperature || 0.7) + '</span></div>'
    +   '<input type="range" min="0" max="2" step="0.1" value="' + (settings.temperature || 0.7) + '" class="w-full" style="accent-color:var(--accent)" oninput="document.getElementById(\'ms-temp-value\').textContent=this.value">'
    + '</div>'
    + ''
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-arrow-right-arrow-left"></i> Max Turns <span class="text-muted" style="font-weight:400">(conversation limit)</span></div>'
    +   '<input id="ms-max-turns" type="number" min="1" max="100" class="settings-input" value="' + (settings.max_turns || 10) + '">'
    + '</div>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-palette"></i> Theme</div>'
    +   '<select id="ms-theme" class="settings-select">'
    +     '<option value="dark"' + ((settings.cli_theme || 'dark') === 'dark' ? ' selected' : '') + '>🌙 Dark</option>'
    +     '<option value="light"' + (settings.cli_theme === 'light' ? ' selected' : '') + '>☀️ Light</option>'
    +   '</select>'
    + '</div>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-language"></i> Language</div>'
    +   '<select id="ms-lang" class="settings-select" onchange="Lang.setLang(this.value)">'
    +     '<option value="en"' + ((typeof Lang !== 'undefined' && Lang.currentLang === 'en') ? ' selected' : '') + '>🇬🇧 English</option>'
    +     '<option value="ar"' + ((typeof Lang !== 'undefined' && Lang.currentLang === 'ar') ? ' selected' : '') + '>🇸🇦 العربية</option>'
    +   '</select>'
    + '</div>'
    + '<div class="settings-card" style="opacity:0.6"><div class="settings-card-label"><i class="fa-solid fa-file-code"></i> Config File</div>'
    +   '<code class="text-11 text-muted">' + escapeHtml(settings.config_path || '—') + '</code>'
    + '</div>'
    + '<div class="flex-ac gap-10"><button id="save-general-btn" data-click="save-general-settings" class="btn-primary"><i class="fa-solid fa-floppy-disk"></i> Save</button><span id="ms-status" class="text-sm text-muted"></span></div>';

  var modelOpts = {};
  providers.forEach(function(p) {
    modelOpts[p.id] = (p.models || []).map(function(m) {
      return '<option value="' + escapeHtml(m) + '"' + ((p.id === (prov.name || 'opencode-zen') && m === prov.model) ? ' selected' : '') + '>' + escapeHtml(m) + '</option>';
    }).join('');
  });
  var tabProviders = providers.map(function(p) {
    var pid = p.id;
    var isActive = pid === (prov.name || 'opencode-zen');
    var needsKey = pid === 'deepseek' || pid === 'openai';
    var defaultUrl = p.default_base || '';
    var currentUrl = isActive ? (prov.base_url || defaultUrl) : defaultUrl;
    var badge = pid === 'opencode-zen' ? '🆓 FREE' : pid === 'deepseek' ? '🔑 API KEY' : pid === 'openai' ? '🔑 API KEY' : pid === 'ollama' ? '💻 LOCAL' : '📦 GGUF';

    return '<div class="settings-card" style="border-left:3px solid ' + (isActive ? 'var(--accent)' : 'transparent') + '">'
      + '<div class="flex-ac-sb mb-8">'
      + '<strong>' + escapeHtml(p.name) + '</strong>'
      + '<span style="font-size:10px;font-weight:600;padding:2px 10px;border-radius:999px;background:' + (isActive ? 'var(--accent-dim)' : 'var(--fill-active)') + ';color:' + (isActive ? 'var(--accent)' : 'var(--text-tertiary)') + '">' + badge + '</span>'
      + '</div>'
      + '<div class="settings-card-label text-11">Model</div>'
      + '<select id="prov-model-' + pid + '" class="settings-select">' + modelOpts[pid] + '</select>'
      + '<div class="settings-card-label text-11" style="margin-top:6px">Base URL</div>'
      + '<input id="prov-url-' + pid + '" class="settings-input" value="' + escapeHtml(currentUrl) + '" placeholder="' + escapeHtml(defaultUrl) + '">'
      + (needsKey ? '<div class="settings-card-label text-11" style="margin-top:6px">API Key</div>'
        + '<input id="prov-key-' + pid + '" type="password" class="settings-input" placeholder="' + (isActive && prov.has_key ? 'Key exists' : 'Enter API key') + '">' : '')
      + (pid === 'deepseek' ? '<div class="flex-ac gap-8 mt-8">'
        + '<input type="checkbox" id="thinking-toggle" ' + (settings.thinking !== false ? 'checked' : '') + '>'
        + '<span class="text-sm text-secondary">🧠 Deep reasoning (slower, more accurate)</span>'
        + '</div>' : '')
      + '</div>';
  }).join('');

  tabProviders += '<div class="flex-ac gap-10" style="margin-top:4px;flex-wrap:wrap">'
    + '<button id="save-providers-btn" data-click="save-all-providers" class="btn-primary"><i class="fa-solid fa-floppy-disk"></i> Save All Providers</button>'
    + '<button data-click="refresh-provider-models" class="rounded-6 border-main text-secondary cursor-pointer text-12" style="padding:6px 14px;background:var(--bg-card)"><i class="fa-solid fa-rotate"></i> Refresh Models</button>'
    + '<span id="prov-status" class="text-sm text-muted"></span></div>';

  var tabNetwork = ''
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-toggle-on"></i> Enable Proxy</div>'
    +   '<label class="flex-ac gap-8 cursor-pointer">'
    +     '<input type="checkbox" id="settings-proxy-enabled" ' + (proxy.enabled ? 'checked' : '') + ' onchange="document.getElementById(\'settings-proxy-label\').textContent=this.checked?\'Enabled\':\'Disabled\'">'
    +     '<span id="settings-proxy-label" class="text-sm text-secondary">' + (proxy.enabled ? 'Enabled' : 'Disabled') + '</span>'
    +   '</label></div>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-link"></i> HTTP Proxy</div><input id="settings-proxy-http" class="settings-input" placeholder="http://proxy:8080" value="' + escapeHtml(proxy.http || '') + '"></div>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-link"></i> HTTPS Proxy</div><input id="settings-proxy-https" class="settings-input" placeholder="https://proxy:8443" value="' + escapeHtml(proxy.https || '') + '"></div>'
    + '<div class="flex-ac gap-10"><button data-click="save-proxy-settings" class="btn-primary"><i class="fa-solid fa-floppy-disk"></i> Save</button><span id="settings-proxy-status" class="text-sm text-muted"></span></div>';

  var tabSecurity = ''
    + '<h4 class="text-sm text-secondary" style="margin:0 0 8px">Permissions</h4>'
    + _renderPermissions(perms)
    + '<h4 class="text-sm text-secondary" style="margin:16px 0 8px">API Keys</h4>'
    + _renderApiKeys(apikeys);

  var tabResources = ''
    + '<h4 class="text-sm text-secondary" style="margin:0 0 8px">Token Budget</h4>'
    + _renderTokenBudget(tokens)
    + '<h4 class="text-sm text-secondary" style="margin:16px 0 8px">GGUF Models</h4>'
    + '<div class="settings-card"><div class="settings-card-label"><i class="fa-solid fa-upload"></i> Load Model</div>'
    + '<div class="flex gap-8"><input id="settings-gguf-path" class="settings-input" placeholder="/path/to/model.gguf">'
    + '<button data-click="load-gguf-settings" class="send-btn w-auto rounded-6" style="padding:0 16px">Load</button></div></div>'
    + '<div id="settings-gguf-list">' + _renderGGUFList(gguf) + '</div>';

  var tabAutomation = ''
    + _renderAutoCommit(ac);

  var tabConnections = _renderGateway(gateway);

  area.innerHTML = TEMPLATES.view('fa-sliders', 'Settings', 'All configuration — organised by category',
    '<style>'
    + '.settings-tabs{display:flex;gap:0;border-bottom:1px solid var(--border-main);margin-bottom:16px}'
    + '.settings-tab{padding:8px 18px;cursor:pointer;border-bottom:2px solid transparent;color:var(--text-tertiary);font-size:var(--font-size-sm);font-weight:500;transition:all .12s;user-select:none}'
    + '.settings-tab:hover{color:var(--text-secondary)}'
    + '.settings-tab.active{color:var(--accent);border-bottom-color:var(--accent)}'
    + '</style>'
    + '<div class="settings-tabs">'
    +   '<div class="settings-tab active" data-tab="general" data-click="switch-settings-tab"><i class="fa-solid fa-sliders"></i> General</div>'
    +   '<div class="settings-tab" data-tab="providers" data-click="switch-settings-tab"><i class="fa-solid fa-cloud"></i> Providers</div>'
    +   '<div class="settings-tab" data-tab="network" data-click="switch-settings-tab"><i class="fa-solid fa-plug"></i> Network</div>'
    +   '<div class="settings-tab" data-tab="security" data-click="switch-settings-tab"><i class="fa-solid fa-shield-halved"></i> Security</div>'
    +   '<div class="settings-tab" data-tab="resources" data-click="switch-settings-tab"><i class="fa-solid fa-coins"></i> Resources</div>'
    +   '<div class="settings-tab" data-tab="automation" data-click="switch-settings-tab"><i class="fa-solid fa-arrows-rotate"></i> Automation</div>'
    +   '<div class="settings-tab" data-tab="connections" data-click="switch-settings-tab-connections"><i class="fa-solid fa-tower-broadcast"></i> Connections</div>'
    +   '<div class="settings-tab" data-tab="mcp" data-click="switch-settings-tab-mcp"><i class="fa-solid fa-plug"></i> MCP</div>'
    + '</div>'
    + '<div id="settings-tab-general" class="settings-tab-content">' + tabGeneral + '</div>'
    + '<div id="settings-tab-providers" class="settings-tab-content" style="display:none">' + tabProviders + '</div>'
    + '<div id="settings-tab-network" class="settings-tab-content" style="display:none">' + tabNetwork + '</div>'
    + '<div id="settings-tab-security" class="settings-tab-content" style="display:none">' + tabSecurity + '</div>'
    + '<div id="settings-tab-resources" class="settings-tab-content" style="display:none">' + tabResources + '</div>'
    + '<div id="settings-tab-automation" class="settings-tab-content" style="display:none">' + tabAutomation + '</div>'
    + '<div id="settings-tab-connections" class="settings-tab-content" style="display:none">' + tabConnections + '</div>'
    + '<div id="settings-tab-mcp" class="settings-tab-content" style="display:none">' + _renderMCPServers(mcp) + '</div>'
  );

  setActivity('Ready', '—');
}

window.switchSettingsTab = function(name) {
  document.querySelectorAll('.settings-tab').forEach(function(t) {
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.settings-tab-content').forEach(function(p) {
    p.style.display = p.id === 'settings-tab-' + name ? 'block' : 'none';
  });
};

function _renderModelOptions(settings) {
  var prov = settings.provider || {};
  var providers = settings.available_providers || [];
  var cp = providers.find(function(p) { return p.id === (prov.name || 'opencode-zen'); }) || providers[0] || {};
  var models = cp.models || [];
  return models.length
    ? models.map(function(m) { return '<option value="' + escapeHtml(m) + '"' + (m === prov.model ? ' selected' : '') + '>' + escapeHtml(m) + '</option>'; }).join('')
    : '<option value="">No models</option>';
}

function _renderPermissions(perms) {
  var levels = perms.levels || ['permissive','normal','strict','silent'];
  var current = perms.level || 'normal';
  var descs = {permissive:'Allow all commands', normal:'Block dangerous patterns', strict:'Read-only + safe tools', silent:'Read-only, no confirmations'};
  return '<div class="flex flex-col gap-6">'
    + levels.map(function(l) {
      var active = l === current;
      return '<div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:' + (active ? 'var(--accent-dim)' : 'var(--bg-input)') + ';border-radius:6px;cursor:pointer" data-click="set-perm-level" data-level="' + l + '">'
        + '<input type="radio" name="perm-level" ' + (active ? 'checked' : '') + ' style="accent-color:var(--accent)">'
        + '<div><strong>' + l + '</strong><br><span class="text-11" style="color:var(--text-tertiary)">' + (descs[l] || '') + '</span></div>'
        + (active ? '<span class="text-semibold" style="margin-left:auto;color:var(--accent)">Current</span>' : '')
        + '</div>';
    }).join('') + '</div>';
}

function _renderTokenBudget(tokens) {
  var pct = tokens.percentage || 0;
  var barColor = pct > 80 ? 'var(--error)' : pct > 50 ? 'var(--warning)' : 'var(--success)';
  return '<div class="settings-card">'
    + '<div class="flex" style="justify-content:space-between;margin-bottom:6px">'
    + '<span class="text-secondary text-sm">Used: ' + (tokens.used || 0).toLocaleString() + '</span>'
    + '<span class="text-secondary text-sm">Limit: ' + ((tokens.limit || 0) ? (tokens.limit || 0).toLocaleString() : 'Unlimited') + '</span>'
    + '</div>'
    + '<div style="background:var(--fill-active);border-radius:var(--radius-full);height:10px;overflow:hidden;margin-bottom:4px">'
    + '<div style="width:' + Math.min(pct, 100) + '%;height:100%;background:' + barColor + ';border-radius:var(--radius-full);transition:width 0.5s"></div></div>'
    + '<div class="flex text-xs" style="justify-content:space-between">'
    + '<span style="color:var(--text-tertiary)">' + pct + '% used</span>'
    + '<span style="color:var(--text-tertiary)">' + (tokens.remaining || 0).toLocaleString() + ' remaining</span>'
    + '</div>'
    + '<button data-click="reset-token-budget-settings" class="btn-primary mt-8 h-32 text-12" style="background:var(--warning);color:#000"><i class="fa-solid fa-rotate"></i> Reset</button>'
    + '<span id="settings-token-status" class="text-sm text-muted ml-8"></span>'
    + '</div>';
}

function _renderAutoCommit(ac) {
  return '<div class="settings-card">'
    + '<div class="flex-ac-sb">'
    + '<div><span class="text-primary text-bold">Status</span>'
    + '<br><span class="text-muted text-sm">' + (ac.enabled ? '🟢 Running' : '⚪ Stopped') + '</span></div>'
    + '<button data-click="toggle-autocommit-settings" class="send-btn w-auto rounded-6" style="padding:6px 18px;background:' + (ac.enabled ? 'var(--error)' : 'var(--success)') + '">'
    + (ac.enabled ? 'Stop' : 'Start') + '</button>'
    + '</div>'
    + '<div class="mt-8 text-sm" style="color:var(--text-tertiary)">'
    + 'Interval: ' + (ac.interval || '—') + 's · Last commit: ' + (ac.last_commit || 'Never')
    + '</div></div>';
}

function _renderGGUFList(models) {
  if (!Array.isArray(models) || !models.length) {
    return '<span class="text-muted text-sm">No GGUF models loaded.</span>'
      + '<button data-click="unload-gguf-settings" class="btn-primary h-32 text-12" style="margin-top:6px;background:var(--error)" disabled><i class="fa-solid fa-power-off"></i> Unload</button>';
  }
  return models.map(function(m) {
    var name = m.name || m.path || 'unknown';
    var loaded = m.loaded ? '🟢' : '⚪';
    var size = m.size ? ' · ' + Math.round(m.size / 1024 / 1024) + 'MB' : '';
    return '<div class="flex-ac-sb py-6 border-bottom-light text-sm">'
      + '<span>' + loaded + ' ' + escapeHtml(name) + escapeHtml(size) + '</span></div>';
  }).join('')
    + '<button data-click="unload-gguf-settings" class="btn-primary mt-8 h-32 text-12" style="background:var(--error)"><i class="fa-solid fa-power-off"></i> Unload</button>';
}

function _renderApiKeys(apikeys) {
  var entries = Object.entries(apikeys);
  if (!entries.length) {
    return '<div class="settings-card"><span class="text-muted text-sm">No API keys stored. Add one in the Provider section above.</span></div>';
  }
  return entries.map(function(kv) {
    var name = kv[0];
    var info = kv[1] || {};
    return '<div class="settings-card"><div class="flex-ac gap-10">'
      + '<span style="font-size:18px">🔑</span>'
      + '<div><strong class="text-primary text-sm">' + escapeHtml(name) + '</strong>'
      + '<br><span class="text-muted text-11 text-mono">' + escapeHtml(info.masked || '—') + '</span></div>'
      + (info.has_key ? '<span class="text-11" style="color:var(--success);margin-left:auto">✓ Configured</span>' : '')
      + '</div></div>';
  }).join('');
}

function _renderMCPServers(servers) {
  if (!Array.isArray(servers) || !servers.length) {
    return '<div class="settings-card"><span class="text-muted text-sm">No MCP servers configured.</span>'
      + '<div class="mt-8 flex gap-8">'
      + '<input id="settings-mcp-name" class="settings-input flex-1" placeholder="Server name">'
      + '<input id="settings-mcp-cmd" class="settings-input flex-2" placeholder="Command (e.g. npx ...)">'
      + '<button data-click="add-mcp-settings" class="send-btn w-auto rounded-6" style="padding:0 16px">Add</button>'
      + '</div></div>';
  }
  return '<div class="mb-8 flex gap-8">'
    + '<input id="settings-mcp-name" class="settings-input flex-1" placeholder="Server name">'
    + '<input id="settings-mcp-cmd" class="settings-input flex-2" placeholder="Command (e.g. npx ...)">'
    + '<button data-click="add-mcp-settings" class="send-btn w-auto rounded-6" style="padding:0 16px">Add</button>'
    + '</div>'
    + servers.map(function(s) {
      var name = s.name || s.id || 'unknown';
      var status = s.status || 'unknown';
      var color = status === 'running' ? 'var(--success)' : status === 'error' ? 'var(--error)' : 'var(--text-muted)';
      return '<div class="settings-card"><div class="flex-ac-sb">'
        + '<div><strong>' + escapeHtml(name) + '</strong></div>'
        + '<div><span style="color:' + color + ';font-size:var(--font-size-sm)">● ' + status + '</span>'
+ ' <button class="btn-icon-accent" data-click="restart-mcp-settings" data-mcp="' + escapeHtml(name) + '" title="Restart">↻</button>'
         + ' <button class="btn-icon-error" data-click="del-mcp-settings" data-mcp="' + escapeHtml(name) + '" title="Remove">✕</button>'
        + '</div></div>'
        + '<div class="text-11 text-muted" style="margin-top:4px">' + escapeHtml(s.command || s.description || '') + '</div>'
        + '</div>';
    }).join('');
}

function _renderGateway(gw) {
  var channels = gw && gw.channels ? gw.channels : [];
  if (!channels.length) {
    return '<div class="text-muted text-sm mb-12">No platforms connected.</div>'
      + _renderConnectForm('telegram', 'Telegram', 'fa-telegram', '#0088cc')
      + _renderConnectForm('discord', 'Discord', 'fa-discord', '#5865F2');
  }
  var html = '';
  channels.forEach(function(ch) {
    var isOnline = ch.status === 'connected' || ch.status === 'running';
    html += '<div class="settings-card"><div class="flex-ac-sb">'
      + '<div class="flex-ac gap-10">'
      + '<span style="font-size:24px;color:' + (isOnline ? 'var(--success)' : 'var(--text-muted)') + '">'
      + (ch.name === 'Telegram' ? '✈️' : '💬') + '</span>'
      + '<div><strong>' + escapeHtml(ch.name) + '</strong>'
      + '<br><span class="text-11 text-muted">' + (ch.message_count || 0) + ' msgs'
      + (ch.last_message ? ' · ' + new Date(ch.last_message).toLocaleString() : '') + '</span></div></div>'
      + '<span style="font-size:var(--font-size-sm);color:' + (isOnline ? 'var(--success)' : 'var(--text-muted)') + '">'
      + (isOnline ? '● Connected' : '○ Disconnected') + '</span>'
      + '</div>'
      + (ch.error ? '<div class="rounded-4 text-11" style="margin-top:6px;padding:6px 8px;background:var(--error-dim);color:var(--error)">' + escapeHtml(ch.error) + '</div>' : '')
      + '<div class="mt-8 flex gap-8">'
      +   '<input id="gw-token-' + ch.name.toLowerCase() + '" type="password" class="settings-input flex-1 h-34 text-12" placeholder="New token to reconnect...">'
      +   '<button data-click="connect-gateway-settings" data-gw-platform="' + ch.name.toLowerCase() + '" class="send-btn w-auto px-14 rounded-6 h-34 text-12">Connect</button>'
      +   '<button data-click="disconnect-gateway-settings" data-gw-platform="' + ch.name.toLowerCase() + '" class="send-btn w-auto px-14 rounded-6 h-34 text-12" style="background:var(--error)">Disconnect</button>'
      + '</div></div>';
  });
  return html;
}

function _renderConnectForm(platform, label, icon, color) {
  return '<div class="settings-card"><div class="flex-ac gap-10 mb-8">'
    + '<span style="font-size:20px;color:' + color + '">' + (platform === 'telegram' ? '✈️' : '💬') + '</span>'
    + '<strong>' + escapeHtml(label) + '</strong></div>'
    + '<div class="flex gap-8">'
    + '<input id="gw-token-' + platform + '" type="password" class="settings-input flex-1" placeholder="Paste your ' + label + ' bot token...">'
    + '<button data-click="connect-gateway-settings" data-gw-platform="' + platform + '" class="send-btn w-auto rounded-6" style="padding:0 16px">Connect</button>'
    + '</div></div>';
}

window.loadMCPTab = function() {
  var container = document.getElementById('settings-tab-mcp');
  if (!container) return;
  container.innerHTML = '<div class="text-muted text-sm">Loading...</div>';
  fetch('/api/mcp').then(function(r){return r.json()}).then(function(servers) {
    container.innerHTML = _renderMCPServers(servers);
  }).catch(function(e) {
    container.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  });
};

window.addMCPServerFromSettings = function() {
  var name = document.getElementById('settings-mcp-name')?.value.trim();
  var cmd = document.getElementById('settings-mcp-cmd')?.value.trim();
  if (!name || !cmd) { showToast('Name and command required', 'error'); return; }
  fetch('/api/mcp', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:name, command:cmd}) })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'added' ? 'MCP server added' : (d.error || 'Failed'), d.status === 'added' ? 'success' : 'error');
      if (d.status === 'added') loadMCPTab();
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.delMCPFromSettings = async function(name) {
  var ok = await showConfirm('Remove MCP server?', '"' + name + '" will be removed from MCP configuration.', { confirmText: 'Remove', danger: true });
  if (!ok) return;
  fetch('/api/mcp/' + encodeURIComponent(name), { method:'DELETE' })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'removed' ? 'MCP server removed' : (d.error || 'Failed'), d.status === 'removed' ? 'success' : 'error');
      loadMCPTab();
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.restartMCPFromSettings = function(name) {
  fetch('/api/mcp/' + encodeURIComponent(name) + '/restart', { method:'POST' })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'restarted' ? 'MCP server restarted' : (d.error || 'Failed'), d.status === 'restarted' ? 'success' : 'error');
      loadMCPTab();
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.loadConnectionsTab = function() {
  var container = document.getElementById('settings-tab-connections');
  if (!container) return;
  container.innerHTML = '<div class="text-muted text-sm">Loading...</div>';
  fetch('/api/dashboard/gateway').then(function(r){return r.json()}).then(function(d) {
    container.innerHTML = _renderGateway(d);
  }).catch(function(e) {
    container.innerHTML = '<span class="text-error">' + escapeHtml(e.message) + '</span>';
  });
};

window.connectGateway = function(platform) {
  var token = document.getElementById('gw-token-' + platform)?.value;
  if (!token) { showToast('Please paste your token first', 'error'); return; }
  fetch('/api/gateway/start', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({platform:platform, token:token}) })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'ok' ? platform + ' connected!' : (d.message || 'Failed'), d.status === 'ok' ? 'success' : 'error');
      if (d.status === 'ok') loadConnectionsTab();
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.disconnectGateway = async function(platform) {
  var ok = await showConfirm('Disconnect ' + platform + '?', 'The gateway connection to ' + platform + ' will be stopped.', { confirmText: 'Disconnect', danger: true });
  if (!ok) return;
  fetch('/api/gateway/stop', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({platform:platform}) })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(platform + ' disconnected', 'info');
      loadConnectionsTab();
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.onMSProviderChange = function(providerId) {
  showToast('Switch to Providers tab to configure model, URL & key', 'info');
};

window.saveGeneralSettings = function() {
  var btn = document.getElementById('save-general-btn');
  var status = document.getElementById('ms-status');
  if (btn) { btn.disabled = true; btn.style.opacity = '0.6'; }
  if (status) status.textContent = 'Saving...';
  var data = {
    provider: { name: document.getElementById('ms-provider')?.value || '' },
    // system_prompt: hardcoded in core/constants.py — not user-editable
    temperature: parseFloat(document.getElementById('ms-temp-value')?.textContent || '0.7'),
    max_turns: parseInt(document.getElementById('ms-max-turns')?.value || '10', 10),
    cli_theme: document.getElementById('ms-theme')?.value || 'dark',
  };
  fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) })
    .then(function(r){return r.json()}).then(function(result) {
      if (result.status === 'ok') {
        if (status) { status.textContent = 'Saved!'; status.style.color = 'var(--success)'; }
        if (data.cli_theme) { document.documentElement.setAttribute('data-theme', data.cli_theme); localStorage.setItem('widdx-theme', data.cli_theme); }
        showToast('Settings saved', 'success');
      } else {
        if (status) { status.textContent = 'Error: ' + (result.message || 'Failed'); status.style.color = 'var(--error)'; }
      }
    }).catch(function(e) {
      if (status) { status.textContent = 'Error: ' + e.message; status.style.color = 'var(--error)'; }
    }).finally(function() {
      if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    });
};

window.saveAllProviders = function() {
  var btn = document.getElementById('save-providers-btn');
  var status = document.getElementById('prov-status');
  if (btn) { btn.disabled = true; btn.style.opacity = '0.6'; }
  if (status) status.textContent = 'Saving...';

  var activeProvider = document.getElementById('ms-provider')?.value || 'opencode-zen';
  var allProvs = {};
  var providerIds = ['opencode-zen', 'deepseek', 'openai', 'ollama', 'gguf'];
  providerIds.forEach(function(pid) {
    var modelEl = document.getElementById('prov-model-' + pid);
    var urlEl = document.getElementById('prov-url-' + pid);
    var keyEl = document.getElementById('prov-key-' + pid);
    allProvs[pid] = {
      model: modelEl ? modelEl.value : '',
      base_url: urlEl ? urlEl.value : '',
      api_key: keyEl ? keyEl.value : '',
    };
  });

  var active = allProvs[activeProvider] || {};
  var thinking = document.getElementById('thinking-toggle')?.checked !== false;

  var data = {
    provider: {
      name: activeProvider,
      model: active.model || '',
      base_url: active.base_url || '',
    },
    thinking: thinking,
    all_providers: allProvs,
  };
  if (active.api_key) data.provider.api_key = active.api_key;

  fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data) })
    .then(function(r){return r.json()}).then(function(result) {
      if (result.status === 'ok') {
        if (status) { status.textContent = 'Saved!'; status.style.color = 'var(--success)'; }
        document.getElementById('modelName').textContent = active.model || '—';
        showToast('All providers saved', 'success');
      } else {
        if (status) { status.textContent = 'Error: ' + (result.message || 'Failed'); status.style.color = 'var(--error)'; }
      }
    }).catch(function(e) {
      if (status) { status.textContent = 'Error: ' + e.message; status.style.color = 'var(--error)'; }
    }).finally(function() {
      if (btn) { btn.disabled = false; btn.style.opacity = '1'; }
    });
};

window.saveModelSetup = window.saveGeneralSettings;

window.saveProxySettings = function() {
  var enabled = document.getElementById('settings-proxy-enabled')?.checked || false;
  var http = document.getElementById('settings-proxy-http')?.value || '';
  var https = document.getElementById('settings-proxy-https')?.value || '';
  var status = document.getElementById('settings-proxy-status');
  if (status) status.textContent = 'Saving...';
  fetch('/api/proxy', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({http:http, https:https, enabled:enabled})
  }).then(function(r){return r.json()}).then(function(d) {
    if (status) status.textContent = d.status === 'updated' ? 'Saved' : (d.error || 'Failed');
    if (d.status === 'updated') showToast('Proxy updated', 'success');
  }).catch(function(e) { if (status) status.textContent = e.message; showToast(e.message, 'error'); });
};

window.setPermLevel = function(level) {
  fetch('/api/permissions', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({level:level}) })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'set' ? 'Permission: ' + level : (d.error || 'Failed'), d.status === 'set' ? 'success' : 'error');
      showModelSetupView(document.getElementById('messagesArea'));
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.resetTokenBudgetSettings = async function() {
  var ok = await showConfirm('Reset token budget?', 'All token usage counters will be reset to zero.', { confirmText: 'Reset', danger: true });
  if (!ok) return;
  var status = document.getElementById('settings-token-status');
  if (status) status.textContent = 'Resetting...';
  fetch('/api/token-budget/reset', { method:'POST' })
    .then(function(r){return r.json()}).then(function(d) {
      if (status) status.textContent = d.status === 'reset' ? 'Reset' : (d.error || 'Failed');
      if (d.status === 'reset') { showToast('Token budget reset', 'success'); showModelSetupView(document.getElementById('messagesArea')); }
    }).catch(function(e) { if (status) status.textContent = e.message; showToast(e.message, 'error'); });
};

window.toggleAutoCommitSettings = function() {
  fetch('/api/autocommit/toggle', { method:'POST' })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'toggled' ? 'Auto-commit ' + (d.enabled ? 'started' : 'stopped') : (d.error || 'Failed'), d.status === 'toggled' ? 'success' : 'error');
      showModelSetupView(document.getElementById('messagesArea'));
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.loadGGUFSettings = function() {
  var path = document.getElementById('settings-gguf-path')?.value.trim();
  if (!path) { showToast('Please enter a model path', 'error'); return; }
  fetch('/api/gguf/load', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({path:path}) })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'loaded' ? 'Model loaded' : (d.error || 'Failed'), d.status === 'loaded' ? 'success' : 'error');
      showModelSetupView(document.getElementById('messagesArea'));
    }).catch(function(e) { showToast(e.message, 'error'); });
};

window.refreshProviderModels = async function() {
  var active = document.getElementById('ms-provider')?.value || 'opencode-zen';
  try {
    var r = await fetch('/api/settings/models?provider=' + encodeURIComponent(active));
    var d = await r.json();
    if (d.models && d.models.length) {
      var sel = document.getElementById('prov-model-' + active.replace(/\s+/g, '-'));
      if (sel) {
        var current = sel.value;
        sel.innerHTML = d.models.map(function(m) {
          return '<option value="' + escapeHtml(m) + '"' + (m === current ? ' selected' : '') + '>' + escapeHtml(m) + '</option>';
        }).join('');
      }
      showToast('Models refreshed: ' + d.models.length + ' available', 'success');
    } else {
      showToast('No models returned for ' + active, 'info');
    }
  } catch(e) { showToast(e.message, 'error'); }
};

window.unloadGGUFSettings = async function() {
  var ok = await showConfirm('Unload GGUF model?', 'The current GGUF model will be unloaded from memory.', { confirmText: 'Unload', danger: true });
  if (!ok) return;
  fetch('/api/gguf/unload', { method:'POST' })
    .then(function(r){return r.json()}).then(function(d) {
      showToast(d.status === 'unloaded' ? 'Model unloaded' : (d.error || 'Failed'), 'info');
      showModelSetupView(document.getElementById('messagesArea'));
    }).catch(function(e) { showToast(e.message, 'error'); });
};

async function showSettingsView(area) {
  return showModelSetupView(area);
}
