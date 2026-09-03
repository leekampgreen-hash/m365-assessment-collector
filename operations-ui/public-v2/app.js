// Page descriptions for dummy pages
const pageDescriptions = {
    'overview': 'Get a comprehensive overview of your M365 tenant health, security posture, and user activity.',
    'user-intelligence': 'Analyze user behavior patterns, collaboration metrics, and productivity insights.',
    'mfa-coverage': 'Monitor Multi-Factor Authentication adoption across all users and identify gaps.',
    'conditional-access': 'Review and manage Conditional Access policies and their enforcement status.',
    'admin-roles': 'View administrator roles, permissions, and privileged account activity.',
    'risky-users': 'Identify users with risky sign-in behavior or compromised accounts.',
    'sign-in-activity': 'Audit sign-in logs, failed attempts, and authentication patterns.',
    'exchange': 'Manage Exchange Online mailboxes, retention policies, and mailbox permissions.',
    'onedrive': 'Monitor OneDrive storage usage, sharing settings, and file access.',
    'sharepoint': 'Administer SharePoint sites, permissions, and content management.',
    'teams': 'Review Microsoft Teams usage, meetings, chats, and team governance.',
    'utilization': 'Track license allocation, utilization rates, and assignment details.',
    'optimizer': 'Optimize license assignments and identify cost-saving opportunities.',
    'parking-report': 'Generate reports on parked or unused licenses and resources.',
    'defender-office365': 'Monitor Defender for Office 365 threats, policies, and protection status.',
    'cloud-app-discovery': 'Discover shadow IT apps connected to your M365 environment.',
    'dlp-violations': 'Review Data Loss Prevention policy violations and sensitive data exposure.',
    'sensitivity-labels': 'Manage information protection labels and classified content.',
    'guest-users': 'Audit external guest users, their access levels, and invitation status.',
    'auth-methods': 'Review authentication methods registered by users and security defaults.',
    'named-locations': 'Define and manage trusted IP ranges and location-based policies.',
    'intune-devices': 'Monitor enrolled devices, compliance status, and managed applications.',
    'compliance-policies': 'Create and manage compliance policies across your organization.',
    'mobile-apps': 'Control mobile application access and mobile device management.',
    'api-keys': 'Generate and manage API keys for external integrations.',
    'email-reports': 'Configure automated email reports and delivery schedules.',
    'tenants': 'Manage multiple M365 tenants and cross-tenant configurations.'
};

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initNavigation();
    initSectionCollapsible();
    initSidebarToggle();
    handleInitialRoute();
});

// Handle hash changes
window.addEventListener('hashchange', function() {
    handleRouteChange();
});

// Initialize sidebar toggle
function initSidebarToggle() {
    const toggleBtn = document.getElementById('sidebarToggle');
    if (toggleBtn) {
        toggleBtn.addEventListener('click', function() {
            const sidebar = document.getElementById('sidebar');
            sidebar.classList.toggle('collapsed');
        });
    }
}

// Initialize section collapsible
function initSectionCollapsible() {
    const sectionHeaders = document.querySelectorAll('.section-header');
    
    sectionHeaders.forEach(function(header) {
        header.addEventListener('click', function() {
            const navSection = this.parentElement;
            const isActive = !navSection.classList.contains('collapsed');
            
            // Toggle section collapsed state
            if (isActive) {
                navSection.classList.add('collapsed');
            } else {
                navSection.classList.remove('collapsed');
            }
        });
    });
}

// Handle URL routing
function handleInitialRoute() {
    const hash = window.location.hash || '#/overview';
    loadPage(hash);
}

function handleRouteChange() {
    const hash = window.location.hash;
    loadPage(hash);
}

function loadPage(hash) {
    // Parse hash to get page name
    const pageName = hash.replace('#/', '') || 'overview';
    
    // Update active menu item
    updateActiveMenuItem(pageName);
    
    // Load page content
    renderDummyPage(pageName);
}

// Update active menu item
function updateActiveMenuItem(pageName) {
    // Remove active class from all nav items
    document.querySelectorAll('.nav-item').forEach(function(item) {
        item.classList.remove('active');
    });
    
    // Add active class to current page
    const currentPageItem = document.querySelector(`.nav-item[data-page="${pageName}"]`);
    if (currentPageItem) {
        currentPageItem.classList.add('active');
        
        // Scroll into view if needed
        currentPageItem.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
}

// Render dummy page content
function renderDummyPage(pageName) {
    const container = document.getElementById('contentContainer');
    if (!container) return;
    
    const title = getPageTitle(pageName);
    const description = pageDescriptions[pageName] || 'No description available.';
    
    container.innerHTML = `
        <div class="page-card">
            <div class="placeholder-icon">&#128202;</div>
            <h1 class="page-title">${title}</h1>
            <p class="page-subtitle">This section is under construction</p>
            <p class="page-description">${description}</p>
        </div>
    `;
}

// Get page title from page name
function getPageTitle(pageName) {
    const titleMap = {
        'overview': 'Overview',
        'user-intelligence': 'User Intelligence',
        'mfa-coverage': 'MFA Coverage',
        'conditional-access': 'Conditional Access',
        'admin-roles': 'Admin Roles',
        'risky-users': 'Risky Users',
        'sign-in-activity': 'Sign-in Activity',
        'exchange': 'Exchange',
        'onedrive': 'OneDrive',
        'sharepoint': 'SharePoint',
        'teams': 'Teams',
        'utilization': 'License Utilization',
        'optimizer': 'License Optimizer',
        'parking-report': 'Parking Report',
        'defender-office365': 'Defender for Office 365',
        'cloud-app-discovery': 'Cloud App Discovery',
        'dlp-violations': 'DLP Violations',
        'sensitivity-labels': 'Sensitivity Labels',
        'guest-users': 'Guest Users',
        'auth-methods': 'Auth Methods',
        'named-locations': 'Named Locations',
        'intune-devices': 'Intune Devices',
        'compliance-policies': 'Compliance Policies',
        'mobile-apps': 'Mobile Apps',
        'api-keys': 'API Keys',
        'email-reports': 'Email Reports',
        'tenants': 'Tenants'
    };
    
    return titleMap[pageName] || pageName.charAt(0).toUpperCase() + pageName.slice(1).replace('-', ' ');
}

// Navigation initialization
function initNavigation() {
    // Set up click handlers for all nav items
    document.querySelectorAll('.nav-item a').forEach(function(link) {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            const href = this.getAttribute('href');
            window.location.hash = href.substring(2); // Remove #/
        });
    });
}
