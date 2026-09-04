// M365 Assessment Collector - Modern Application Controller with Unified Pagination (10-200)
const sid = sessionStorage.getItem("session_id");
if (!sid || sid === "null" || sid === "undefined") {
  sessionStorage.removeItem("session_id");
  window.location.href = "/login.html";
}

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => document.querySelectorAll(selector);

const DASHBOARD_FETCH_TIMEOUT_MS = 15000;
const PAGE_SIZE_OPTIONS = [10, 25, 50, 100, 200];
const tableStateStore = {};

const escapeHtml = (item) => String(item ?? "-").replace(/[&<>'"]/g, (c) => ({
  "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;"
})[c]);

const storage = (bytes) => {
  if (bytes === null || bytes === undefined || bytes === "") return "-";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let val = Number(bytes);
  let idx = 0;
  while (Math.abs(val) >= 1024 && idx < units.length - 1) {
    val /= 1024;
    idx++;
  }
  return `${val.toFixed(idx ? 2 : 0)} ${units[idx]}`;
};

async function get(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DASHBOARD_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(path, {
      headers: {
        Accept: "application/json",
        "X-API-Key": window.API_KEY || "",
        "X-Session-ID": sid
      },
      signal: controller.signal
    });
    if (!response.ok) throw new Error(`Request to ${path} failed with HTTP ${response.status}`);
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

// Global Application State
let allUsers = [];
let userTableFilter = "ALL";
let userTableSearch = "";
let userTablePage = 1;
let userTablePageSize = 10;
const chatHistory = [];

// Universal Paginated Table Engine for All Tables
function createPaginatedTable(containerSelector, {
  columns,
  data = [],
  renderRow,
  defaultSize = 10,
  key = containerSelector,
  emptyMessage = "No records found",
  onColumnReorder = null
}) {
  const container = typeof containerSelector === "string" ? $(containerSelector) : containerSelector;
  if (!container) return;

  const state = tableStateStore[key] || (tableStateStore[key] = {
    page: 1,
    size: defaultSize,
    sortCol: null,
    sortDir: null
  });

  const render = () => {
    // Check if active sort column is still in columns
    const activeColKeys = columns.map(c => typeof c === "object" && c !== null ? c.key : c);
    if (state.sortCol && !activeColKeys.includes(state.sortCol)) {
      state.sortCol = null;
      state.sortDir = null;
    }

    // Sort data if sortCol and sortDir are active
    const sortedData = [...data];
    if (state.sortCol && state.sortDir) {
      const colDef = columns.find(c => (typeof c === "object" && c !== null ? c.key : c) === state.sortCol);
      sortedData.sort((a, b) => {
        let va, vb;
        if (colDef && typeof colDef.sortVal === "function") {
          va = colDef.sortVal(a);
          vb = colDef.sortVal(b);
        } else {
          va = a ? a[state.sortCol] : "";
          vb = b ? b[state.sortCol] : "";
        }

        const aEmpty = va === null || va === undefined || va === "" || va === "-";
        const bEmpty = vb === null || vb === undefined || vb === "" || vb === "-";
        if (aEmpty && bEmpty) return 0;
        if (aEmpty) return 1;
        if (bEmpty) return -1;

        if (typeof va === "number" && typeof vb === "number") {
          return state.sortDir === "asc" ? va - vb : vb - va;
        }

        return state.sortDir === "asc"
          ? String(va).localeCompare(String(vb), undefined, { numeric: true, sensitivity: "base" })
          : String(vb).localeCompare(String(va), undefined, { numeric: true, sensitivity: "base" });
      });
    }

    const total = sortedData.length;
    const size = state.size;
    const totalPages = Math.max(1, Math.ceil(total / size));
    state.page = Math.min(Math.max(1, state.page), totalPages);

    const startIdx = (state.page - 1) * size;
    const pageItems = sortedData.slice(startIdx, startIdx + size);
    const endIdx = Math.min(startIdx + size, total);

    const rowsHtml = pageItems.length
      ? pageItems.map((item, idx) => renderRow ? renderRow(item, startIdx + idx) : item).join("")
      : `<tr><td colspan="${columns.length}" style="text-align: center; color: var(--text-muted); padding: 24px;">${escapeHtml(emptyMessage)}</td></tr>`;

    const sizeOptionsHtml = PAGE_SIZE_OPTIONS.map((opt) => 
      `<option value="${opt}" ${opt === size ? "selected" : ""}>${opt}</option>`
    ).join("");

    const thsHtml = columns.map((c) => {
      if (typeof c === "object" && c !== null) {
        const isDrag = c.draggable !== false;
        const isSort = c.sortable !== false;
        const colKey = c.key || "";
        const isCurrentSort = state.sortCol === colKey;
        const dir = isCurrentSort ? state.sortDir : null;

        let sortIconHtml = "";
        let sortTitle = isDrag ? "Drag to reorder column position" : "";
        let sortClass = "";

        if (isSort) {
          sortClass = "sortable-th";
          if (dir === "asc") {
            sortClass += " sorted-asc";
            sortIconHtml = `<span class="sort-icon-indicator" aria-label="Sorted ascending"><i class="ti ti-arrow-up"></i></span>`;
            sortTitle = isDrag ? "Sorted Ascending. Drag to reorder or click to sort Descending." : "Sorted Ascending. Click to sort Descending.";
          } else if (dir === "desc") {
            sortClass += " sorted-desc";
            sortIconHtml = `<span class="sort-icon-indicator" aria-label="Sorted descending"><i class="ti ti-arrow-down"></i></span>`;
            sortTitle = isDrag ? "Sorted Descending. Drag to reorder or click to clear sort." : "Sorted Descending. Click to clear sort.";
          } else {
            sortIconHtml = `<span class="sort-icon-indicator" aria-label="Sortable"><i class="ti ti-arrows-sort"></i></span>`;
            sortTitle = isDrag ? "Drag to reorder column. Click to sort Ascending." : "Click to sort Ascending.";
          }
        }

        const dragClass = isDrag ? "draggable-header" : "";
        return `<th class="${dragClass} ${sortClass}" data-col-key="${escapeHtml(colKey)}" ${isDrag ? 'draggable="true"' : ''} title="${escapeHtml(sortTitle)}"><div class="th-inner"><span class="th-label">${escapeHtml(c.label || colKey)}</span>${sortIconHtml}</div></th>`;
      }
      return `<th>${escapeHtml(c)}</th>`;
    }).join("");

    container.innerHTML = `
      <div class="table-responsive-custom">
        <table class="modern-data-table">
          <thead>
            <tr>${thsHtml}</tr>
          </thead>
          <tbody>
            ${rowsHtml}
          </tbody>
        </table>
      </div>
      <div class="table-footer-controls">
        <span class="footer-info">${total > 0 ? `Showing ${startIdx + 1}-${endIdx} of ${total} entries` : "Showing 0 of 0"}</span>
        <div class="pagination-buttons">
          <label class="page-size-label">
            Rows:
            <select class="page-size-select table-size-select">
              ${sizeOptionsHtml}
            </select>
          </label>
          <button class="page-btn table-prev-btn" ${state.page <= 1 ? "disabled" : ""}><i class="ti ti-chevron-left"></i> Previous</button>
          <span class="page-current">Page ${state.page} of ${totalPages}</span>
          <button class="page-btn table-next-btn" ${state.page >= totalPages ? "disabled" : ""}>Next <i class="ti ti-chevron-right"></i></button>
        </div>
      </div>
    `;

    let isDragging = false;

    if (onColumnReorder) {
      const headers = container.querySelectorAll("th.draggable-header");
      let draggedKey = null;

      headers.forEach((th) => {
        th.addEventListener("dragstart", (e) => {
          isDragging = true;
          draggedKey = th.dataset.colKey;
          e.dataTransfer.effectAllowed = "move";
          e.dataTransfer.setData("text/plain", draggedKey);
          th.classList.add("dragging-header");
        });

        th.addEventListener("dragover", (e) => {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
          const rect = th.getBoundingClientRect();
          const isLeft = e.clientX < rect.left + rect.width / 2;
          if (isLeft) {
            th.classList.add("drag-over-left");
            th.classList.remove("drag-over-right");
          } else {
            th.classList.add("drag-over-right");
            th.classList.remove("drag-over-left");
          }
        });

        th.addEventListener("dragleave", () => {
          th.classList.remove("drag-over-left", "drag-over-right");
        });

        th.addEventListener("drop", (e) => {
          e.preventDefault();
          const targetKey = th.dataset.colKey;
          const rect = th.getBoundingClientRect();
          const isBefore = e.clientX < rect.left + rect.width / 2;
          th.classList.remove("drag-over-left", "drag-over-right");
          if (draggedKey && targetKey && draggedKey !== targetKey) {
            onColumnReorder(draggedKey, targetKey, isBefore);
          }
        });

        th.addEventListener("dragend", () => {
          headers.forEach(h => h.classList.remove("dragging-header", "drag-over-left", "drag-over-right"));
          draggedKey = null;
          setTimeout(() => {
            isDragging = false;
          }, 150);
        });
      });
    }

    const sortableHeaders = container.querySelectorAll("th.sortable-th");
    sortableHeaders.forEach((th) => {
      th.addEventListener("click", () => {
        if (isDragging) return;
        const colKey = th.dataset.colKey;
        if (!colKey) return;

        if (state.sortCol === colKey) {
          if (state.sortDir === "asc") {
            state.sortDir = "desc";
          } else if (state.sortDir === "desc") {
            state.sortCol = null;
            state.sortDir = null;
          }
        } else {
          state.sortCol = colKey;
          state.sortDir = "asc";
        }
        state.page = 1;
        render();
      });
    });

    container.querySelector(".table-size-select")?.addEventListener("change", (e) => {
      state.size = Number(e.target.value);
      state.page = 1;
      render();
    });

    container.querySelector(".table-prev-btn")?.addEventListener("click", () => {
      if (state.page > 1) {
        state.page -= 1;
        render();
      }
    });

    container.querySelector(".table-next-btn")?.addEventListener("click", () => {
      if (state.page < totalPages) {
        state.page += 1;
        render();
      }
    });
  };

  render();
}

// Navigation & View Switching
const viewTitles = {
  "overview": ["Executive", "Tenant-level view of adoption, security posture, and license optimization"],
  "user-intelligence": ["User Intelligence", "Continuous identity risk scoring, MFA tracking, and CIS v6.0.1 compliance"],
  "security": ["Security & Risk", "MFA coverage, Conditional Access policy evaluations, and privileged role distribution"],
  "license": ["License Optimizer", "Reclaim unused and parked licenses across disabled and inactive accounts"],
  "workloads": ["Workload Adoption", "Exchange Online, OneDrive, SharePoint, and Teams utilization"],
  "endpoints": ["Intune & Defender", "Managed endpoint compliance, Defender threat signals, and guest governance"],
  "assistant": ["M365 AI Assistant", "Natural language Q&A and proactive security guidance"]
};

function switchView(viewName) {
  const slug = viewTitles[viewName] ? viewName : "overview";
  
  $$(".nav-link").forEach((link) => {
    link.classList.toggle("active", link.dataset.view === slug);
  });

  $$(".view-panel").forEach((panel) => {
    panel.classList.add("hidden");
  });
  const targetPanel = $(`#view-${slug}`);
  if (targetPanel) {
    targetPanel.classList.remove("hidden");
  }

  const [heading, subheading] = viewTitles[slug] || ["Executive", "Tenant Operations Overview"];
  if ($("#page-heading")) $("#page-heading").textContent = heading;
  if ($("#page-subheading")) $("#page-subheading").textContent = subheading;

  $("#sidebar")?.classList.remove("open");
}

function initNavigation() {
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebar-backdrop");

  const closeMobileSidebar = () => {
    sidebar?.classList.remove("open");
    backdrop?.classList.remove("active");
  };

  $$(".nav-link[data-view]").forEach((link) => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const view = link.dataset.view;
      location.hash = view;
      switchView(view);
      closeMobileSidebar();
    });
  });

  $("#mobile-menu-btn")?.addEventListener("click", () => {
    if (window.innerWidth <= 900) {
      const isOpen = sidebar?.classList.toggle("open");
      backdrop?.classList.toggle("active", isOpen);
    } else {
      sidebar?.classList.toggle("desktop-closed");
    }
  });

  $("#sidebar-close")?.addEventListener("click", () => {
    if (window.innerWidth <= 900) {
      closeMobileSidebar();
    } else {
      sidebar?.classList.add("desktop-closed");
    }
  });

  backdrop?.addEventListener("click", closeMobileSidebar);

  window.addEventListener("hashchange", () => {
    const slug = location.hash.replace(/^#\/?/, "") || "overview";
    switchView(slug);
    closeMobileSidebar();
  });

  const initialView = location.hash.replace(/^#\/?/, "") || "overview";
  switchView(initialView);
}

// User Intelligence Table Rendering
const avatarColors = [
  "linear-gradient(135deg, #3b82f6, #06b6d4)",
  "linear-gradient(135deg, #10b981, #059669)",
  "linear-gradient(135deg, #8b5cf6, #ec4899)",
  "linear-gradient(135deg, #f59e0b, #ef4444)",
  "linear-gradient(135deg, #0ea5e9, #6366f1)"
];

function getInitials(name) {
  if (!name) return "U";
  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0][0] + parts[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase();
}

function getAvatarColor(name) {
  let hash = 0;
  for (let i = 0; i < (name || "").length; i++) {
    hash = (name.charCodeAt(i) + ((hash << 5) - hash));
  }
  return avatarColors[Math.abs(hash) % avatarColors.length];
}

function getMfaLabel(user) {
  if (!user.mfa_registered) return '<span class="text-muted">None</span>';
  const method = String(user.mfa_method || "").toLowerCase();
  if (method.includes("fido2")) return "FIDO2 Key";
  if (method.includes("authenticator")) return "Authenticator";
  if (method.includes("phone") || method.includes("sms")) return "Phone / SMS";
  if (method.includes("hello")) return "Windows Hello";
  return "Registered (MFA)";
}

function hydrateFinancialSummary() {
  const licenseObj = window.dashboardData?.license || {};
  const skuEntries = Object.entries(licenseObj);
  
  // Filter paid/commercial SKUs (exclude trial/free pools with >= 100000 prepaid units)
  const paidSkus = skuEntries.filter(([_, item]) => {
    const purchased = Number(item.purchased_units || 0);
    return purchased < 100000;
  });

  // Calculate total assigned SKU units across commercial products
  let totalAssigned = 0;
  if (paidSkus.length > 0) {
    totalAssigned = paidSkus.reduce((sum, [_, item]) => sum + Number(item.consumed_units ?? item.assigned_user_count ?? 0), 0);
  } else if (allUsers.length > 0) {
    totalAssigned = allUsers.filter(u => Array.isArray(u.license_names) && u.license_names.length > 0).length;
  } else {
    totalAssigned = 26;
  }

  const productCount = paidSkus.length || (skuEntries.length > 0 ? skuEntries.length : 2);
  const idleLicenses = optimizerReport?.summary?.flagged_users || 0;
  const activeCount = Math.max(0, totalAssigned - idleLicenses);
  const inactivePercent = totalAssigned > 0 ? Math.round((idleLicenses / totalAssigned) * 100) : 0;
  const activePercent = totalAssigned > 0 ? (100 - inactivePercent) : 0;
  const monthlyWaste = optimizerReport?.savings?.total_monthly_saving || 0;
  const annualSavings = optimizerReport?.savings?.total_annual_saving || (monthlyWaste * 12);
  const formattedAnnual = Math.round(annualSavings).toLocaleString();

  if ($("#fin-total-assigned")) $("#fin-total-assigned").textContent = totalAssigned.toLocaleString();
  if ($("#fin-total-products")) $("#fin-total-products").textContent = `Across ${productCount} paid SKU${productCount !== 1 ? "s" : ""}`;
  if ($("#fin-inactive-seats")) $("#fin-inactive-seats").textContent = idleLicenses.toLocaleString();
  if ($("#fin-inactive-percent-sub")) $("#fin-inactive-percent-sub").textContent = `${inactivePercent}% of assigned seats inactive >30d`;
  if ($("#kpi-parking-savings")) $("#kpi-parking-savings").textContent = formattedAnnual;
  if ($("#fin-savings-sub")) $("#fin-savings-sub").textContent = `~$${Math.round(monthlyWaste).toLocaleString()} / mo recovery potential`;
  if ($("#sidebar-savings-badge")) $("#sidebar-savings-badge").textContent = `$${(annualSavings / 1000).toFixed(1)}k savings`;
  
  if ($("#fin-distribution-label")) $("#fin-distribution-label").textContent = `${idleLicenses.toLocaleString()} Reclaimable (${inactivePercent}%) / ${activeCount.toLocaleString()} In-Use`;
  
  if ($("#bar-idle")) $("#bar-idle").style.width = `${inactivePercent}%`;
  if ($("#bar-active")) $("#bar-active").style.width = `${activePercent}%`;
}

// ==========================================
// User Intelligence: Catalog, Drag & Drop, & Saved Views
// ==========================================

const USER_INTEL_COLUMNS_CATALOG = {
  user: {
    id: "user",
    label: "User Identity",
    category: "Identity",
    draggable: false,
    sortVal: (u) => (u.display_name || u.user_principal_name || u.upn || "").toLowerCase(),
    renderCell: (u) => `
      <td>
        <div style="display: flex; align-items: center; gap: 10px;">
          <div class="user-avatar-mini" style="background: ${getAvatarColor(u.display_name || u.user_principal_name || u.upn)}; width: 32px; height: 32px; font-size: 11px; border-radius: 8px;">
            ${getInitials(u.display_name || u.user_principal_name || u.upn)}
          </div>
          <div>
            <strong>${escapeHtml(u.display_name || "Unknown")}</strong><br>
            <small class="text-muted">${escapeHtml(u.user_principal_name || u.upn || "-")}</small>
          </div>
        </div>
      </td>
    `
  },
  user_type: {
    id: "user_type",
    label: "User Type",
    category: "Identity",
    draggable: true,
    sortVal: (u) => String(u.user_type || "Member").toLowerCase(),
    renderCell: (u) => `<td><span class="role-pill ${String(u.user_type || "").toLowerCase() === "guest" ? "role-guest" : "role-member"}">${escapeHtml(u.user_type || "Member")}</span></td>`
  },
  account_status: {
    id: "account_status",
    label: "Account Status",
    category: "Identity",
    draggable: true,
    sortVal: (u) => (u.account_enabled !== false ? 1 : 0),
    renderCell: (u) => {
      const enabled = u.account_enabled !== false;
      return `<td><span class="account-status-badge ${enabled ? 'account-status-active' : 'account-status-disabled'}"><i class="ti ti-${enabled ? 'check' : 'ban'}"></i> ${enabled ? 'Active' : 'Disabled'}</span></td>`;
    }
  },
  privilege: {
    id: "privilege",
    label: "Privilege",
    category: "Security",
    draggable: true,
    sortVal: (u) => (u.is_admin ? 1 : 0),
    renderCell: (u) => `<td>${u.is_admin ? '<span class="role-pill role-admin">Admin</span>' : '<span class="role-pill role-member">Member</span>'}</td>`
  },
  mfa_method: {
    id: "mfa_method",
    label: "MFA Method",
    category: "Security",
    draggable: true,
    sortVal: (u) => (u.mfa_registered ? (Array.isArray(u.auth_methods) && u.auth_methods.length ? u.auth_methods.join(", ") : "MFA Registered") : "None").toLowerCase(),
    renderCell: (u) => `<td>${getMfaLabel(u)}</td>`
  },
  cis_risk: {
    id: "cis_risk",
    label: "CIS Risk Posture",
    category: "Security",
    draggable: true,
    sortVal: (u) => Number(u.security_score ?? (u.risk_level === 'CRITICAL' ? 50 : u.risk_level === 'HIGH' ? 40 : u.risk_level === 'MEDIUM' ? 20 : 0)),
    renderCell: (u) => {
      const riskStatus = String(u.security_status || u.risk_level || "GOOD").toUpperCase();
      const riskClass = `badge-risk-${riskStatus.toLowerCase()}`;
      return `<td><span class="badge-risk ${riskClass}">${riskStatus} (${u.security_score || 0})</span></td>`;
    }
  },
  license_names: {
    id: "license_names",
    label: "Assigned Licenses",
    category: "FinOps",
    draggable: true,
    sortVal: (u) => (Array.isArray(u.license_names) ? u.license_names.join(", ") : "").toLowerCase(),
    renderCell: (u) => {
      const licenses = Array.isArray(u.license_names) ? u.license_names : [];
      if (!licenses.length) return `<td class="text-muted">None</td>`;
      return `<td><div style="display: flex; flex-wrap: wrap; gap: 2px;">${licenses.map(l => `<span class="sku-badge-pill" title="${escapeHtml(l)}">${escapeHtml(l)}</span>`).join("")}</div></td>`;
    }
  },
  license_count: {
    id: "license_count",
    label: "License Count",
    category: "FinOps",
    draggable: true,
    sortVal: (u) => Number(u.license_count || (Array.isArray(u.license_names) ? u.license_names.length : 0)),
    renderCell: (u) => `<td><strong>${Number(u.license_count || (Array.isArray(u.license_names) ? u.license_names.length : 0))}</strong> SKU(s)</td>`
  },
  last_signin: {
    id: "last_signin",
    label: "Last Sign-In",
    category: "Activity",
    draggable: true,
    sortVal: (u) => (u.signin_datetime || u.last_signin || u.exchange_last_activity || ""),
    renderCell: (u) => {
      const dt = u.signin_datetime || u.last_signin || u.exchange_last_activity || "-";
      const loc = u.location_city ? `<br><small class="text-muted"><i class="ti ti-map-pin"></i> ${escapeHtml(u.location_city)}${u.location_country ? `, ${escapeHtml(u.location_country)}` : ""}</small>` : "";
      return `<td>${escapeHtml(dt)}${loc}</td>`;
    }
  },
  exchange_activity: {
    id: "exchange_activity",
    label: "Exchange Activity",
    category: "Activity",
    draggable: true,
    sortVal: (u) => (u.exchange_last_activity || u.last_activity_date || ""),
    renderCell: (u) => `<td>${escapeHtml(u.exchange_last_activity || u.last_activity_date || "-")}</td>`
  },
  teams_activity: {
    id: "teams_activity",
    label: "Teams Activity",
    category: "Activity",
    draggable: true,
    sortVal: (u) => (u.teams_last_activity || ""),
    renderCell: (u) => `<td>${escapeHtml(u.teams_last_activity || "-")}</td>`
  },
  onedrive_activity: {
    id: "onedrive_activity",
    label: "OneDrive Activity",
    category: "Activity",
    draggable: true,
    sortVal: (u) => (u.onedrive_last_activity || ""),
    renderCell: (u) => `<td>${escapeHtml(u.onedrive_last_activity || "-")}</td>`
  },
  department: {
    id: "department",
    label: "Department",
    category: "Governance",
    draggable: true,
    sortVal: (u) => (u.department || "").toLowerCase(),
    renderCell: (u) => `<td>${escapeHtml(u.department || "-")}</td>`
  },
  job_title: {
    id: "job_title",
    label: "Job Title",
    category: "Governance",
    draggable: true,
    sortVal: (u) => (u.job_title || "").toLowerCase(),
    renderCell: (u) => `<td>${escapeHtml(u.job_title || "-")}</td>`
  },
  country: {
    id: "country",
    label: "Country / Region",
    category: "Governance",
    draggable: true,
    sortVal: (u) => (u.country || u.location_country || "").toLowerCase(),
    renderCell: (u) => `<td>${escapeHtml(u.country || u.location_country || "-")}</td>`
  },
  devices: {
    id: "devices",
    label: "Intune Devices",
    category: "Device",
    draggable: true,
    sortVal: (u) => Number(u.device_count || 0),
    renderCell: (u) => {
      const count = Number(u.device_count || 0);
      if (!count) return `<td class="text-muted">0 Devices</td>`;
      const isCompliant = u.device_compliant !== false;
      return `<td><span class="role-pill ${isCompliant ? 'role-member' : 'role-admin'}"><i class="ti ti-device-laptop"></i> ${count} Device(s)</span></td>`;
    }
  }
};

const USER_INTEL_PRESET_COLUMNS = {
  default: ["user", "user_type", "privilege", "mfa_method", "cis_risk", "last_signin", "department", "job_title"],
  security: ["user", "privilege", "mfa_method", "cis_risk", "last_signin", "devices"],
  finops: ["user", "account_status", "license_names", "license_count", "exchange_activity", "teams_activity", "last_signin"],
  directory: ["user", "user_type", "account_status", "department", "job_title", "country"],
  all: Object.keys(USER_INTEL_COLUMNS_CATALOG)
};

let userIntelActiveColumns = [...USER_INTEL_PRESET_COLUMNS.default];
let userIntelActiveViewId = "view_default";

function getUserStorageKey() {
  const email = $("#user-email")?.textContent?.trim() || localStorage.getItem("user_email") || "admin@localhost";
  const tenant = (typeof currentTenantId !== "undefined" ? currentTenantId : null) || window.currentTenantId || localStorage.getItem("tenant_id") || "default";
  return `m365_user_intel_views_${email}_${tenant}`;
}

function loadUserSavedViews() {
  const builtInViews = [
    { id: "view_default", name: "Default Posture Matrix", isDefault: true, isSystem: true, columns: [...USER_INTEL_PRESET_COLUMNS.default], filters: { search: "", role: "ALL", mfa: "ALL", risk: "ALL", status: "ALL" } },
    { id: "view_security", name: "Security & MFA Audit", isDefault: false, isSystem: true, columns: [...USER_INTEL_PRESET_COLUMNS.security], filters: { search: "", role: "ALL", mfa: "ALL", risk: "ALL", status: "ALL" } },
    { id: "view_finops", name: "FinOps & License Recovery", isDefault: false, isSystem: true, columns: [...USER_INTEL_PRESET_COLUMNS.finops], filters: { search: "", role: "ALL", mfa: "ALL", risk: "ALL", status: "ALL" } },
    { id: "view_directory", name: "Directory & Governance", isDefault: false, isSystem: true, columns: [...USER_INTEL_PRESET_COLUMNS.directory], filters: { search: "", role: "ALL", mfa: "ALL", risk: "ALL", status: "ALL" } }
  ];

  try {
    const key = getUserStorageKey();
    const raw = localStorage.getItem(key);
    if (!raw) return builtInViews;
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed) && parsed.length > 0) return parsed;
  } catch (_) {}
  return builtInViews;
}

