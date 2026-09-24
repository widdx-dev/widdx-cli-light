/* WIDDX Nexus — Gateway View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity, showConfirm, showToast) */

async function showGatewayView(area) {
  setActivity('Loading', 'gateway');
  area.innerHTML = '<div class="view-container"><div class="view-header"><h2><i class="fa-solid fa-tower-broadcast"></i> Gateway Hub</h2><p>Connect WIDDX to Telegram or Discord \u2014 easy step-by-step guide</p></div><div class="view-body"><div class="section-card"><div class="section-card-header"><i class="fa-solid fa-robot"></i> Step 1: Choose your platform</div><div class="section-card-body flex" style="gap:12px;flex-wrap:wrap"><div class="gw-option" data-click="select-platform" data-platform="telegram" id="gw-opt-telegram"><i class="fa-brands fa-telegram" style="font-size:28px;color:#0088cc"></i><span>Telegram</span><small>Connect a bot to your Telegram</small></div><div class="gw-option" data-click="select-platform" data-platform="discord" id="gw-opt-discord"><i class="fa-brands fa-discord" style="font-size:28px;color:#5865F2"></i><span>Discord</span><small>Connect a bot to your Discord</small></div></div></div><div id="gw-setup-form" style="display:none"></div><div class="gateway-grid" id="gateway-view-grid"><div class="empty-state"><i class="fa-solid fa-spinner fa-spin"></i><p>Loading channels...</p></div></div></div></div>';

  try {
    const r = await fetch('/api/dashboard/gateway');
    var data = await r.json();
    renderGatewayChannels(data);
  } catch(e) {
    var g2 = document.getElementById('gateway-view-grid');
    if (g2) g2.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Error</h3><p>' + escapeHtml(e.message) + '</p></div>';
  }
  setActivity('Ready', '\u2014');
}

window.selectPlatform = function(platform) {
  var form = document.getElementById('gw-setup-form');
  document.querySelectorAll('.gw-option').forEach(function(o) { o.classList.remove('selected'); });
  document.getElementById('gw-opt-' + platform).classList.add('selected');
  if (platform === 'telegram') {
    form.style.display = 'block';
    form.innerHTML = '<div class="section-card"><div class="section-card-header"><i class="fa-solid fa-key"></i> Step 2: Get your bot token</div><div class="section-card-body"><div class="gw-steps"><div class="gw-step"><span class="gw-step-num">1</span><div><strong>Open Telegram</strong><br><span class="text-muted text-sm">Search for <strong>@BotFather</strong> in Telegram</span></div></div><div class="gw-step"><span class="gw-step-num">2</span><div><strong>Create a new bot</strong><br><span class="text-muted text-sm">Send <code>/newbot</code> to BotFather and follow the steps</span></div></div><div class="gw-step"><span class="gw-step-num">3</span><div><strong>Copy the token</strong><br><span class="text-muted text-sm">BotFather will give you a token like <code>123456:ABC-DEF1234</code></span></div></div></div><div class="flex-ac gap-8" style="margin-top:12px;flex-wrap:wrap"><span class="text-bold text-sm">Paste your token:</span><input id="gw-token" type="password" class="flex-1 h-38 bg-input border-main text-primary text-13" style="min-width:200px;border-radius:var(--radius-md);padding:0 12px" placeholder="123456:ABC-DEF1234"><button class="send-btn w-auto px-20 rounded-6 h-38" data-click="start-gateway" data-platform="telegram"><i class="fa-solid fa-plug"></i> Connect Telegram</button></div></div></div>';
  } else if (platform === 'discord') {
    form.style.display = 'block';
    form.innerHTML = '<div class="section-card"><div class="section-card-header"><i class="fa-solid fa-key"></i> Step 2: Get your bot token</div><div class="section-card-body"><div class="gw-steps"><div class="gw-step"><span class="gw-step-num">1</span><div><strong>Go to Discord Developer Portal</strong><br><span class="text-muted text-sm">Open <a href="https://discord.com/developers/applications" target="_blank" style="color:var(--accent)">discord.com/developers</a></span></div></div><div class="gw-step"><span class="gw-step-num">2</span><div><strong>Create an application</strong><br><span class="text-muted text-sm">Click "New Application", give it a name</span></div></div><div class="gw-step"><span class="gw-step-num">3</span><div><strong>Create a bot</strong><br><span class="text-muted text-sm">Go to "Bot" tab, click "Add Bot", then "Reset Token"</span></div></div><div class="gw-step"><span class="gw-step-num">4</span><div><strong>Copy the token</strong><br><span class="text-muted text-sm">Click "Copy" to get your bot token</span></div></div></div><div class="flex-ac gap-8" style="margin-top:12px;flex-wrap:wrap"><span class="text-bold text-sm">Paste your token:</span><input id="gw-token" type="password" class="flex-1 h-38 bg-input border-main text-primary text-13" style="min-width:200px;border-radius:var(--radius-md);padding:0 12px" placeholder="paste your token here"><button class="send-btn w-auto px-20 rounded-6 h-38" data-click="start-gateway" data-platform="discord"><i class="fa-solid fa-plug"></i> Connect Discord</button></div></div></div>';
  }
};

