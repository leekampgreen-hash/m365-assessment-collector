// Page data for dummy pages
const pageData = {
    'overview': {
        title: 'Overview',
        description: 'Get a comprehensive overview of your M365 tenant health, security posture, and user activity.'
    },
    'user-intelligence': {
        title: 'User Intelligence',
        description: 'Analyze user behavior patterns, collaboration metrics, and productivity insights.'
    },
    'mfa-coverage': {
        title: 'MFA Coverage',
        description: 'Monitor Multi-Factor Authentication adoption across all users and identify gaps.'
    },
    'conditional-access': {
        title: 'Conditional Access',
        description: 'Review and manage Conditional Access policies and their enforcement status.'
    },
    'admin-roles': {
        title: 'Admin Roles',
        description: 'View administrator roles, permissions, and privileged account activity.'
    },
    'risky-users': {
        title: 'Risky Users',
        description: 'Identify users with risky sign-in behavior or compromised accounts.'
    },
    'sign-in-activity': {
        title: 'Sign-in Activity',
        description: 'Audit sign-in logs, failed attempts, and authentication patterns.'
    },
    'exchange': {
        title: 'Exchange',
        description: 'Manage Exchange Online mailboxes, retention policies, and mailbox permissions.'
    },
    'onedrive': {
        title: 'OneDrive',
        description: 'Monitor OneDrive storage usage, sharing settings, and file access.'
    },
    'sharepoint': {
        title: 'SharePoint',
        description: 'Administer SharePoint sites, permissions, and content management.'
    },
    'teams': {
        title: 'Teams',
        description: 'Review Microsoft Teams usage, meetings, chats, and team governance.'
    },
    'utilization': {
        title: 'License Utilization',
        description: 'Track license allocation, utilization rates, and assignment details.'
    },
    'optimizer': {
        title: 'License Optimizer',
        description: 'Optimize license assignments and identify cost-saving opportunities.'
    },
    'parking-report': {
        title: 'Parking Report',
        description: 'Generate reports on parked or unused licenses and resources.'
    },
    'defender-office365': {
        title: 'Defender for Office 365',
        description: 'Monitor Defender for Office 365 threats, policies, and protection status.'
    },
    'cloud-app-discovery': {
        title: 'Cloud App Discovery',
        description: 'Discover shadow IT apps connected to your M365 environment.'
    },
    'dlp-violations': {
        title: 'DLP Violations',
        description: 'Review Data Loss Prevention policy violations and sensitive data exposure.'
    },
    'sensitivity-labels': {
        title: 'Sensitivity Labels',
        description: 'Manage information protection labels and classified content.'
    },
    'guest-users': {
        title: 'Guest Users',
        description: 'Audit external guest users, their access levels, and invitation status.'
    },
    'auth-methods': {
        title: 'Auth Methods',
        description: 'Review authentication methods registered by users and security defaults.'
    },
    'named-locations': {
        title: 'Named Locations',
        description: 'Define and manage trusted IP ranges and location-based policies.'
    },
    'intune-devices': {
        title: 'Intune Devices',
        description: 'Monitor enrolled devices, compliance status, and managed applications.'
    },
    'compliance-policies': {
        title: 'Compliance Policies',
        description: 'Create and manage compliance policies across your organization.'
    },
    'mobile-apps': {
        title: 'Mobile Apps',
        description: 'Control mobile application access and mobile device management.'
    },
    'api-keys': {
        title: 'API Keys',
        description: 'Generate and manage API keys for external integrations.'
    },
    'email-reports': {
        title: 'Email Reports',
        description: 'Configure automated email reports and delivery schedules.'
    },
    'tenants': {
        title: 'Tenants',
        description: 'Manage multiple M365 tenants and cross-tenant configurations.'
    }
};

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    initSidebarCollapsible();
    initNavbarCollapse();
    handleInitialRoute();
});

// Handle hash changes
window.addEventListener('hashchange', function() {
    handleRouteChange();
});

// Toggle sidebar (for responsive behavior)
function toggleSidebar() {
    const sidebar = document.querySelector('.navbar-vertical');
    if (!sidebar) return;
    
    // For small screens, toggle collapse
    if (window.innerWidth < 992) {
        const menu = document.getElementById('sidebar-menu');
        menu.classList.toggle('show');
    } else {
        // For large screens, you could implement collapsible logic
        const navbarBtn = document.querySelector('[data-bs-target="#pageWrapper"]');
        if (navbarBtn) {
            navbarBtn.dispatchEvent(new Event('click'));
        }
    }
}

// Initialize sidebar collapsible sections
function initSidebarCollapsible() {
    const collapseElements = document.querySelectorAll('[data-bs-toggle="collapse"]');
    
    collapseElements.forEach(function(element) {
        element.addEventListener('click', function() {
            const targetId = this.getAttribute('data-bs-target');
            const collapse = document.querySelector(targetId);
            
            // Close other open collapses in same parent section
            const siblings = collapse.parentElement.querySelectorAll('.collapse');
            siblings.forEach(function(sibling) {
                if (sibling !== collapse && sibling !== document.getElementById('workspace-submenu')) {
                    bs.Collapse.getInstance(sibling)?.hide();
                }
            });
        });
    });
}

// Initialize navbar collapse behavior
function initNavbarCollapse() {
    // Auto-expand workspace submenu on load
    const workspaceSubmenu = document.getElementById('workspace-submenu');
    if (workspaceSubmenu && !workspaceSubmenu.classList.contains('show')) {
        const bsCollapse = new bootstrap.Collapse(workspaceSubmenu, { show: true });
    }
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

// Load page based on route
function loadPage(hash) {
    const pageName = hash.replace('#/', '') || 'overview';
    
    // Update active menu item
    updateActiveMenuItem(pageName);
    
    // Load page content
    renderDummyPage(pageName);
    
    // Scroll to top
    window.scrollTo(0, 0);
}

// Update active menu item
function updateActiveMenuItem(pageName) {
    // Remove active class from all nav items
    document.querySelectorAll('.nav-link').forEach(function(link) {
        link.classList.remove('active');
    });
    
    // Add active class to current page
    const currentPageItem = document.querySelector(`[href="#/${pageName}"]`);
    if (currentPageItem) {
        currentPageItem.classList.add('active');
        
        // Expand parent collapse if needed
        expandParentCollapse(currentPageItem);
    }
}

// Expand parent collapse when clicking a menu item
function expandParentCollapse(element) {
    let parent = element.closest('.collapse');
    while (parent) {
        parent.classList.add('show');
        parent = parent.closest('.collapse');
    }
}

// Render dummy page content
function renderDummyPage(pageName) {
    const container = document.getElementById('contentContainer');
    if (!container) return;
    
    const page = pageData[pageName];
    const title = page ? page.title : pageName.charAt(0).toUpperCase() + pageName.slice(1).replace('-', ' ');
    const description = page ? page.description : 'No description available.';
    
    container.innerHTML = `
        <div class="page-card">
            <div class="placeholder-icon">🔨</div>
            <h1 class="page-title">${title}</h1>
            <p class="page-subtitle">This section is under construction</p>
            <p class="page-description">${description}</p>
        </div>
    `;
}