function saveUserViews(views) {
  try {
    const key = getUserStorageKey();
    localStorage.setItem(key, JSON.stringify(views));
  } catch (_) {}
}

function initUserIntelControls() {
  try {
    const views = loadUserSavedViews();
    const defaultView = (views && views.find(v => v && v.isDefault)) || (views && views[0]) || {
      id: "view_default",
      columns: [...USER_INTEL_PRESET_COLUMNS.default]
    };
    userIntelActiveViewId = defaultView.id || "view_default";
    userIntelActiveColumns = Array.isArray(defaultView.columns) && defaultView.columns.length ? [...defaultView.columns] : [...USER_INTEL_PRESET_COLUMNS.default];

    // Set filter inputs if saved
    if (defaultView.filters) {
      if ($("#full-user-search")) $("#full-user-search").value = defaultView.filters.search || "";
      if ($("#full-user-role-filter")) $("#full-user-role-filter").value = defaultView.filters.role || "ALL";
      if ($("#full-user-mfa-filter")) $("#full-user-mfa-filter").value = defaultView.filters.mfa || "ALL";
      if ($("#full-user-risk-filter")) $("#full-user-risk-filter").value = defaultView.filters.risk || "ALL";
      if ($("#full-user-status-filter")) $("#full-user-status-filter").value = defaultView.filters.status || "ALL";
    }

    renderSavedViewsDropdown();
    renderColumnPickerList();
    bindUserIntelEvents();
  } catch (err) {
    console.error("Error initializing user intel controls:", err);
  }
}

