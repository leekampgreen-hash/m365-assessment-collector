const sections = [
  ['WORKSPACE', [['Overview', 'home']]],
  ['USERS', [['User Intelligence', 'users']]],
  ['SECURITY', [['MFA Coverage', 'shield-check'], ['Conditional Access', 'lock'], ['Admin Roles', 'crown'], ['Risky Users', 'alert-triangle'], ['Sign-in Activity', 'activity']]],
  ['PRODUCTIVITY', [['Exchange', 'mail'], ['OneDrive', 'cloud'], ['SharePoint', 'layout'], ['Teams', 'message-circle']]],
  ['LICENSE', [['Utilization', 'chart-bar'], ['Optimizer', 'sparkles'], ['Parking Report', 'car']]],
  ['PROTECTION', [['Defender for Office 365', 'shield'], ['Cloud App Discovery', 'search'], ['DLP Violations', 'alert-circle'], ['Sensitivity Labels', 'tag']]],
  ['IDENTITY', [['Guest Users', 'user-plus'], ['Auth Methods', 'key'], ['Named Locations', 'map-pin']]],
  ['COMPLIANCE', [['Intune Devices', 'device-laptop'], ['Compliance Policies', 'clipboard-check'], ['Mobile Apps', 'device-mobile']]],
  ['SETTINGS', [['API Keys', 'terminal'], ['Email Reports', 'send'], ['Tenants', 'building']]]
];

const navigation = document.querySelector('#navigation');
const content = document.querySelector('#content');
const headerTitle = document.querySelector('#header-title');

sections.forEach(([section, items]) => {
  const heading = document.createElement('li');
  heading.className = 'nav-item navbar-heading';
  heading.textContent = section;
  navigation.appendChild(heading);
  items.forEach(([title, icon]) => {
    const slug = title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
    const item = document.createElement('li');
    item.className = 'nav-item';
    item.innerHTML = `<a class="nav-link" href="#/${slug}" data-page="${slug}"><span class="nav-link-icon d-md-none d-lg-inline-block"><i class="ti ti-${icon}"></i></span><span class="nav-link-title">${title}</span></a>`;
    navigation.appendChild(item);
  });
});

function render() {
  const slug = window.location.hash.replace(/^#\/?/, '') || 'overview';
  const link = navigation.querySelector(`[data-page="${slug}"]`) || navigation.querySelector('[data-page="overview"]');
  const title = link ? link.querySelector('.nav-link-title').textContent : 'Overview';
  navigation.querySelectorAll('.nav-link').forEach((navLink) => navLink.classList.toggle('active', navLink === link));
  headerTitle.textContent = title;
  content.innerHTML = `<div class="page-header mb-4"><div><h2 class="page-title">${title}</h2><div class="text-secondary">This section is under construction</div></div></div><div class="card placeholder-card"><div class="card-body"><div class="placeholder-icon mb-3"><i class="ti ti-tool"></i></div><h3 class="card-title">${title}</h3><p class="text-secondary mb-0">Placeholder content for this assessment area.</p></div></div>`;
}

window.addEventListener('hashchange', render);
render();