window.startGateway = async function(platform) {
  var token = document.getElementById('gw-token')?.value;
  if (!token) { showToast('Please paste your token first', 'error'); return; }
  try {
    var r = await fetch('/api/gateway/start', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({platform:platform, token:token})
    });
    var d = await r.json();
    if (d.status === 'ok') {
      showToast(platform + ' connected successfully!', 'success');
      renderGatewayChannels();
    } else {
      showToast(d.message || 'Connection failed', 'error');
    }
  } catch(e) { showToast(e.message, 'error'); }
};

window.stopGateway = async function(platform) {
  var ok = await showConfirm('Disconnect ' + platform + '?', 'The gateway will be stopped immediately.', { confirmText: 'Disconnect', danger: true });
  if (!ok) return;
  try {
    var r = await fetch('/api/gateway/stop', {
      method:'POST', headers:{'Content-Type':'application/json'},
      body:JSON.stringify({platform:platform})
    });
    await r.json();
    showToast(platform + ' disconnected', 'info');
    renderGatewayChannels();
  } catch(e) { showToast(e.message, 'error'); }
};

async function renderGatewayChannels(existingData) {
  var grid = document.getElementById('gateway-view-grid');
  if (!grid) return;
  try {
    var data = existingData;
    if (!data) {
      var r = await fetch('/api/dashboard/gateway');
      data = await r.json();
    }
    if (data?.channels?.length) {
      grid.innerHTML = data.channels.map(function(ch) {
        var isRunning = ch.status === 'running';
        return '<div class="gateway-card"><div class="gateway-top"><div class="gateway-status-dot ' + (isRunning ? 'connected' : 'disconnected') + '"></div><span class="gateway-name">' + escapeHtml(ch.name) + '</span><span class="gateway-status-label">' + (isRunning ? 'Connected' : 'Offline') + '</span></div><div class="gateway-meta">' + (ch.message_count || 0) + ' messages' + (ch.last_message ? ' \u00b7 Last activity: ' + new Date(ch.last_message).toLocaleString() : '') + '</div>' + (ch.error ? '<div class="gateway-error">\u26a0 ' + escapeHtml(ch.error) + '</div>' : '') + '<div class="mt-8"><button class="gw-disconnect-btn" data-click="stop-gateway" data-platform="' + ch.name.toLowerCase() + '">Disconnect</button></div></div>';
      }).join('');
    } else {
      grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-tower-broadcast"></i><h3>No channels connected</h3><p>Choose a platform above and follow the steps to connect.</p></div>';
    }
  } catch(e) {
    grid.innerHTML = '<div class="empty-state"><i class="fa-solid fa-triangle-exclamation"></i><h3>Error</h3><p>' + escapeHtml(e.message) + '</p></div>';
  }
}