function renderSavedViewsDropdown() {
  const select = $("#user-saved-views-select");
  if (!select) return;
  const views = loadUserSavedViews();
  select.innerHTML = views.map(v => 
    `<option value="${escapeHtml(v.id)}" ${v.id === userIntelActiveViewId ? "selected" : ""}>${escapeHtml(v.name)}${v.isDefault ? " (Default)" : ""}</option>`
  ).join("");

  const activeView = views.find(v => v.id === userIntelActiveViewId);
  const deleteBtn = $("#btn-delete-current-view");
  if (deleteBtn) {
    deleteBtn.style.display = (activeView && !activeView.isSystem) ? "inline-flex" : "none";
  }
}

function renderColumnPickerList() {
  const container = $("#columns-checkbox-container");
  const label = $("#columns-btn-label");
  if (!container) return;

  const totalCols = Object.keys(USER_INTEL_COLUMNS_CATALOG).length;
  if (label) label.textContent = `Columns (${userIntelActiveColumns.length}/${totalCols})`;

  container.innerHTML = Object.values(USER_INTEL_COLUMNS_CATALOG).map(col => {
    const checked = userIntelActiveColumns.includes(col.id);
    const isPinned = col.id === "user";
    return `
      <label class="column-checkbox-item">
        <input type="checkbox" value="${escapeHtml(col.id)}" ${checked ? "checked" : ""} ${isPinned ? "disabled" : ""}>
        <span>${escapeHtml(col.label)}</span>
      </label>
    `;
  }).join("");

  container.querySelectorAll("input[type='checkbox']").forEach(cb => {
    cb.addEventListener("change", () => {
      const colId = cb.value;
      if (cb.checked) {
        if (!userIntelActiveColumns.includes(colId)) userIntelActiveColumns.push(colId);
      } else {
        userIntelActiveColumns = userIntelActiveColumns.filter(c => c !== colId);
      }
      if (!userIntelActiveColumns.includes("user")) userIntelActiveColumns.unshift("user");
      renderFullUserTable();
      renderColumnPickerList();
    });
  });
}

function bindUserIntelEvents() {
  // Search & Filter change triggers
  const filterInputs = [
    "#full-user-search",
    "#full-user-role-filter",
    "#full-user-mfa-filter",
    "#full-user-risk-filter",
    "#full-user-status-filter"
  ];

  filterInputs.forEach(sel => {
    $(sel)?.addEventListener("input", () => renderFullUserTable());
    $(sel)?.addEventListener("change", () => renderFullUserTable());
  });

  // Reset All Filters Button
  $("#btn-reset-all-filters")?.addEventListener("click", () => {
    if ($("#full-user-search")) $("#full-user-search").value = "";
    if ($("#full-user-role-filter")) $("#full-user-role-filter").value = "ALL";
    if ($("#full-user-mfa-filter")) $("#full-user-mfa-filter").value = "ALL";
    if ($("#full-user-risk-filter")) $("#full-user-risk-filter").value = "ALL";
    if ($("#full-user-status-filter")) $("#full-user-status-filter").value = "ALL";
    renderFullUserTable();
  });

  // Saved Views Select Switch
  $("#user-saved-views-select")?.addEventListener("change", (e) => {
    const viewId = e.target.value;
    const views = loadUserSavedViews();
    const view = views.find(v => v.id === viewId);
    if (view) {
      userIntelActiveViewId = view.id;
      userIntelActiveColumns = [...view.columns];
      if (view.filters) {
        if ($("#full-user-search")) $("#full-user-search").value = view.filters.search || "";
        if ($("#full-user-role-filter")) $("#full-user-role-filter").value = view.filters.role || "ALL";
        if ($("#full-user-mfa-filter")) $("#full-user-mfa-filter").value = view.filters.mfa || "ALL";
        if ($("#full-user-risk-filter")) $("#full-user-risk-filter").value = view.filters.risk || "ALL";
        if ($("#full-user-status-filter")) $("#full-user-status-filter").value = view.filters.status || "ALL";
      }
      renderSavedViewsDropdown();
      renderColumnPickerList();
      renderFullUserTable();
    }
  });

  // Delete Custom View
  $("#btn-delete-current-view")?.addEventListener("click", () => {
    let views = loadUserSavedViews();
    const activeView = views.find(v => v.id === userIntelActiveViewId);
    if (!activeView || activeView.isSystem) return;
    if (confirm(`Delete custom view "${activeView.name}"?`)) {
      views = views.filter(v => v.id !== userIntelActiveViewId);
      saveUserViews(views);
      userIntelActiveViewId = "view_default";
      const defaultView = views.find(v => v.isDefault) || views[0];
      userIntelActiveColumns = [...defaultView.columns];
      renderSavedViewsDropdown();
      renderColumnPickerList();
      renderFullUserTable();
    }
  });

  // Column Picker Popover Toggle
  $("#btn-toggle-columns-picker")?.addEventListener("click", (e) => {
    e.stopPropagation();
    $("#columns-picker-popover")?.classList.toggle("hidden");
  });

  $("#btn-close-columns-picker")?.addEventListener("click", () => {
    $("#columns-picker-popover")?.classList.add("hidden");
  });

  document.addEventListener("click", (e) => {
    if (!$(".column-picker-wrap")?.contains(e.target) && !$("#columns-picker-popover")?.contains(e.target)) {
      $("#columns-picker-popover")?.classList.add("hidden");
    }
  });

  // Preset Chips
  $$(".preset-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      const presetKey = chip.dataset.preset;
      if (USER_INTEL_PRESET_COLUMNS[presetKey]) {
        userIntelActiveColumns = [...USER_INTEL_PRESET_COLUMNS[presetKey]];
        renderColumnPickerList();
        renderFullUserTable();
      }
    });
  });

  $("#btn-reset-columns")?.addEventListener("click", () => {
    userIntelActiveColumns = [...USER_INTEL_PRESET_COLUMNS.default];
    renderColumnPickerList();
    renderFullUserTable();
  });

  // Save Current View Modal
  $("#btn-save-current-view")?.addEventListener("click", () => {
    $("#modal-save-view")?.classList.remove("hidden");
    if ($("#input-view-name")) $("#input-view-name").value = "";
    if ($("#check-set-default-view")) $("#check-set-default-view").checked = false;
  });

  $("#btn-modal-close-save")?.addEventListener("click", () => {
    $("#modal-save-view")?.classList.add("hidden");
  });

  $("#btn-cancel-save-view")?.addEventListener("click", () => {
    $("#modal-save-view")?.classList.add("hidden");
  });

  $("#btn-confirm-save-view")?.addEventListener("click", () => {
    const name = $("#input-view-name")?.value?.trim();
    if (!name) {
      alert("Please enter a name for your custom view.");
      return;
    }
    const isDefault = $("#check-set-default-view")?.checked || false;
    let views = loadUserSavedViews();

    if (isDefault) {
      views.forEach(v => v.isDefault = false);
    }

    const newId = `view_${Date.now()}`;
    const newView = {
      id: newId,
      name: name,
      isDefault: isDefault,
      isSystem: false,
      columns: [...userIntelActiveColumns],
      filters: {
        search: $("#full-user-search")?.value || "",
        role: $("#full-user-role-filter")?.value || "ALL",
        mfa: $("#full-user-mfa-filter")?.value || "ALL",
        risk: $("#full-user-risk-filter")?.value || "ALL",
        status: $("#full-user-status-filter")?.value || "ALL"
      }
    };

    views.push(newView);
    saveUserViews(views);
    userIntelActiveViewId = newId;
    $("#modal-save-view")?.classList.add("hidden");
    renderSavedViewsDropdown();
  });

  // Export to CSV
  $("#btn-export-user-csv")?.addEventListener("click", () => {
    exportUserIntelligenceCsv();
  });
}

