/* WIDDX Nexus — Skills View */
/* Depends on: nexus.js (TEMPLATES, escapeHtml, setActivity) */

async function showSkillsView(area) {
  setActivity('Loading', 'skills');
  area.innerHTML = TEMPLATES.view('fa-toolbox', 'Skill Studio', 'Browse and manage agent skills',
    TEMPLATES.filterBar('skills-search', 'Search skills...',
      '<button class="filter-btn" data-click="load-skills-view"><i class="fa-solid fa-rotate"></i> Refresh</button>',
      'filterSkillsView(this.value)')
    + '<div class="skills-grid" id="skills-grid">' + TEMPLATES.loading('Loading skills...') + '</div>'
  );

  try {
    const r = await fetch('/api/dashboard/skills');
    var skills = await r.json();
    var grid = document.getElementById('skills-grid');
    if (!grid) return;
    if (skills.length) {
      window._allSkills = skills;
      grid.innerHTML = skills.map(function(s) {
        var cat = s.name?.includes('-') ? s.name.split('-')[0] : 'general';
        return '<div class="skill-card"><div class="skill-top"><div class="skill-icon"><i class="fa-solid fa-toolbox"></i></div><div class="skill-info"><div class="skill-name">' + escapeHtml(s.name || '') + '</div><div class="skill-desc">' + escapeHtml(s.description || '') + '</div></div></div><span class="skill-tag">' + escapeHtml(cat) + '</span>' + '<button class="skill-toggle active">Enabled</button></div>';
      }).join('');
    } else {
      grid.innerHTML = TEMPLATES.empty('fa-toolbox', 'No skills found', 'Skills will appear here once installed.');
    }
    setActivity('Ready', '\u2014');
  } catch(e) {
    var g3 = document.getElementById('skills-grid');
    if (g3) g3.innerHTML = TEMPLATES.error(e.message);
    setActivity('Ready', '\u2014');
  }
}

window.filterSkillsView = function(query) {
  var skills = window._allSkills || [];
  if (!skills.length) return;
  var q = query.toLowerCase().trim();
  var items = document.querySelectorAll('.skill-card');
  items.forEach(function(card) {
    var text = card.textContent.toLowerCase();
    card.style.display = (!q || text.indexOf(q) !== -1) ? '' : 'none';
  });
};

window.loadSkillsView = function() {
  var area = document.getElementById('messagesArea');
  if (area && typeof showSkillsView === 'function') showSkillsView(area);
};