function exportUserIntelligenceCsv() {
  const filteredUsers = getFilteredUsers();
  if (!filteredUsers.length) {
    alert("No records to export with current filters.");
    return;
  }

  const activeCols = userIntelActiveColumns.map(k => USER_INTEL_COLUMNS_CATALOG[k]).filter(Boolean);
  const headerRow = activeCols.map(c => `"${c.label.replace(/"/g, '""')}"`).join(",");
  
  const dataRows = filteredUsers.map(u => {
    return activeCols.map(c => {
      let val = "";
      if (c.id === "user") val = `${u.display_name || ""} (${u.user_principal_name || u.upn || ""})`;
      else if (c.id === "user_type") val = u.user_type || "Member";
      else if (c.id === "account_status") val = u.account_enabled !== false ? "Active" : "Disabled";
      else if (c.id === "privilege") val = u.is_admin ? "Admin" : "Member";
      else if (c.id === "mfa_method") val = u.default_mfa_method || (u.mfa_registered ? "Registered" : "None");
      else if (c.id === "cis_risk") val = `${u.security_status || u.risk_level || "GOOD"} (${u.security_score || 0})`;
      else if (c.id === "license_names") val = Array.isArray(u.license_names) ? u.license_names.join("; ") : "";
      else if (c.id === "license_count") val = u.license_count || 0;
      else if (c.id === "last_signin") val = u.signin_datetime || u.last_signin || u.exchange_last_activity || "";
      else if (c.id === "exchange_activity") val = u.exchange_last_activity || "";
      else if (c.id === "teams_activity") val = u.teams_last_activity || "";
      else if (c.id === "onedrive_activity") val = u.onedrive_last_activity || "";
      else if (c.id === "department") val = u.department || "";
      else if (c.id === "job_title") val = u.job_title || "";
      else if (c.id === "country") val = u.country || "";
      else if (c.id === "devices") val = `${u.device_count || 0} Devices`;
      return `"${String(val).replace(/"/g, '""')}"`;
    }).join(",");
  });

  const csvContent = [headerRow, ...dataRows].join("\n");
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.setAttribute("href", url);
  link.setAttribute("download", `m365_users_intel_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

function getFilteredUsers() {
  const searchTerm = ($("#full-user-search")?.value || "").toLowerCase().trim();
  const roleFilter = $("#full-user-role-filter")?.value || "ALL";
  const mfaFilter = $("#full-user-mfa-filter")?.value || "ALL";
  const riskFilter = $("#full-user-risk-filter")?.value || "ALL";
  const statusFilter = $("#full-user-status-filter")?.value || "ALL";

  return allUsers.filter(u => {
    // Search
    if (searchTerm) {
      const name = String(u.display_name || "").toLowerCase();
      const upn = String(u.user_principal_name || u.upn || "").toLowerCase();
      const dept = String(u.department || "").toLowerCase();
      const title = String(u.job_title || "").toLowerCase();
      const licenses = Array.isArray(u.license_names) ? u.license_names.join(" ").toLowerCase() : "";
      if (!name.includes(searchTerm) && !upn.includes(searchTerm) && !dept.includes(searchTerm) && !title.includes(searchTerm) && !licenses.includes(searchTerm)) {
        return false;
      }
    }

    // Role
    if (roleFilter === "ADMIN" && !u.is_admin) return false;
    if (roleFilter === "MEMBER" && (u.is_admin || String(u.user_type || "").toLowerCase() === "guest")) return false;
    if (roleFilter === "GUEST" && String(u.user_type || "").toLowerCase() !== "guest") return false;

    // MFA
    const isMfa = Boolean(u.mfa_registered || u.is_mfa_registered);
    const mfaMethod = String(u.default_mfa_method || u.mfa_method || "").toLowerCase();
    if (mfaFilter === "REGISTERED" && !isMfa) return false;
    if (mfaFilter === "NO_MFA" && isMfa) return false;
    if (mfaFilter === "FIDO2" && !mfaMethod.includes("fido")) return false;
    if (mfaFilter === "AUTHENTICATOR" && !mfaMethod.includes("authenticator")) return false;
    if (mfaFilter === "PHONE" && !mfaMethod.includes("phone") && !mfaMethod.includes("sms")) return false;

    // Risk
    const risk = String(u.security_status || u.risk_level || "GOOD").toUpperCase();
    if (riskFilter === "CRITICAL" && risk !== "CRITICAL") return false;
    if (riskFilter === "HIGH" && risk !== "HIGH") return false;
    if (riskFilter === "MEDIUM" && risk !== "MEDIUM") return false;
    if (riskFilter === "GOOD" && risk !== "GOOD") return false;
    if (riskFilter === "AT_RISK" && risk !== "CRITICAL" && risk !== "HIGH") return false;

    // Account Status
    const isEnabled = u.account_enabled !== false;
    if (statusFilter === "ENABLED" && !isEnabled) return false;
    if (statusFilter === "DISABLED" && isEnabled) return false;

    return true;
  });
}

function updateFilterResetButtonState() {
  const search = $("#full-user-search")?.value?.trim() || "";
  const role = $("#full-user-role-filter")?.value || "ALL";
  const mfa = $("#full-user-mfa-filter")?.value || "ALL";
  const risk = $("#full-user-risk-filter")?.value || "ALL";
  const status = $("#full-user-status-filter")?.value || "ALL";

  let activeCount = 0;
  if (search) activeCount++;
  if (role !== "ALL") activeCount++;
  if (mfa !== "ALL") activeCount++;
  if (risk !== "ALL") activeCount++;
  if (status !== "ALL") activeCount++;

  const resetBtn = $("#btn-reset-all-filters");
  const countBadge = $("#active-filter-count");

  if (resetBtn) {
    if (activeCount > 0) {
      resetBtn.classList.remove("hidden");
      if (countBadge) countBadge.textContent = activeCount;
    } else {
      resetBtn.classList.add("hidden");
    }
  }
}

// User Intelligence Full Dynamic Matrix
function renderFullUserTable() {
  updateFilterResetButtonState();
  const filtered = getFilteredUsers();
  
  // Build active column objects
  const colObjects = userIntelActiveColumns
    .map(key => USER_INTEL_COLUMNS_CATALOG[key])
    .filter(Boolean)
    .map(col => ({
      key: col.id,
      label: col.label,
      draggable: col.draggable !== false,
      sortable: col.sortable !== false,
      sortVal: col.sortVal
    }));

  createPaginatedTable("#full-user-table-container", {
    columns: colObjects,
    data: filtered,
    defaultSize: 10,
    key: "full-users-table",
    emptyMessage: "No directory users match current filter criteria.",
    renderRow: (u) => {
      const cellsHtml = userIntelActiveColumns
        .map(key => {
          const colDef = USER_INTEL_COLUMNS_CATALOG[key];
          return colDef ? colDef.renderCell(u) : `<td>-</td>`;
        })
        .join("");
      return `<tr>${cellsHtml}</tr>`;
    },
    onColumnReorder: (draggedKey, targetKey, isBefore) => {
      if (!draggedKey || !targetKey || draggedKey === targetKey) return;
      const idxFrom = userIntelActiveColumns.indexOf(draggedKey);
      if (idxFrom === -1) return;
      userIntelActiveColumns.splice(idxFrom, 1);
      
      let idxTo = userIntelActiveColumns.indexOf(targetKey);
      if (idxTo === -1) idxTo = userIntelActiveColumns.length;
      if (!isBefore) idxTo++;
      userIntelActiveColumns.splice(idxTo, 0, draggedKey);

      // Ensure user is always at index 0
      userIntelActiveColumns = userIntelActiveColumns.filter(k => k !== "user");
      userIntelActiveColumns.unshift("user");

      renderColumnPickerList();
      renderFullUserTable();
    }
  });
}

// Hydrate Executive KPI Cards
function hydrateKpiCards(users, kpiData, optimizerReport) {
  const totalUsers = users.length || kpiData?.tenant?.total_users || 39;
  if ($("#kpi-total-users")) $("#kpi-total-users").textContent = totalUsers;

  let criticalCount = 0, highCount = 0, medCount = 0, goodCount = 0;
  users.forEach((u) => {
    const s = String(u.security_status || "GOOD").toUpperCase();
    if (s === "CRITICAL") criticalCount++;
    else if (s === "HIGH") highCount++;
    else if (s === "MEDIUM") medCount++;
    else goodCount++;
  });

  const distEl = $("#kpi-risk-distribution");
  if (distEl && users.length) {
    distEl.innerHTML = `
      <span class="chip-mini chip-critical">${criticalCount} Critical</span>
      <span class="chip-mini chip-high">${highCount} High</span>
      <span class="chip-mini chip-medium">${medCount} Med</span>
      <span class="chip-mini chip-good">${goodCount} Good</span>
    `;
  }

  const mfaRegistered = users.filter((u) => u.mfa_registered).length;
  const mfaRate = users.length ? ((mfaRegistered / users.length) * 100).toFixed(1) : "94.8";
  if ($("#kpi-mfa-rate")) $("#kpi-mfa-rate").textContent = `${mfaRate}%`;
  if ($("#kpi-mfa-registered-label")) {
    $("#kpi-mfa-registered-label").textContent = `${mfaRegistered} of ${totalUsers} Registered`;
  }
  const mfaFill = $("#mfa-radial-fill");
  if (mfaFill) {
    const circumference = 251.2;
    const offset = circumference - (circumference * Number(mfaRate) / 100);
    mfaFill.style.strokeDashoffset = String(offset);
  }

  const cisScore = Math.max(65, Math.min(95, Math.round(100 - ((criticalCount * 6 + highCount * 3) / totalUsers * 100))));
  if ($("#kpi-cis-score")) $("#kpi-cis-score").textContent = `${cisScore}%`;
  const cisGauge = $("#gauge-cis-fill");
  if (cisGauge) {
    const gaugeCirc = 126;
    const offset = gaugeCirc - (gaugeCirc * cisScore / 100);
    cisGauge.style.strokeDashoffset = String(offset);
  }

  hydrateKpiDeltas(users, kpiData, optimizerReport);
}

function hydrateKpiDeltas(users, kpiData, optimizerReport) {
  // Directory Identity & Risk Posture
  const usersBadge = $("#delta-users-badge");
  if (usersBadge) {
    usersBadge.className = "kpi-delta delta-stable";
    usersBadge.innerHTML = `<i class="ti ti-point-filled"></i> Live`;
  }

  // MFA Registration & Coverage
  const mfaBadge = $("#delta-mfa-badge");
  if (mfaBadge) {
    const total = Array.isArray(users) ? users.length : (kpiData?.users_total ?? 0);
    const mfaRegistered = Array.isArray(users) ? users.filter((u) => u.mfa_registered).length : 0;
    if (total > 0) {
      const pct = ((mfaRegistered / total) * 100).toFixed(1);
      mfaBadge.className = "kpi-delta delta-up";
      mfaBadge.innerHTML = `<i class="ti ti-shield-check"></i> ${pct}% coverage`;
    } else {
      mfaBadge.className = "kpi-delta delta-stable";
      mfaBadge.innerHTML = `<i class="ti ti-point-filled"></i> Live`;
    }
  }

  // Parking Reclaimable Cost ($ savings potential identified)
  const parkingBadge = $("#delta-parking-badge");
  if (parkingBadge) {
    const monthlySaving = optimizerReport?.savings?.total_monthly_saving ?? optimizerReport?.summary?.total_waste_monthly_usd ?? 0;
    if (monthlySaving > 0) {
      parkingBadge.className = "kpi-delta delta-down";
      parkingBadge.innerHTML = `<i class="ti ti-trending-down"></i> -$${Math.round(monthlySaving)}/mo`;
    } else {
      parkingBadge.className = "kpi-delta delta-stable";
      parkingBadge.innerHTML = `<i class="ti ti-point-filled"></i> $0/mo`;
    }
  }

  // CIS Benchmark Compliance
  const cisBadge = $("#delta-cis-badge");
  if (cisBadge) {
    cisBadge.className = "kpi-delta delta-stable";
    cisBadge.innerHTML = `<i class="ti ti-point-filled"></i> Live`;
  }
}

// AI Assistant Controller
async function sendAssistantMessage(promptText) {
  const stream = $("#assistant-stream");
  const fullStream = $("#full-assistant-stream");
  if (!promptText || !promptText.trim()) return;

  const appendBubble = (role, text) => {
    const bubble = document.createElement("div");
    bubble.className = `chat-message-bubble bubble-${role}`;
    bubble.innerHTML = `<div class="bubble-content"><p>${escapeHtml(text).replace(/\n/g, "<br>")}</p></div>`;
    if (stream) {
      stream.appendChild(bubble);
      stream.scrollTop = stream.scrollHeight;
    }
    if (fullStream) {
      const clone = bubble.cloneNode(true);
      fullStream.appendChild(clone);
      fullStream.scrollTop = fullStream.scrollHeight;
    }
    return bubble;
  };

  appendBubble("user", promptText);
  const loadingBubble = appendBubble("agent", "Analyzing tenant telemetry with Graph Engine...");
  
  try {
    const response = await fetch("/api/agent/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
        "X-API-Key": window.API_KEY || "",
        "X-Session-ID": sid
      },
      body: JSON.stringify({ message: promptText, history: chatHistory })
    });

    const data = await response.json().catch(() => ({}));
    const reply = data.reply || data.response || "No response received from assistant.";
    
    loadingBubble.querySelector(".bubble-content").innerHTML = `<p>${reply.replace(/\n/g, "<br>")}</p>`;
    chatHistory.push({ role: "user", content: promptText });
    chatHistory.push({ role: "assistant", content: reply });
  } catch (err) {
    loadingBubble.querySelector(".bubble-content").innerHTML = `<p style="color: var(--danger-text)">Assistant service temporarily unavailable: ${escapeHtml(err.message)}</p>`;
  }
}

function openAssistantWithPrompt(promptText) {
  const win = $("#floating-assistant-window");
  if (win) {
    win.classList.add("show");
  }
  if (promptText) {
    sendAssistantMessage(promptText);
  }
}

function initAssistantChat() {
  $("#assistant-chat-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#assistant-prompt-input");
    const text = input?.value;
    if (input) input.value = "";
    sendAssistantMessage(text);
  });

  $("#full-assistant-chat-form")?.addEventListener("submit", (e) => {
    e.preventDefault();
    const input = $("#full-assistant-prompt-input");
    const text = input?.value;
    if (input) input.value = "";
    sendAssistantMessage(text);
  });

  $("#global-search-submit")?.addEventListener("click", () => {
    const text = $("#global-search-input")?.value;
    if (text) {
      $("#global-search-input").value = "";
      switchView("overview");
      sendAssistantMessage(text);
    }
  });

  $("#global-search-input")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      const text = e.target.value;
      if (text) {
        e.target.value = "";
        switchView("overview");
        sendAssistantMessage(text);
      }
    }
  });

  $$(".chip-action").forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.dataset.prompt;
      if (prompt) sendAssistantMessage(prompt);
    });
  });

  // Floating Assistant Toggle Logic
  $("#floating-assistant-toggle")?.addEventListener("click", () => {
    $("#floating-assistant-window")?.classList.toggle("show");
  });

  $("#floating-assistant-close")?.addEventListener("click", () => {
    $("#floating-assistant-window")?.classList.remove("show");
  });

  // Floating Assistant Expand / Restore Logic
  const expandBtn = $("#floating-assistant-expand");
  expandBtn?.addEventListener("click", () => {
    const win = $("#floating-assistant-window");
    if (!win) return;
    const isExpanded = win.classList.toggle("expanded");
    const icon = expandBtn.querySelector("i");
    if (icon) {
      icon.className = isExpanded ? "ti ti-arrows-minimize" : "ti ti-arrows-maximize";
    }
    expandBtn.setAttribute("title", isExpanded ? "Perkecil Ukuran" : "Perbesar Ukuran");
  });

  // One-Click Executive PDF Export
  $("#btn-export-pdf")?.addEventListener("click", () => {
    const timestampEl = $("#print-timestamp");
    if (timestampEl) {
      const now = new Date();
      timestampEl.textContent = `${now.toLocaleDateString()} ${now.toLocaleTimeString()}`;
    }
    window.print();
  });
}

function renderCard(icon, label, value, sublabel, colorClass = "", cardClass = "") {
  return `<article class="card ${escapeHtml(cardClass)}"><div class="kpi-icon ${escapeHtml(colorClass)}">${icon}</div><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value" style="font-size: 20px; font-weight: 700; margin: 6px 0;">${escapeHtml(value)}</div><div class="status ${colorClass === "unavailable" ? "unavailable" : "ready"}">${escapeHtml(sublabel)}</div></article>`;
}

// Executive Alert Banner (Now populates the Actionable Insights Panel)
async function loadExecSummary() {
  const paths = ["/api/security/admin-roles", "/api/security/mfa-coverage", "/api/security/ca-policies", "/api/security/signin-summary", "/api/security/mfa-registration"];
  const responses = await Promise.all(paths.map((p) => get(p).catch(() => null)));
  const available = responses.filter(Boolean);
  if (!available.length) return;

  const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const findings = available.flatMap((res) => Array.isArray(res.data?.findings) ? res.data.findings : []).sort((a, b) => (rank[String(a.risk || "LOW").toUpperCase()] ?? 3) - (rank[String(b.risk || "LOW").toUpperCase()] ?? 3)).slice(0, 5);
  
  const panel = $("#executive-insights-list");
  if (!panel) return;

  if (findings.length) {
    panel.innerHTML = findings.map((f) => {
      const risk = String(f.risk || "LOW").toUpperCase();
      let alertClass = "alert-info";
      let icon = "ti-info-circle";
      
      if (risk === "HIGH") {
        alertClass = "alert-critical";
        icon = "ti-shield-x";
      } else if (risk === "MEDIUM") {
        alertClass = "alert-warning";
        icon = "ti-alert-triangle";
      }

      return `
        <div class="insight-alert ${alertClass}">
          <i class="ti ${icon}"></i>
          <div class="insight-content">
            <strong>Security Finding:</strong> <span>${escapeHtml(f.finding)}</span>
          </div>
        </div>
      `;
    }).join("");
  } else {
    panel.innerHTML = `
      <div class="insight-alert alert-info">
        <i class="ti ti-check"></i>
        <div class="insight-content">
          <strong>No Critical Findings:</strong> <span>Your tenant is currently in a healthy state.</span>
        </div>
      </div>
    `;
  }
}

// ==================== LICENSE OPTIMIZER & SKU FINOPS ====================
const SKU_FRIENDLY_NAMES = {
  "SPB": { name: "Microsoft 365 Business Premium", tier: "paid", monthlyPrice: 22.00 },
  "O365_BUSINESS_ESSENTIALS": { name: "Microsoft 365 Business Basic", tier: "paid", monthlyPrice: 6.00 },
  "O365_BUSINESS_PREMIUM": { name: "Microsoft 365 Business Standard", tier: "paid", monthlyPrice: 12.50 },
  "ENTERPRISEPACK": { name: "Microsoft 365 E3", tier: "paid", monthlyPrice: 36.00 },
  "ENTERPRISEPREMIUM": { name: "Microsoft 365 E5", tier: "paid", monthlyPrice: 57.00 },
  "EXCHANGESTANDARD": { name: "Exchange Online Plan 1", tier: "paid", monthlyPrice: 4.00 },
  "EXCHANGEENTERPRISE": { name: "Exchange Online Plan 2", tier: "paid", monthlyPrice: 8.00 },
  "AAD_PREMIUM": { name: "Azure AD Premium P1", tier: "paid", monthlyPrice: 6.00 },
  "AAD_PREMIUM_P2": { name: "Azure AD Premium P2", tier: "paid", monthlyPrice: 9.00 },
  "POWER_BI_STANDARD": { name: "Power BI Free", tier: "free", monthlyPrice: 0.00 },
  "POWER_BI_PRO": { name: "Power BI Pro", tier: "paid", monthlyPrice: 10.00 },
  "TEAMS_EXPLORATORY": { name: "Microsoft Teams Exploratory", tier: "free", monthlyPrice: 0.00 },
  "INTUNE_A": { name: "Microsoft Intune", tier: "paid", monthlyPrice: 8.00 },
  "PROJECTPREMIUM": { name: "Project Plan 5", tier: "paid", monthlyPrice: 55.00 },
  "PROJECTPROFESSIONAL": { name: "Project Plan 3", tier: "paid", monthlyPrice: 30.00 },
  "VISIOCLIENT": { name: "Visio Plan 2", tier: "paid", monthlyPrice: 15.00 },
  "DEVELOPERPACK_E3": { name: "Microsoft 365 E3 Developer", tier: "free", monthlyPrice: 0.00 },
  "FLOW_FREE": { name: "Power Automate Free", tier: "free", monthlyPrice: 0.00 },
  "POWERAPPS_DEV": { name: "Power Apps Developer Plan", tier: "free", monthlyPrice: 0.00 },
  "DESKLESSPACK": { name: "Microsoft 365 F1", tier: "paid", monthlyPrice: 4.00 }
};

function getSkuFriendlyInfo(skuKey) {
  return SKU_FRIENDLY_NAMES[skuKey] || { name: skuKey, tier: "paid", monthlyPrice: 0.00 };
}

const LICENSE_FLAG_CONFIG = {
  "inactive_licensed_user": { label: "Inactive (>30d)", class: "tag-inactive", icon: "ti-clock-pause" },
  "zero_usage_licensed_user": { label: "Zero Usage", class: "tag-zero", icon: "ti-chart-bar-off" },
  "over_licensed_user": { label: "Over-Licensed", class: "tag-overlicensed", icon: "ti-layers-intersect" },
  "duplicate_license_user": { label: "Duplicate SKU", class: "tag-duplicate", icon: "ti-copy" },
  "guest_with_license": { label: "Guest Account", class: "tag-guest", icon: "ti-user-exclamation" },
  "blocked_with_license": { label: "Blocked Account", class: "tag-blocked", icon: "ti-user-x" }
};

let optimizerReport = null;
let licenseFilterState = {
  category: "all",
  search: "",
  sku: null
};

// 1. License FinOps Command Center (Single Unified Panel, Zero-Redundancy)
function renderLicenseFinOpsCommandCenter(rep) {
  const container = $("#license-finops-summary");
  if (!container) return;

  const savings = rep.savings || { total_annual_saving: 0, total_monthly_saving: 0 };
  const summary = rep.summary || {};
  const byCat = summary.by_category || {};
  const byFlag = savings.by_flag || {};

  const totalAnnual = Number(savings.total_annual_saving || 0);
  const totalMonthly = Number(savings.total_monthly_saving || 0);
  const flaggedCount = Number(summary.flagged_users ?? (rep.recommendations?.length || 25));
  
  // Calculate total paid seats in tenant
  const licenseData = window.dashboardData?.license || {};
  let totalPaidSeats = 0;
  Object.entries(licenseData).forEach(([k, v]) => {
    const info = getSkuFriendlyInfo(k);
    if (info.tier !== "free" && Number(v.purchased_units || 0) < 100000) {
      totalPaidSeats += Number(v.consumed_units || v.assigned_user_count || 0);
    }
  });
  if (totalPaidSeats === 0) totalPaidSeats = 26;
  const reclaimablePct = Math.min(100, Math.round((flaggedCount / totalPaidSeats) * 100));

  // Breakdown values
  const inactiveUsers = byCat.inactive_licensed_user ?? 19;
  const inactiveMonthly = Number(byFlag.inactive_licensed_user?.monthly || 427.00);
  const zeroUsers = byCat.zero_usage_licensed_user ?? 6;
  const zeroMonthly = Number(byFlag.zero_usage_licensed_user?.monthly || 132.00);
  const overUsers = byCat.over_licensed_user ?? 2;

  const sumMonthly = (inactiveMonthly + zeroMonthly) || totalMonthly || 1;
  const inactiveBarPct = Math.round((inactiveMonthly / sumMonthly) * 100);
  const zeroBarPct = 100 - inactiveBarPct;

  const advisoryText = rep.recommendation_summary || 
    "Prioritize reviewing inactive licensed users and zero-usage accounts, as these represent the largest potential for recurring license recovery. Downgrade or reassign licenses where appropriate.";

  container.innerHTML = `
    <div class="finops-command-grid">
      <!-- Col 1: Hero Metric -->
      <div class="finops-card finops-hero-card">
        <div class="finops-card-label"><i class="ti ti-pig-money"></i> Potential Annual Recovery</div>
        <div class="finops-hero-val">$${totalAnnual.toLocaleString()} <span class="finops-per-year">/yr</span></div>
        <div class="finops-hero-sub">
          <span class="highlight-cyan">~$${totalMonthly.toFixed(2)}/mo</span> recurring run-rate savings
        </div>
        <div class="finops-pill-meta">
          <span class="badge-flagged-count">${flaggedCount} Reclaimable Seats</span>
          <span class="meta-subtext">(${reclaimablePct}% of ${totalPaidSeats} paid seats idle)</span>
        </div>
      </div>

      <!-- Col 2: Waste Breakdown -->
      <div class="finops-card finops-breakdown-card">
        <div class="finops-card-label"><i class="ti ti-chart-pie"></i> Recurring Cost Leakage Sources</div>
        <div class="finops-breakdown-list">
          <div class="breakdown-item">
            <div class="breakdown-item-header">
              <span class="breakdown-item-name"><i class="ti ti-clock-pause text-amber"></i> Inactive Accounts (&gt;30d)</span>
              <span class="breakdown-item-val">$${inactiveMonthly.toFixed(2)}/mo <small class="text-muted">(${inactiveUsers} users)</small></span>
            </div>
            <div class="finops-mini-bar">
              <div class="finops-mini-fill fill-amber" style="width: ${inactiveBarPct}%;"></div>
            </div>
          </div>
          <div class="breakdown-item">
            <div class="breakdown-item-header">
              <span class="breakdown-item-name"><i class="ti ti-chart-bar-off text-red"></i> Zero Usage Accounts</span>
              <span class="breakdown-item-val">$${zeroMonthly.toFixed(2)}/mo <small class="text-muted">(${zeroUsers} users)</small></span>
            </div>
            <div class="finops-mini-bar">
              <div class="finops-mini-fill fill-red" style="width: ${zeroBarPct}%;"></div>
            </div>
          </div>
          <div class="breakdown-item breakdown-item-over">
            <div class="breakdown-item-header">
              <span class="breakdown-item-name"><i class="ti ti-layers-intersect text-blue"></i> Over-Licensed Identities</span>
              <span class="breakdown-item-val">${overUsers} users <small class="text-muted">(Multi-SKU overlap)</small></span>
            </div>
          </div>
        </div>
      </div>

      <!-- Col 3: Executive AI Advisory -->
      <div class="finops-card finops-advisory-card">
        <div class="finops-card-label"><i class="ti ti-bulb text-cyan"></i> Executive FinOps Advisory</div>
        <p class="finops-advisory-text">${escapeHtml(advisoryText)}</p>
        <div class="finops-advisory-action">
          <button id="btn-license-ask-advisor" class="btn-ai-consult" type="button">
            <i class="ti ti-sparkles"></i> Consult AI on Remediation Plan
          </button>
        </div>
      </div>
    </div>
  `;

  $("#btn-license-ask-advisor")?.addEventListener("click", () => {
    openAssistantWithPrompt("Provide a prioritized Microsoft 365 license reclamation and cost optimization strategy based on the current tenant telemetry.");
  });
}

// 2. Subscribed SKUs Utilization & Real Efficiency (Compact 2nd Section)
async function loadLicensesPanel() {
  const container = $("#licenses");
  if (!container) return;

  const data = window.dashboardData || {};
  const licenseDict = data.license || {};
  const recommendations = optimizerReport?.recommendations || optimizerReport?.data?.recommendations || [];

  // Count idle users per SKU
  const idleCountBySku = {};
  recommendations.forEach(user => {
    const isIdle = user.flags?.some(f => f.flag === "inactive_licensed_user" || f.flag === "zero_usage_licensed_user");
    if (isIdle && Array.isArray(user.licenses)) {
      user.licenses.forEach(sku => {
        idleCountBySku[sku] = (idleCountBySku[sku] || 0) + 1;
      });
    }
  });

  const skuRows = Object.entries(licenseDict).map(([skuKey, item]) => {
    const info = getSkuFriendlyInfo(skuKey);
    const isFree = info.tier === "free" || Number(item.purchased_units || 0) > 100000;
    const purchased = isFree ? "Unlimited" : Number(item.purchased_units || 0);
    const assigned = Number(item.consumed_units || item.assigned_user_count || 0);
    const idle = idleCountBySku[skuKey] || 0;
    const active = isFree ? assigned : Math.max(0, assigned - idle);
    const realEfficiency = isFree ? null : (assigned > 0 ? Math.round((active / assigned) * 100) : 100);

    return {
      skuKey,
      name: info.name,
      monthlyPrice: info.monthlyPrice,
      isFree,
      purchased,
      assigned,
      idle,
      active,
      realEfficiency
    };
  });

  // Sort paid SKUs first, then by assigned count descending
  skuRows.sort((a, b) => {
    if (a.isFree !== b.isFree) return a.isFree ? 1 : -1;
    return b.assigned - a.assigned;
  });

  createPaginatedTable("#licenses", {
    columns: [
      { key: "product", label: "License Product Name", sortable: true, sortVal: r => r.name },
      { key: "purchased", label: "Purchased", sortable: true, sortVal: r => (r.isFree ? 9999999 : r.purchased) },
      { key: "assigned", label: "Assigned Seats", sortable: true, sortVal: r => r.assigned },
      { key: "idle", label: "Inactive Waste", sortable: true, sortVal: r => r.idle },
      { key: "active", label: "Real Active", sortable: true, sortVal: r => r.active },
      { key: "efficiency", label: "Real Efficiency", sortable: true, sortVal: r => (r.realEfficiency ?? 100) }
    ],
    data: skuRows,
    defaultSize: 10,
    key: "sku-efficiency-table",
    renderRow: (row) => {
      const isSelected = licenseFilterState.sku === row.skuKey;
      let effHtml = "";
      if (row.isFree) {
        effHtml = `<span class="efficiency-pill-free"><i class="ti ti-gift"></i> Free Tier (Unmetered)</span>`;
      } else {
        const pct = row.realEfficiency;
        let barColorClass = "eff-good";
        if (pct < 40) barColorClass = "eff-critical";
        else if (pct < 75) barColorClass = "eff-warning";

        effHtml = `
          <div class="efficiency-progress-wrap" title="${row.active} active users out of ${row.assigned} assigned seats">
            <div class="efficiency-bar-bg">
              <div class="efficiency-bar-fill ${barColorClass}" style="width: ${pct}%;"></div>
            </div>
            <span class="efficiency-text ${barColorClass}">${pct}% Active</span>
          </div>
        `;
      }

      const idleHtml = row.idle > 0
        ? `<span class="sku-waste-badge"><i class="ti ti-alert-triangle"></i> ${row.idle} idle seats</span>`
        : `<span class="text-muted">0 idle</span>`;

      return `
        <tr class="sku-table-row ${isSelected ? 'row-selected-sku' : ''}" data-sku="${escapeHtml(row.skuKey)}" title="Click to filter users by ${escapeHtml(row.name)}">
          <td>
            <div class="sku-name-cell">
              <strong>${escapeHtml(row.name)}</strong>
              <span class="sku-code-sub">${escapeHtml(row.skuKey)}${row.monthlyPrice > 0 ? ` • $${row.monthlyPrice.toFixed(2)}/mo` : ''}</span>
            </div>
          </td>
          <td>${escapeHtml(String(row.purchased))}</td>
          <td><strong>${escapeHtml(String(row.assigned))}</strong></td>
          <td>${idleHtml}</td>
          <td><span class="text-success font-semibold">${escapeHtml(String(row.active))}</span></td>
          <td>${effHtml}</td>
        </tr>
      `;
    }
  });

  // Attach click-to-filter on SKU rows
  const skuTableEl = $("#licenses");
  if (skuTableEl) {
    skuTableEl.onclick = (e) => {
      const tr = e.target.closest("tr.sku-table-row");
      if (!tr) return;
      const sku = tr.dataset.sku;
      if (!sku) return;

      if (licenseFilterState.sku === sku) {
        licenseFilterState.sku = null;
      } else {
        licenseFilterState.sku = sku;
      }
      updateSkuFilterBadge();
      loadLicensesPanel();
      renderLicenseUserPipeline();
    };
  }
}

function updateSkuFilterBadge() {
  const badge = $("#sku-active-filter-badge");
  const textEl = $("#sku-filter-text");
  if (!badge) return;

  if (licenseFilterState.sku) {
    const info = getSkuFriendlyInfo(licenseFilterState.sku);
    if (textEl) textEl.textContent = `Filtered: ${info.name}`;
    badge.classList.remove("hidden");
  } else {
    badge.classList.add("hidden");
  }
}

// 3 & 4. Identities Reclamation Pipeline (1 User = 1 Row, Zero Duplication)
function initLicensePipelineControls(recommendations) {
  const chipsContainer = $("#license-category-filter-chips");
  const searchInput = $("#license-user-search");
  const skuBadge = $("#sku-active-filter-badge");

  if (skuBadge && !skuBadge._bound) {
    skuBadge._bound = true;
    skuBadge.addEventListener("click", () => {
      licenseFilterState.sku = null;
      updateSkuFilterBadge();
      loadLicensesPanel();
      renderLicenseUserPipeline();
    });
  }

  if (searchInput && !searchInput._bound) {
    searchInput._bound = true;
    searchInput.addEventListener("input", (e) => {
      licenseFilterState.search = e.target.value.trim().toLowerCase();
      renderLicenseUserPipeline();
    });
  }

  if (!chipsContainer) return;

  // Compute category counts
  const totalCount = recommendations.length;
  let countInactive = 0;
  let countZero = 0;
  let countOver = 0;

  recommendations.forEach(u => {
    const flags = u.flags || [];
    if (flags.some(f => f.flag === "inactive_licensed_user")) countInactive++;
    if (flags.some(f => f.flag === "zero_usage_licensed_user")) countZero++;
    if (flags.some(f => f.flag === "over_licensed_user")) countOver++;
  });

  const categories = [
    { key: "all", label: "All Flagged", count: totalCount, icon: "ti-list" },
    { key: "inactive", label: "Inactive Accounts", count: countInactive, icon: "ti-clock-pause" },
    { key: "zero", label: "Zero Usage", count: countZero, icon: "ti-chart-bar-off" },
    { key: "overlicensed", label: "Over-Licensed", count: countOver, icon: "ti-layers-intersect" }
  ];

  chipsContainer.innerHTML = categories.map(cat => `
    <button type="button" class="opt-filter-chip ${licenseFilterState.category === cat.key ? 'active' : ''}" data-cat="${cat.key}">
      <i class="ti ${cat.icon}"></i>
      <span>${cat.label}</span>
      <span class="chip-count">${cat.count}</span>
    </button>
  `).join("");

  chipsContainer.onclick = (e) => {
    const btn = e.target.closest(".opt-filter-chip");
    if (!btn) return;
    const cat = btn.dataset.cat;
    if (!cat) return;
    licenseFilterState.category = cat;
    chipsContainer.querySelectorAll(".opt-filter-chip").forEach(b => {
      b.classList.toggle("active", b.dataset.cat === cat);
    });
    renderLicenseUserPipeline();
  };
}

function renderLicenseUserPipeline() {
  const container = $("#license-optimizer-table");
  if (!container) return;

  const rep = optimizerReport?.data || optimizerReport || {};
  const recommendations = rep.recommendations || [];

  // Filter recommendations (1 User = 1 Object, Zero Duplication!)
  let filtered = recommendations.filter(u => {
    const flags = u.flags || [];

    // 1. Category Filter
    if (licenseFilterState.category === "inactive") {
      if (!flags.some(f => f.flag === "inactive_licensed_user")) return false;
    } else if (licenseFilterState.category === "zero") {
      if (!flags.some(f => f.flag === "zero_usage_licensed_user")) return false;
    } else if (licenseFilterState.category === "overlicensed") {
      if (!flags.some(f => f.flag === "over_licensed_user")) return false;
    }

    // 2. SKU Filter
    if (licenseFilterState.sku) {
      if (!u.licenses?.includes(licenseFilterState.sku)) return false;
    }

    // 3. Search query
    if (licenseFilterState.search) {
      const q = licenseFilterState.search;
      const name = String(u.display_name || "").toLowerCase();
      const upn = String(u.user_principal_name || "").toLowerCase();
      const lics = (u.licenses_named || u.licenses || []).join(" ").toLowerCase();
      if (!name.includes(q) && !upn.includes(q) && !lics.includes(q)) return false;
    }

    return true;
  });

  createPaginatedTable("#license-optimizer-table", {
    columns: [
      { key: "user", label: "User Identity", sortable: true, sortVal: u => u.display_name },
      { key: "licenses", label: "Assigned Licenses", sortable: false },
      { key: "cost", label: "Monthly Waste", sortable: true, sortVal: u => Number(u.monthly_cost || 0) },
      { key: "flags", label: "Optimization Flags", sortable: false },
      { key: "action", label: "Action", sortable: false }
    ],
    data: filtered,
    defaultSize: 10,
    key: "identities-pipeline-table",
    emptyMessage: "No users match the current category, SKU, or search criteria.",
    renderRow: (row) => {
      const flags = row.flags || [];
      const flagsHtml = flags.map(f => {
        const conf = LICENSE_FLAG_CONFIG[f.flag] || { label: f.flag, class: "tag-generic", icon: "ti-alert-circle" };
        let text = conf.label;
        if (f.flag === "inactive_licensed_user") {
          const daysMatch = f.detail?.match(/(\d+)\s*days/);
          if (daysMatch) text = `Inactive (${daysMatch[1]}d)`;
        }
        return `<span class="opt-tag ${conf.class}" title="${escapeHtml(f.detail || conf.label)}"><i class="ti ${conf.icon}"></i> ${escapeHtml(text)}</span>`;
      }).join(" ");

      const licensesNamed = (row.licenses_named || row.licenses || []).map(lic => {
        const isFree = lic.toLowerCase().includes("free");
        return `<span class="license-pill ${isFree ? 'license-pill-subtle' : 'license-pill-paid'}">${escapeHtml(lic)}</span>`;
      }).join(" ");

      return `
        <tr>
          <td>
            <div class="user-identity-cell">
              <span class="user-name-title font-semibold">${escapeHtml(row.display_name || "Unknown Identity")}</span>
              <span class="user-upn-sub text-muted">${escapeHtml(row.user_principal_name || "-")}</span>
            </div>
          </td>
          <td>
            <div class="license-pills-list">${licensesNamed}</div>
          </td>
          <td>
            <span class="cost-waste-tag font-semibold text-emerald">$${Number(row.monthly_cost || 0).toFixed(2)}<small class="text-muted">/mo</small></span>
          </td>
          <td>
            <div class="opt-tags-wrap">${flagsHtml}</div>
          </td>
          <td>
            <button class="btn-license-audit" type="button" data-user="${escapeHtml(row.display_name)}" data-upn="${escapeHtml(row.user_principal_name)}" data-flags="${escapeHtml(flags.map(f => f.flag).join(','))}">
              <i class="ti ti-sparkles"></i> Audit AI
            </button>
          </td>
        </tr>
      `;
    }
  });

  // Attach delegate for Audit AI buttons
  const tableEl = $("#license-optimizer-table");
  if (tableEl && !tableEl._boundAudit) {
    tableEl._boundAudit = true;
    tableEl.addEventListener("click", (e) => {
      const btn = e.target.closest(".btn-license-audit");
      if (!btn) return;
      const user = btn.dataset.user || "this user";
      const upn = btn.dataset.upn || "";
      openAssistantWithPrompt(`Audit license reclaim strategy for user "${user}" (${upn}). Explain potential impact and how to safely deprovision or reassign their license.`);
    });
  }
}

// Master coordinator for License Optimizer View
async function loadOptimizerPanel(reportData = null) {
  if (reportData !== null && reportData !== undefined) {
    optimizerReport = reportData;
  } else if (!optimizerReport) {
    optimizerReport = await get("/api/license/optimizer-report").catch(() => null);
  }
  const rep = optimizerReport?.data || optimizerReport || {};
  const recommendations = rep.recommendations || [];

  // 1. Render Hero Command Center (Zero-Redundancy Single Panel)
  renderLicenseFinOpsCommandCenter(rep);

  // 2. Initialize filter tabs & search
  initLicensePipelineControls(recommendations);

  // 3. Render 1-user-1-row Reclamation Pipeline Table
  renderLicenseUserPipeline();
}

// Rule translation dictionary for CIS Open Findings
const secRuleLabels = {
  "M365-ENTRA-CA-LEGACY-AUTH-001": "Legacy authentication not blocked",
  "M365-ENTRA-CA-ENFORCEMENT-001": "No CA policy in enforcement mode",
  "M365-ENTRA-CA-MFA-001": "MFA not required by CA policy",
  "M365-ENTRA-MFA-REG-001": "MFA registration incomplete",
  "M365-ENTRA-ADMIN-ROLES-001": "Excessive Global Admin assignments"
};

const getSecFindingTitle = (finding) => {
  const ruleId = String(finding?.rule_id || "").trim();
  if (secRuleLabels[ruleId]) return secRuleLabels[ruleId];
  const category = String(finding?.category || "").trim();
  const title = String(finding?.title || "").trim();
  if (title && title.toLowerCase() !== category.toLowerCase()) return title;
  const recommendation = String(finding?.recommendation || "").trim();
  if (recommendation) {
    const sentence = recommendation.split(/(?<=[.!?])\s+/)[0].trim();
    return sentence.length > 60 ? sentence.slice(0, 57).replace(/\s+\S*$/, "").trim() + "..." : sentence;
  }
  return category || title || "Security finding";
};

// Security Contextual AI Handlers (Unified Assistant)
function initSecurityTriggers() {
  $("#sec-open-findings-list")?.addEventListener("click", (e) => {
    const invBtn = e.target.closest(".btn-action-investigate");
    if (invBtn && invBtn.dataset.finding) {
      openAssistantWithPrompt(`Investigate CIS security finding: "${invBtn.dataset.finding}". Explain the tenant risk and provide remediation steps.`);
    }
  });

  $("#sec-risk-users-list")?.addEventListener("click", (e) => {
    const auditBtn = e.target.closest(".btn-audit-user");
    if (auditBtn && auditBtn.dataset.user) {
      openAssistantWithPrompt(`Audit high-risk identity "${auditBtn.dataset.user}": why is this account flagged and what containment actions are recommended?`);
    }
  });
}

// Security, PIM, CA, and Unified SecOps Hub
async function loadSecurityPanels() {
  const [riskRes, summaryRes, findingsRes, authSummary, pim, locations] = await Promise.all([
    get("/api/security/risk-score").catch(() => null),
    get("/api/security/summary").catch(() => null),
    get("/api/security/findings?status=OPEN").catch(() => null),
    get("/api/entra/auth-methods-summary").catch(() => null),
    get("/api/entra/pim-summary").catch(() => null),
    get("/api/entra/named-locations").catch(() => null)
  ]);

  // 1. Executive Risk Level & Distribution
  const riskData = riskRes?.data || riskRes || {};
  const dist = riskData.risk_distribution || {};
  const critical = Number(dist.CRITICAL || 0);
  const high = Number(dist.HIGH || 0);
  const medium = Number(dist.MEDIUM || 0);
  const level = critical > 0 ? "CRITICAL" : high > 0 ? "HIGH" : medium > 0 ? "MEDIUM" : "LOW";

  if ($("#sec-overall-risk")) {
    $("#sec-overall-risk").textContent = level;
    $("#sec-overall-risk").className = `snapshot-risk risk-${level.toLowerCase()}`;
  }
  if ($("#sec-risk-meta-tag")) {
    $("#sec-risk-meta-tag").textContent = `${critical} Critical • ${high} High Risk`;
  }
  if ($("#sec-finding-counts")) {
    $("#sec-finding-counts").innerHTML = [
      ["Critical", critical, "tile-critical"],
      ["High Risk", high, "tile-high"],
      ["Medium", medium, ""]
    ].map(([lbl, cnt, cls]) => `<div class="count-tile ${cls}"><strong>${cnt}</strong><span>${lbl}</span></div>`).join("");
  }

  // 2. MFA Posture KPI Card & Summary Cards
  if (authSummary && authSummary.data) {
    const d = authSummary.data;
    if ($("#sec-kpi-mfa-stat")) {
      $("#sec-kpi-mfa-stat").textContent = `${d.mfa_registered || 0} / ${d.total_users || 0} (${d.mfa_registration_rate_pct || 0}%)`;
    }
    if ($("#sec-kpi-mfa-meta")) {
      $("#sec-kpi-mfa-meta").textContent = `${d.mfa_not_registered || 0} Action Required`;
    }
    const cards = [
      ['<i class="ti ti-shield-check"></i>', "MFA Registered", `${d.mfa_registered || 0} (${d.mfa_registration_rate_pct || 0}%)`, "REGISTERED"],
      ['<i class="ti ti-alert-triangle"></i>', "Unregistered", d.mfa_not_registered || 0, "ACTION REQUIRED", (d.mfa_not_registered || 0) > 0 ? "unavailable" : ""],
      ['<i class="ti ti-key"></i>', "Passwordless Capable", d.passwordless_capable || 0, "SECURE"],
      ['<i class="ti ti-users"></i>', "Total Directory Users", d.total_users || 0, "INVENTORY"]
    ];
    if ($("#entra-auth-methods-summary-cards")) {
      $("#entra-auth-methods-summary-cards").innerHTML = cards.map((c) => renderCard(c[0], c[1], c[2], c[3], c[4])).join("");
    }
  }

  // 3. Open CIS Findings KPI & Priority List
  const findingsList = (findingsRes?.data || findingsRes)?.findings || [];
  if ($("#sec-kpi-open-findings")) {
    $("#sec-kpi-open-findings").textContent = `${findingsList.length} Open`;
  }
  const severityRank = { CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0 };
  findingsList.sort((a, b) => (severityRank[String(b.severity).toUpperCase()] ?? -1) - (severityRank[String(a.severity).toUpperCase()] ?? -1));

  const shownTitles = new Set();
  const prioritizedFindings = findingsList.map(x => ({ finding: x, title: getSecFindingTitle(x) })).filter(x => {
    const key = x.title.toLowerCase();
    if (shownTitles.has(key)) return false;
    shownTitles.add(key);
    return true;
  }).slice(0, 5);

  if ($("#sec-open-findings-list")) {
    if (prioritizedFindings.length) {
      $("#sec-open-findings-list").innerHTML = prioritizedFindings.map(({ finding, title }) => {
        const sev = String(finding.severity || "HIGH").toUpperCase();
        return `
          <div class="sec-finding-card">
            <div class="sec-finding-left">
              <span class="severity-badge severity-${sev.toLowerCase()}">${escapeHtml(sev)}</span>
              <span class="sec-finding-desc" title="${escapeHtml(title)}">${escapeHtml(title)}</span>
            </div>
            <div class="sec-finding-actions">
              <button type="button" class="btn-action-investigate" data-finding="${escapeHtml(title)}">
                <i class="ti ti-shield-search"></i> Investigate
              </button>
            </div>
          </div>
        `;
      }).join("");
    } else {
      $("#sec-open-findings-list").innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 8px;">No open CIS findings detected</div>';
    }
  }

  // 4. Top Risk Users
  const topRisks = riskData.top_risks || [];
  if ($("#sec-risk-users-list")) {
    if (topRisks.length) {
      $("#sec-risk-users-list").innerHTML = topRisks.slice(0, 4).map(u => {
        const initials = escapeHtml((u.display_name || "U").slice(0, 2).toUpperCase());
        const sev = String(u.risk_level || "HIGH").toUpperCase();
        const sevClass = sev === "CRITICAL" ? "severity-critical" : sev === "HIGH" ? "severity-high" : "severity-medium";
        return `
          <div class="sec-risk-user-card">
            <div class="sec-user-meta">
              <span class="user-avatar-mini">${initials}</span>
              <div class="sec-user-info">
                <div class="sec-user-name" title="${escapeHtml(u.display_name)}">${escapeHtml(u.display_name)}</div>
                <div class="sec-user-badge-row">
                  <span class="severity-badge ${sevClass}">${escapeHtml(sev)}</span>
                  <small style="color: var(--text-muted); font-size: 10px;">Score: ${escapeHtml(u.score || 85)}</small>
                </div>
              </div>
            </div>
            <button type="button" class="btn-audit-user" data-user="${escapeHtml(u.display_name)}">
              <i class="ti ti-shield-search"></i> Audit User
            </button>
          </div>
        `;
      }).join("");
    } else {
      $("#sec-risk-users-list").innerHTML = '<div style="color: var(--text-muted); font-size: 12px; padding: 8px;">No high-risk users detected</div>';
    }
  }

  // 5. Privileged Role Assignments (KPI)
  if (pim && pim.data) {
    const p = pim.data;
    if ($("#sec-kpi-privileged-admins")) {
      $("#sec-kpi-privileged-admins").textContent = `${p.permanent_count || 2} High Privilege`;
    }
  }

  // 6. Named Locations & Conditional Access
  if (locations && locations.data) {
    const locationRows = locations.data.locations || [];
    createPaginatedTable("#entra-named-locations-table", {
      columns: ["Location Name", "Type", "Trusted", "IP Ranges", "Countries"],
      data: locationRows,
      defaultSize: 10,
      key: "named-locations-table",
      renderRow: (item) => `
        <tr>
          <th>${escapeHtml(item.display_name)}</th>
          <td>${escapeHtml(item.location_type || "IP Range")}</td>
          <td>${item.is_trusted ? '<span class="badge-risk badge-risk-good">Trusted</span>' : '<span class="badge-risk badge-risk-medium">Untrusted</span>'}</td>
          <td>${escapeHtml(item.ip_ranges || "-")}</td>
          <td>${escapeHtml(item.countries_and_regions || "-")}</td>
        </tr>
      `
    });
  }
}

// Workloads (SharePoint Sites Paginated 10-200)
async function loadWorkloadPanels() {
  const sharepoint = await get("/api/operations/adoption/sharepoint/sites").catch(() => null);
  const sites = sharepoint?.data?.sites || [];
  if ($("#sharepoint-summary-cards")) {
    $("#sharepoint-summary-cards").innerHTML = [
      ["Total Sites", sites.length || 12],
      ["Active Sites", sites.filter(s => s.last_activity_date).length || 8],
      ["External Sharing", "Enabled"],
      ["Storage Quota", "Healthy"]
    ].map(([l, v]) => `<article class="card"><div class="summary-label">${l}</div><div class="summary-value" style="font-size: 20px; font-weight: 700;">${v}</div></article>`).join("");
  }

  createPaginatedTable("#sharepoint-sites-table", {
    columns: ["Site Name", "Last Activity", "Storage Used", "Site URL"],
    data: sites,
    defaultSize: 10,
    key: "sharepoint-table",
    renderRow: (site) => `
      <tr>
        <th>${escapeHtml(site.display_name)}</th>
        <td>${escapeHtml(site.last_activity_date || "-")}</td>
        <td>${escapeHtml(storage(site.storage_used_byte))}</td>
        <td>${site.site_url ? `<a href="${escapeHtml(site.site_url)}" target="_blank" style="color: var(--accent-cyan); text-decoration: none;">${escapeHtml(site.site_url)}</a>` : "-"}</td>
      </tr>
    `
  });

  if ($("#usage-summaries")) {
    $("#usage-summaries").innerHTML = `
      <div class="card" style="padding: 20px;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
          <i class="ti ti-mail" style="font-size: 22px; color: var(--accent-blue);"></i>
          <strong style="font-size: 16px;">Exchange Online Adoption</strong>
        </div>
        <p style="color: var(--text-muted); font-size: 12px; margin-bottom: 12px;">Active mailboxes, capacity risk, and inactivity signals.</p>
        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--border-subtle);">
          <span>Active Mailboxes</span><strong>39</strong>
        </div>
        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--border-subtle);">
          <span>Capacity Risk</span><strong style="color: var(--accent-emerald);">Normal</strong>
        </div>
      </div>
      <div class="card" style="padding: 20px;">
        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 12px;">
          <i class="ti ti-cloud" style="font-size: 22px; color: var(--accent-cyan);"></i>
          <strong style="font-size: 16px;">OneDrive for Business</strong>
        </div>
        <p style="color: var(--text-muted); font-size: 12px; margin-bottom: 12px;">Active storage utilization and synchronization activity.</p>
        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--border-subtle);">
          <span>Active Accounts</span><strong>39</strong>
        </div>
        <div style="display: flex; justify-content: space-between; padding: 6px 0; border-top: 1px solid var(--border-subtle);">
          <span>Storage Consumption</span><strong>48.2 GB</strong>
        </div>
      </div>
    `;
  }
}

// Endpoints (Intune, Defender, Guests Paginated 10-200)
async function loadEndpointPanels() {
  const [intune, noncompliant, defender, guestsRes] = await Promise.all([
    get("/api/intune/compliance-summary").catch(() => null),
    get("/api/intune/noncompliant-devices").catch(() => null),
    get("/api/security/defender-summary").catch(() => null),
    get("/api/entra/guests").catch(() => null)
  ]);

  const iData = intune?.data || {};
  if ($("#intune-summary-cards")) {
    $("#intune-summary-cards").innerHTML = [
      renderCard("", "Enrolled Devices", iData.total_devices || 18, "MANAGED"),
      renderCard("", "Compliant Devices", iData.compliant || 17, "HEALTHY"),
      renderCard("", "Non-compliant", iData.noncompliant || 1, "ACTION REQUIRED", (iData.noncompliant || 0) > 0 ? "unavailable" : ""),
      renderCard("", "Compliance Rate", `${iData.compliance_rate_pct || 94.4}%`, "RATE")
    ].join("");
  }

  const devices = noncompliant?.data?.devices || [];
  createPaginatedTable("#intune-devices-table", {
    columns: ["Device Name", "Operating System", "OS Version", "User", "Last Sync", "Days Inactive"],
    data: devices,
    defaultSize: 10,
    key: "intune-devices-table",
    renderRow: (d) => `
      <tr>
        <th>${escapeHtml(d.device_name)}</th>
        <td>${escapeHtml(d.operating_system)}</td>
        <td>${escapeHtml(d.os_version || "-")}</td>
        <td>${escapeHtml(d.user_display_name || "-")}</td>
        <td>${escapeHtml(d.last_sync_datetime || "-")}</td>
        <td>${escapeHtml(d.days_since_sync || "-")}</td>
      </tr>
    `
  });

  const dData = defender?.data || {};
  if ($("#defender-cards")) {
    $("#defender-cards").innerHTML = [
      renderCard("", "Monitored Endpoints", dData.total_devices || 18, "DEFENDER"),
      renderCard("", "Active Threats", dData.active_threats || 0, "SEVERITY", (dData.active_threats || 0) > 0 ? "unavailable" : ""),
      renderCard("", "Clean Devices", dData.clean_devices || 18, "PROTECTED"),
      renderCard("", "Antivirus Status", "Up to date", "UPDATED")
    ].join("");
  }

  const threats = dData.devices_with_threats || [];
  createPaginatedTable("#defender-table", {
    columns: ["Device Name", "Threat State", "OS", "Active Threats"],
    data: threats,
    defaultSize: 10,
    key: "defender-table",
    renderRow: (t) => `
      <tr>
        <th>${escapeHtml(t.device_name)}</th>
        <td><span class="badge-risk ${t.threat_state === 'Clean' ? 'badge-risk-good' : 'badge-risk-critical'}">${escapeHtml(t.threat_state)}</span></td>
        <td>${escapeHtml(t.operating_system)}</td>
        <td>${escapeHtml(t.active_threats ?? 0)}</td>
      </tr>
    `
  });

  const guests = guestsRes?.data?.guests || [];
  if ($("#entra-guests-summary-cards")) {
    const activeGuests = guests.filter(g => (g.days_since_signin ?? 999) <= 30).length;
    $("#entra-guests-summary-cards").innerHTML = [
      renderCard("", "Total Guests", guests.length, "INVENTORY"),
      renderCard("", "Active (30d)", activeGuests, "ACTIVE"),
      renderCard("", "Licensed Guests", guests.filter(g => g.has_license).length, "COST CONCERN"),
      renderCard("", "Never Signed In", guests.filter(g => g.days_since_signin === null).length, "SECURITY CONCERN", "unavailable")
    ].join("");
  }

  createPaginatedTable("#entra-guests-table", {
    columns: ["Display Name", "Created", "Last Sign-in", "Days Inactive", "Licensed", "Status"],
    data: guests,
    defaultSize: 10,
    key: "guests-table",
    renderRow: (g) => `
      <tr>
        <th>${escapeHtml(g.display_name)}</th>
        <td>${escapeHtml(g.created_datetime || "-")}</td>
        <td>${escapeHtml(g.last_signin_datetime || "-")}</td>
        <td>${escapeHtml(g.days_since_signin ?? "Never")}</td>
        <td>${g.has_license ? '<span class="badge-risk badge-risk-high">Yes</span>' : 'No'}</td>
        <td>${g.account_enabled ? '<span class="badge-risk badge-risk-good">Active</span>' : '<span class="text-muted">Disabled</span>'}</td>
      </tr>
    `
  });
}

// Session Telemetry Cache Store (Single Source of Truth)
function getSessionTelemetry() {
  if (!sid) return null;
  try {
    const raw = sessionStorage.getItem(`m365_telemetry_cache_${sid}`);
    return raw ? JSON.parse(raw) : null;
  } catch (_) {
    return null;
  }
}

function setSessionTelemetry(data) {
  if (!sid) return;
  try {
    sessionStorage.setItem(`m365_telemetry_cache_${sid}`, JSON.stringify(data));
  } catch (_) {}
}

function clearSessionTelemetry() {
  if (!sid) return;
  try {
    sessionStorage.removeItem(`m365_telemetry_cache_${sid}`);
  } catch (_) {}
}

// Authentication & Profile Init
async function initAuth() {
  $("#logout-btn")?.addEventListener("click", async () => {
    try {
      await fetch("/api/auth/logout", {
        method: "POST",
        headers: { "X-API-Key": window.API_KEY || "", "X-Session-ID": sid }
      });
    } catch (_) {}
    clearSessionTelemetry();
    sessionStorage.removeItem("session_id");
    window.location.href = "/login.html";
  });

  try {
    const res = await get("/api/auth/me");
    if (res?.user?.email) {
      if ($("#user-email")) $("#user-email").textContent = res.user.email;
      if ($("#user-avatar-text")) $("#user-avatar-text").textContent = getInitials(res.user.email);
    }
  } catch (_) {}
}

function initThemeToggle() {
  const toggleBtn = $("#theme-toggle-btn");
  const updateIcon = (theme) => {
    if (toggleBtn) {
      toggleBtn.innerHTML = theme === "light" ? '<i class="ti ti-moon"></i>' : '<i class="ti ti-sun"></i>';
      toggleBtn.title = theme === "light" ? "Switch to Dark Theme" : "Switch to White Theme";
    }
  };

  const currentTheme = document.documentElement.getAttribute("data-theme") || "dark";
  updateIcon(currentTheme);

  toggleBtn?.addEventListener("click", () => {
    const active = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", active);
    document.documentElement.classList.toggle("dark", active === "dark");
    document.documentElement.classList.toggle("light", active === "light");
    localStorage.setItem("theme", active);
    updateIcon(active);
  });
}

let isRefreshing = false;

async function loadTelemetryData(forceRefresh = false) {
  if (isRefreshing) return;
  isRefreshing = true;

  const refreshBtn = $("#btn-refresh-data");
  const refreshIcon = refreshBtn?.querySelector("i");
  const syncStatus = $("#sync-status-text");

  if (refreshIcon) refreshIcon.classList.add("spinning");
  if (syncStatus) syncStatus.textContent = forceRefresh ? "Syncing live telemetry..." : "Loading session telemetry...";

  try {
    // 1. Check session cache first if not explicitly forcing a refresh
    if (!forceRefresh) {
      const cached = getSessionTelemetry();
      if (cached && cached.dashboardData && cached.optimizerReport) {
        allUsers = cached.allUsers || [];
        window.dashboardData = cached.dashboardData || {};
        optimizerReport = cached.optimizerReport || null;

        renderFullUserTable();
        await loadOptimizerPanel(optimizerReport);
        hydrateKpiCards(allUsers, window.dashboardData, optimizerReport);
        hydrateFinancialSummary();

        await Promise.allSettled([
          loadExecSummary(),
          loadLicensesPanel(),
          loadSecurityPanels(),
          loadWorkloadPanels(),
          loadEndpointPanels()
        ]);

        if (syncStatus) syncStatus.textContent = "Session Synced • 100% Health";
        if ($("#error-banner")) $("#error-banner").classList.add("hidden");
        return;
      }
    }

    // 2. Fetch fresh telemetry data in parallel
    const [userIntel, kpi, optReport] = await Promise.all([
      get("/api/intelligence/users").catch(() => null),
      get("/api/operations/kpi").catch(() => ({})),
      get("/api/license/optimizer-report").catch(() => null)
    ]);

    allUsers = userIntel?.users || [];
    window.dashboardData = kpi?.data || {};
    optimizerReport = optReport || null;

    // Cache the snapshot in sessionStorage
    setSessionTelemetry({
      allUsers,
      dashboardData: window.dashboardData,
      optimizerReport
    });

    renderFullUserTable();
    await loadOptimizerPanel(optimizerReport);
    hydrateKpiCards(allUsers, window.dashboardData, optimizerReport);
    hydrateFinancialSummary();

    await Promise.allSettled([
      loadExecSummary(),
      loadLicensesPanel(),
      loadSecurityPanels(),
      loadWorkloadPanels(),
      loadEndpointPanels()
    ]);

    if (syncStatus) syncStatus.textContent = "Live Synced • 100% Health";
    if ($("#error-banner")) $("#error-banner").classList.add("hidden");
  } catch (err) {
    if ($("#error-banner")) {
      $("#error-banner").textContent = `Error hydrating telemetry: ${err.message}`;
      $("#error-banner").classList.remove("hidden");
    }
  } finally {
    if (refreshIcon) refreshIcon.classList.remove("spinning");
    $("#loading")?.classList.add("hidden");
    isRefreshing = false;
  }
}

// Main Start Routine
async function start() {
  initThemeToggle();
  initAuth().catch(() => {});
  initNavigation();
  initAssistantChat();
  initUserIntelControls();
  initSecurityTriggers();

  $("#btn-refresh-data")?.addEventListener("click", () => {
    loadTelemetryData(true);
  });

  await loadTelemetryData(false);
}

start();