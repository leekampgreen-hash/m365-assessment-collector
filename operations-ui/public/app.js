const sid = sessionStorage.getItem("session_id");
if (!sid) window.location.href = "/login.html";
const $ = (selector) => document.querySelector(selector);
const metric = (object) => object && typeof object === "object" ? object : {};
const value = (object) => metric(object).status === "READY" ? metric(object).value : null;
const display = (object, suffix = "") => { const result = value(object); return result === null || result === undefined ? "Data currently unavailable" : `${result}${suffix}`; };
const storage = (number) => { if (number === null || number === undefined || number === "") return "Data currently unavailable"; const units = ["B", "KB", "MB", "GB", "TB"]; let value = Number(number); let index = 0; while (Math.abs(value) >= 1024 && index < units.length - 1) { value /= 1024; index += 1; } return `${value.toFixed(index ? 2 : 0)} ${units[index]}`; };
const source = (object) => metric(object).source_refresh_date ? `Source refreshed ${metric(object).source_refresh_date}` : "Source refresh unavailable";
const status = (object) => metric(object).status === "READY" ? "Ready" : "Data currently unavailable";
const primitive = (value) => value === null || value === undefined || value === "" ? "Data currently unavailable" : `${value}`;
const storageValue = (object) => storage(metric(object).value ?? object);
const DASHBOARD_FETCH_TIMEOUT_MS = 10000;
const PANEL_LOAD_DELAY_MS = 500;
const escapeHtml = (item) => String(item ?? "-").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
const SKELETON_BAR = '<div class="skeleton-bar"></div>'.repeat(3);

function renderCard(icon, label, value, sublabel, colorClass = "") {
  return `<article class="card"><div class="kpi-icon ${escapeHtml(colorClass)}">${icon}</div><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value">${escapeHtml(value)}</div><div class="status ${colorClass === "unavailable" ? "unavailable" : "ready"}">${escapeHtml(sublabel)}</div></article>`;
}

function renderBadge(text, colorClass = "") {
  return `<span class="badge ${escapeHtml(colorClass)}">${escapeHtml(text)}</span>`;
}

function renderTable(columns, rows) {
  return `<table><thead><tr>${columns.map((column) => `<th>${escapeHtml(column)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>`;
}

function renderEmpty(message) {
  return `<p class="empty-state">${escapeHtml(message)}</p>`;
}

function renderError(message, onRetry) {
  const element = document.createElement("div");
  element.className = "panel-error";
  element.innerHTML = `<p>${escapeHtml(message)}</p><button type="button" class="plain-button">Retry</button>`;
  element.querySelector("button").addEventListener("click", onRetry);
  return element.outerHTML;
}

function renderSkeleton(rows = 4) {
  return `<div class="panel-skeleton"><div class="skeleton-card-grid">${[0, 1, 2].map(() => `<div class="skeleton-card"><div class="skeleton-bar skeleton-bar-title"></div><div class="skeleton-bar skeleton-bar-value"></div><div class="skeleton-bar skeleton-bar-sub"></div></div>`).join("")}</div><div class="skeleton-table">${[0, ...Array(Math.max(0, rows - 1))].map(() => `<div class="skeleton-row"></div>`).join("")}</div></div>`;
}

function renderStat(value, label) {
  return `<div><div class="summary-value">${escapeHtml(value)}</div><div class="summary-label">${escapeHtml(label)}</div></div>`;
}

async function get(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DASHBOARD_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(path, { headers: { Accept: "application/json", "X-API-Key": window.API_KEY || "", "X-Session-ID": sid }, signal: controller.signal });
    if (!response.ok) throw new Error("request failed");
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}

function setHealth(ready) { $("#health-dot").className = `dot ${ready ? "ready" : "error"}`; $("#health-label").textContent = ready ? "Analytics service healthy" : "Analytics service unavailable"; }
function showUnavailable() { $("#error-banner").textContent = "Analytics service unavailable"; $("#error-banner").classList.remove("hidden"); }
function metricCard(label, item, icon, iconClass, sublabel) { return renderCard(icon, label, value(item) === null ? "Data currently unavailable" : display(item), sublabel || status(item), value(item) === null ? "unavailable" : iconClass); }
async function loadExecSummary() {
  const paths = ["/api/security/admin-roles", "/api/security/mfa-coverage", "/api/security/ca-policies", "/api/security/signin-summary", "/api/security/mfa-registration"];
  const responses = await Promise.all(paths.map((path) => get(path).catch(() => null)));
  const available = responses.filter(Boolean);
  if (!available.length) return;
  const rank = { HIGH: 0, MEDIUM: 1, LOW: 2 };
  const findings = available.flatMap((response) => Array.isArray(response.data?.findings) ? response.data.findings : []).sort((a, b) => (rank[String(a.risk || "LOW").toUpperCase()] ?? 3) - (rank[String(b.risk || "LOW").toUpperCase()] ?? 3)).slice(0, 5);
  const panel = $("#exec-summary");
  const count = findings.length;
  if (!count) {
    $("#exec-summary-icon").textContent = "OK";
    $("#exec-summary-count").textContent = "No issues found - tenant looks healthy";
    $("#exec-summary-items").innerHTML = "";
  } else {
    $("#exec-summary-icon").textContent = count >= 3 ? "!" : "!";
    $("#exec-summary-count").textContent = count >= 3 ? `${count} items require your attention` : `! ${count} item${count === 1 ? "" : "s"} require your attention`;
    $("#exec-summary-items").innerHTML = findings.map((finding) => { const risk = String(finding.risk || "LOW").toLowerCase(); const icon = risk === "high" ? "!" : risk === "medium" ? "!" : "."; return `<div class="exec-summary-item ${["high", "medium", "low"].includes(risk) ? risk : "low"}"><span>${icon}</span><span>${escapeHtml(finding.finding)}</span></div>`; }).join("");
  }
  panel.style.display = "block";
}
function renderSummary(data) { const totalUsers = data.tenant?.total_users; const highCount = Number(data.exchange?.capacity_usage?.high ?? 0); const licenseAttention = data.license_attention_count; const card = (label, number, emphasized, icon, iconClass) => renderCard(icon, label, number, emphasized ? "Attention" : "Normal", emphasized ? "unavailable" : iconClass); const personIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5" fill="currentColor"></circle><path d="M5 20c.7-3.5 3.1-5.5 7-5.5s6.3 2 7 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>'; const inboxIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H4z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M4 16h4l1.5-3h5L16 16h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path></svg>'; const badgeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v4a5 5 0 0 1-10 0V4Z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M9 14h6v6H9z" fill="none" stroke="currentColor" stroke-width="2"></path></svg>'; $("#summary-cards").innerHTML = [metricCard("Directory Users", totalUsers, personIcon, "kpi-users", "Active in tenant"), card("Mailbox Capacity Risk", `${highCount} HIGH`, highCount > 0, inboxIcon, "kpi-risk"), card("License Attention", licenseAttention ?? "Data currently unavailable", Number(licenseAttention) > 0, badgeIcon, "kpi-license")].join(""); }
function renderLicenses(data, ready = true) { const rows = ready ? Object.entries(data.license || {}) : []; $("#licenses").innerHTML = rows.length ? `<table><thead><tr><th>SKU</th><th>Purchased</th><th>Consumed</th><th>Available</th><th>Utilization</th><th>Assigned users</th></tr></thead><tbody>${rows.map(([sku, item]) => `<tr><th>${escapeHtml(sku)}</th><td>${escapeHtml(item.purchased_units)}</td><td>${escapeHtml(item.consumed_units)}</td><td class="${Number(item.available_units) === 0 ? "available-zero" : ""}">${escapeHtml(item.available_units)}</td><td><span class="utilization-pill utilization-${Number(item.utilization_percent) === 100 ? "full" : Number(item.utilization_percent) <= 10 ? "low" : "mid"}">${escapeHtml(item.utilization_percent)}%</span></td><td>${escapeHtml(item.assigned_user_count)}</td></tr>`).join("")}</tbody></table>` : `<p class="empty-state">License data currently unavailable</p>`; }
function workloadCard(name, item, fields) { return `<article class="card"><div class="card-head"><h3>${name}</h3></div>${fields.map(([label, key, suffix, kind]) => { const rendered = kind === "primitive" ? primitive(item[key]) : kind === "storage" ? storageValue(item[key]) : display(item[key], suffix); return `<div class="detail-row"><span class="detail-label">${label}</span><strong>${rendered}</strong></div>`; }).join("")}</article>`; }
function renderWorkloads(data) { window.dashboardOnedrive = data.onedrive || {}; renderUsageSummaries(); }
let optimizerReport = null;
let optimizerPage = 1;
let optimizerPageSize = 10;
const confidenceRank = { high: 0, medium: 1, low: 2 };
function renderOptimizer() {
  const report = optimizerReport?.data || optimizerReport || { summary: { flagged_users: 0, by_category: {} }, recommendations: [] };
  const allCategories = ["blocked_with_license", "guest_with_license", "inactive_licensed_user", "zero_usage_licensed_user", "over_licensed_user", "duplicate_license_user"];
  const categories = report.summary?.by_category || {};
  $("#license-optimizer-summary").innerHTML = `<div><div class="summary-label">Total flagged users</div><div class="summary-value">${escapeHtml(report.summary?.flagged_users ?? 0)}</div></div><div class="optimizer-badges">${allCategories.map((key) => `<span class="badge optimizer-${key}">${escapeHtml(key.replaceAll("_", " "))}: ${escapeHtml(categories[key] ?? 0)}</span>`).join("")}</div><p class="optimizer-recommendation">${escapeHtml(report.recommendation_summary || "No recommendation summary available.")}</p>`;
  const savings = report.savings || { total_monthly_saving: 0, total_annual_saving: 0, by_flag: {} };
  $("#license-optimizer-savings").innerHTML = `<section class="optimizer-savings"><h3>POTENTIAL SAVINGS</h3><div class="optimizer-savings-values"><div><strong>$${Number(savings.total_monthly_saving || 0).toFixed(2)}</strong> / month</div><div><strong>$${Number(savings.total_annual_saving || 0).toFixed(2)}</strong> / year</div></div><p>Based on high and medium confidence recommendations only. Unknown SKUs excluded from calculation.</p><table><thead><tr><th>Flag</th><th>Users</th><th>Est. Monthly Saving</th></tr></thead><tbody>${Object.entries(savings.by_flag || {}).map(([flag, item]) => `<tr><th>${escapeHtml(flag)}</th><td>${escapeHtml(item.users)}</td><td>$${Number(item.monthly || 0).toFixed(2)}</td></tr>`).join("")}</tbody></table></section>`;
  const category = $("#optimizer-category")?.value || "ALL", confidence = $("#optimizer-confidence")?.value || "ALL";
  const rows = (report.recommendations || []).flatMap((user) => (user.flags || []).map((flag) => ({ ...user, flag }))).filter((row) => (category === "ALL" || row.flag.flag === category) && (confidence === "ALL" || row.flag.confidence === confidence)).sort((a, b) => confidenceRank[a.flag.confidence] - confidenceRank[b.flag.confidence] || a.flag.flag.localeCompare(b.flag.flag));
  const pageCount = Math.max(1, Math.ceil(rows.length / optimizerPageSize));
  optimizerPage = Math.min(optimizerPage, pageCount);
  const pageRows = rows.slice((optimizerPage - 1) * optimizerPageSize, optimizerPage * optimizerPageSize);
  $("#license-optimizer-controls").innerHTML = `<label>Category <select id="optimizer-category"><option value="ALL">All</option>${allCategories.map((key) => `<option value="${escapeHtml(key)}">${escapeHtml(key.replaceAll("_", " "))}</option>`).join("")}</select></label><label>Confidence <select id="optimizer-confidence"><option value="ALL">All</option><option>high</option><option>medium</option><option>low</option></select></label><label>Rows per page <select id="optimizer-page-size"><option value="10">10</option><option value="25">25</option><option value="50">50</option></select></label>`;
  $("#optimizer-category").value = category; $("#optimizer-confidence").value = confidence; $("#optimizer-page-size").value = String(optimizerPageSize);
  const table = pageRows.length ? `${renderTable(["Display Name", "Licenses", "Monthly Cost", "Flag(s)", "Confidence", "Detail", "Recommended Action"], pageRows.map((row) => `<tr><th>${escapeHtml(row.display_name)}</th><td>${escapeHtml((row.licenses_named || row.licenses || []).join(", "))}</td><td>$${Number(row.monthly_cost || 0).toFixed(2)}</td><td>${escapeHtml(row.flag.flag)}</td><td>${renderBadge(row.flag.confidence, `confidence-${row.flag.confidence}`)}</td><td>${escapeHtml(row.flag.detail)}</td><td>${escapeHtml(row.recommended_action)}</td></tr>`))}<div class="pagination"><button class="plain-button" id="optimizer-previous" type="button" ${optimizerPage === 1 ? "disabled" : ""}>Previous</button><span>Page ${optimizerPage} of ${pageCount}</span><button class="plain-button" id="optimizer-next" type="button" ${optimizerPage === pageCount ? "disabled" : ""}>Next</button></div>` : renderEmpty("No flagged users found");
  $("#license-optimizer-table").innerHTML = table;
  $("#optimizer-category").addEventListener("change", () => { optimizerPage = 1; renderOptimizer(); }); $("#optimizer-confidence").addEventListener("change", () => { optimizerPage = 1; renderOptimizer(); });
  $("#optimizer-page-size").addEventListener("change", (event) => { optimizerPageSize = Number(event.target.value); optimizerPage = 1; renderOptimizer(); });
  $("#optimizer-previous")?.addEventListener("click", () => { optimizerPage -= 1; renderOptimizer(); }); $("#optimizer-next")?.addEventListener("click", () => { optimizerPage += 1; renderOptimizer(); });
}
let sharepointData = {};
function renderSharePoint() {
  const sites = sharepointData.sites || [], external = sharepointData.external || new Set();
  const active = sites.filter((site) => site.last_activity_date !== null && site.last_activity_date !== undefined && site.last_activity_date !== "").length;
  $("#sharepoint-summary-cards").innerHTML = [["Total sites", sites.length], ["Active sites", active], ["Orphaned sites", sharepointData.orphaned?.length || 0], ["External sharing enabled", external.size]].map(([label, count]) => `<article class="card"><div class="summary-label">${label}</div><div class="summary-value">${count}</div></article>`).join("");
  const sort = $("#sharepoint-sort")?.value || "activity";
  const sorted = [...sites].sort((a, b) => sort === "storage" ? Number(b.storage_used_byte || 0) - Number(a.storage_used_byte || 0) : String(b.last_activity_date || "").localeCompare(String(a.last_activity_date || "")));
  const siteUrlCell = (site) => {
    const raw = site.site_url;
    if (raw === null || raw === undefined || String(raw).trim() === "") return `<span class="muted-cell">-</span>`;
    return escapeHtml(raw);
  };
  const nameLooksLikeOwner = (name) => {
    const text = String(name || "").trim();
    if (!text) return false;
    return /\b(Owners?|Administrators?)\b/i.test(text);
  };
  const rows = sorted.map((site) => {
    const name = escapeHtml(site.display_name);
    const ownerNote = nameLooksLikeOwner(site.display_name)
      ? `<div class="muted-note">SharePoint group site</div>`
      : "";
    return `<tr><th><div class="site-name">${name}</div>${ownerNote}</th><td>${escapeHtml(site.last_activity_date || "")}</td><td>${escapeHtml(storage(site.storage_used_byte))}</td><td>${siteUrlCell(site)}</td></tr>`;
  }).join("");
  const table = sorted.length
    ? `<table class="sharepoint-sites"><thead><tr><th>Display Name</th><th>Last Activity</th><th>Storage Used</th><th>Site URL</th></tr></thead><tbody>${rows}</tbody></table>`
    : renderEmpty("No SharePoint site usage data found");
  const note = `<p class="sharepoint-privacy-note">Site URLs are not available. This may be due to tenant privacy settings in Microsoft 365.</p>`;
  $("#sharepoint-sites-table").innerHTML = `<div class="detail-controls"><label>Sort <select id="sharepoint-sort"><option value="activity">Last activity</option><option value="storage">Storage</option></select></label></div>${table}${note}`;
  $("#sharepoint-sort").addEventListener("change", renderSharePoint);
}
const workloadNames = { exchange: '<i class="ti ti-mail" aria-hidden="true"></i>', onedrive: '<i class="ti ti-cloud" aria-hidden="true"></i>' };
const usageLevel = (date, reference) => { if (!date || date === "UNKNOWN") return "NO DATA"; const age = Math.floor((new Date(reference) - new Date(date)) / 86400000); return age <= 1 ? "HIGH" : age <= 7 ? "MEDIUM" : age > 7 ? "LOW" : "NO DATA"; };
const exchangeLevel = (u) => (u.exchange_usage_level || "no_data").replace("no_data", "NO DATA").toUpperCase();
const exchangeBucket = (u) => { const level = exchangeLevel(u); return level === "NO DATA" ? "no_data" : level.toLowerCase(); };
const exchangeActiveUsers = () => correlationUsers.filter((u) => u.exchange_status === "ACTIVE");
const onedriveDetails = () => (window.dashboardOnedrive?.account_details || []);
const onedriveLevel = (u) => String(u.usage_level || "NO_DATA").replace("no_data", "NO DATA").toUpperCase();
let correlationUsers = [];
function usageSummary(workload) { const pool = workload === "exchange" ? exchangeActiveUsers() : workload === "onedrive" ? onedriveDetails() : correlationUsers; const levelOf = workload === "exchange" ? exchangeLevel : workload === "onedrive" ? onedriveLevel : (u) => usageLevel(u[`${workload}_last_activity`], window.dashboardAsOf); const counts = ["HIGH","MEDIUM","LOW","NO DATA"].map((level) => pool.filter((u) => levelOf(u) === level).length); return `<button class="card usage-card" data-workload="${workload}" type="button"><div class="summary-label">${workloadNames[workload]}</div>${counts.map((n,i) => `<div class="usage-count"><span>${["High","Medium","Low","No Data"][i]}</span><strong>${n}</strong></div>`).join("")}</button>`; }
function renderUsageSummaries() { $("#usage-summaries").innerHTML = Object.keys(workloadNames).map(usageSummary).join(""); document.querySelectorAll("[data-workload]").forEach((b) => b.addEventListener("click", () => renderDetail(b.dataset.workload))); }
const formatGb = (number) => { if (number === null || number === undefined || number === "") return "Data currently unavailable"; const gb = Number(number) / (1024 ** 3); return `${gb >= 100 ? gb.toFixed(0) : gb.toFixed(2).replace(/\.00$/, "")} GB`; };
const formatPercent = (number) => number === null || number === undefined || number === "" ? "-" : `${Number(number).toFixed(2).replace(/\.00$/, "")}%`;
const formatFiles = (number) => { if (number === null || number === undefined || number === "") return "-"; const value = Number(number); return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1).replace(/\.0$/, "")}K` : String(value); };
const assignedSkus = (u) => { const skus = u.assigned_skus || u.assignedSkus || []; const items = Array.isArray(skus) ? skus : [skus]; const labels = items.map((sku) => typeof sku === "object" ? (sku.sku_part_number || sku.skuPartNumber || sku.display_name || sku.displayName || sku.product_name || sku.productName || sku.id || "") : sku).map((sku) => String(sku || "").trim()).filter(Boolean); return labels.length ? labels.map(escapeHtml).join("<br>") : "-"; };
let detailState = { workload: null, filter: "ALL", search: "", page: 1, pageSize: 25 };
function renderDetail(workload, filter = detailState.filter, page = 1) {
  detailState = { ...detailState, workload, filter, page };
  $("#usage-detail").classList.remove("hidden"); $("#detail-title").innerHTML = workloadNames[workload];
  const pool = workload === "exchange" ? exchangeActiveUsers() : workload === "onedrive" ? onedriveDetails() : correlationUsers;
  const levelOf = workload === "exchange" ? exchangeLevel : workload === "onedrive" ? onedriveLevel : (u) => usageLevel(u[`${workload}_last_activity`], window.dashboardAsOf);
  const query = detailState.search.trim().toLowerCase();
  const filtered = pool.filter((u) => (detailState.filter === "ALL" || levelOf(u) === detailState.filter) && (!query || [u.display_name, u.user_principal_name, ...(u.assigned_skus || [])].some((v) => String(v || "").toLowerCase().includes(query))));
  const sorted = filtered.sort((a,b) => workload === "exchange" ? ((b.exchange_utilization_percent ?? -1) - (a.exchange_utilization_percent ?? -1)) : String(a[`${workload}_last_activity`] || "").localeCompare(String(b[`${workload}_last_activity`] || "")));
  const pages = Math.max(1, Math.ceil(sorted.length / detailState.pageSize)); detailState.page = Math.min(detailState.page, pages); const shown = sorted.slice((detailState.page - 1) * detailState.pageSize, detailState.page * detailState.pageSize); const first = sorted.length ? (detailState.page - 1) * detailState.pageSize + 1 : 0; const last = Math.min(detailState.page * detailState.pageSize, sorted.length);
  $("#detail-summary").innerHTML = `<div class="detail-controls"><input id="detail-search" type="search" placeholder="Search name, UPN, or SKU" value="${escapeHtml(detailState.search)}"><label>Page size <select id="detail-page-size"><option>25</option><option>50</option><option>100</option></select></label></div><div class="usage-filter-grid">${["HIGH","MEDIUM","LOW","NO DATA"].map((level) => `<button class="filter-button ${detailState.filter === level ? "active" : ""}" data-filter="${level}">${level}: ${pool.filter((u) => levelOf(u) === level).length}</button>`).join("")}<button class="filter-button ${detailState.filter === "ALL" ? "active" : ""}" data-filter="ALL">ALL: ${pool.length}</button></div>`;
  $("#detail-page-size").value = String(detailState.pageSize);
  const headers = workload === "exchange" ? "<th>Storage Used</th><th>Mailbox Capacity</th><th>Utilization %</th>" : workload === "onedrive" ? "<th>Storage Used</th><th>Storage Allocated</th><th>Utilization %</th><th>Files</th>" : "";
  const onedriveTable = workload === "onedrive";
  $("#detail-users").innerHTML = `<table><thead><tr><th>Display Name</th><th>Usage Level</th>${headers}${onedriveTable ? "" : `<th>${workload === "exchange" ? "Last Email Activity" : "Last Activity"}</th><th>Days Since Activity</th>${workload === "exchange" ? "" : `<th>SharePoint Status</th>`}<th>Licensed</th><th>Assigned SKUs</th>`}</tr></thead><tbody>${shown.map((u) => { const date=u[`${workload}_last_activity`], days=date ? Math.floor((new Date(window.dashboardAsOf)-new Date(date))/86400000) : "-"; const cells = workload === "exchange" ? `<td>${formatGb(u.exchange_storage_used ?? u.storage_used)}</td><td>${formatGb(u.mailbox_capacity)}</td><td>${formatPercent(u.exchange_utilization_percent)}</td>` : onedriveTable ? `<td>${escapeHtml(storage(u.storage_used))}</td><td>${escapeHtml(storage(u.storage_allocated))}</td><td>${formatPercent(u.utilization_percent)}</td><td>${formatFiles(u.file_count)}</td>` : ""; return `<tr><th>${escapeHtml(u.display_name || u.user_principal_name)}</th><td>${escapeHtml(levelOf(u))}</td>${cells}${onedriveTable ? "" : `<td>${escapeHtml(date)}</td><td>${days}</td>${workload === "exchange" ? "" : `<td>${escapeHtml(u[`${workload}_status`])}</td>`}<td>${escapeHtml(u.licensed)}</td><td class="sku-cell">${assignedSkus(u)}</td>`}</tr>`; }).join("")}</tbody></table><div class="pagination"><span>Showing ${first}-${last} of ${sorted.length}</span><button class="plain-button" id="detail-prev" ${detailState.page <= 1 ? "disabled" : ""}>Previous</button><span>Page ${detailState.page} of ${pages}</span><button class="plain-button" id="detail-next" ${detailState.page >= pages ? "disabled" : ""}>Next</button></div>`;
  $("#detail-search").addEventListener("input", (e) => { detailState.search = e.target.value; renderDetail(workload, detailState.filter, 1); }); $("#detail-page-size").addEventListener("change", (e) => { detailState.pageSize = Number(e.target.value); renderDetail(workload, detailState.filter, 1); }); document.querySelectorAll(".filter-button").forEach((button) => button.addEventListener("click", () => renderDetail(workload, button.dataset.filter, 1))); $("#detail-prev").addEventListener("click", () => renderDetail(workload, detailState.filter, detailState.page - 1)); $("#detail-next").addEventListener("click", () => renderDetail(workload, detailState.filter, detailState.page + 1));
}
$("#back-overview").addEventListener("click", () => { $("#usage-detail").classList.add("hidden"); });
async function renderInactivity(days = 30) { try { const data = await get(`/api/operations/inactivity?days=${days}`); const item = data.status === "READY" ? (data.data || {}) : {}; $("#inactivity").innerHTML = [["Inactive users", item.inactive_users], ["Active users", item.active_users], ["Insufficient evidence", item.unknown_users], ["Workload inactivity signals", item.multi_workload_inactive_users]].map(([label, number], index) => `<div class="inactivity-cell"><div class="inactivity-number">${data.status === "READY" ? (number ?? 0) : "Data currently unavailable"}</div><div class="inactivity-label">${label}</div>${index === 3 ? '<div class="inactivity-caption">Users with inactivity evidence across evaluated workloads.</div>' : ""}</div>`).join(""); } catch (_) { showUnavailable(); $("#inactivity").innerHTML = `<div class="inactivity-cell">Data currently unavailable</div>`; } }

const PANEL_REGISTRY = {
  usage: { sectionId: "usage-overview-section", loader: loadUsagePanel },
  licenses: { sectionId: "entitlements-section", loader: loadLicensesPanel },
  optimizer: { sectionId: "license-optimizer-section", loader: loadOptimizerPanel },
  sharepoint: { sectionId: "sharepoint-section", loader: loadSharePointPanel },
};
const panelLoadState = {};
const STAGGER_DELAY = PANEL_LOAD_DELAY_MS;

function renderPanelSkeleton(panelKey) {
  const section = document.getElementById(PANEL_REGISTRY[panelKey].sectionId);
  if (!section) return;
  const target = section.querySelector(".panel-body") || section;
  if (!target.querySelector(".panel-skeleton")) {
    const skeleton = document.createElement("div");
    skeleton.innerHTML = renderSkeleton(4);
    const renderedSkeleton = skeleton.firstElementChild;
    renderedSkeleton.dataset.panel = panelKey;
    const actions = document.createElement("div");
    actions.className = "panel-actions";
    actions.innerHTML = `<button type="button" class="plain-button panel-load-btn" data-panel="${panelKey}">Load</button>`;
    renderedSkeleton.appendChild(actions);
    target.appendChild(renderedSkeleton);
  }
}

function renderPanelError(panelKey, retry) {
  const section = document.getElementById(PANEL_REGISTRY[panelKey].sectionId);
  if (!section) return;
  const target = section.querySelector(".panel-body") || section;
target.innerHTML = renderError("Failed to load. Retry?", retry);
   target.querySelector("button").classList.add("panel-retry-btn");
}

async function loadPanel(panelKey) {
  const state = panelLoadState[panelKey];
  if (state && (state.loading || state.loaded)) return;
  panelLoadState[panelKey] = { loading: true, loaded: false };
  const section = document.getElementById(PANEL_REGISTRY[panelKey].sectionId);
  const target = section?.querySelector(".panel-body") || section;
  if (target) {
    const skeleton = target.querySelector(".panel-skeleton");
    if (skeleton) skeleton.remove();
  }
  try {
    await PANEL_REGISTRY[panelKey].loader();
    panelLoadState[panelKey] = { loading: false, loaded: true };
  } catch (error) {
    panelLoadState[panelKey] = { loading: false, loaded: false };
    renderPanelError(panelKey, () => loadPanel(panelKey));
  }
}

function showLoadButtons() {
  Object.keys(PANEL_REGISTRY).forEach((panelKey) => {
    renderPanelSkeleton(panelKey);
    const section = document.getElementById(PANEL_REGISTRY[panelKey].sectionId);
    const btn = section?.querySelector(`.panel-load-btn[data-panel="${panelKey}"]`);
    if (btn) btn.addEventListener("click", () => loadPanel(panelKey));
  });
}

async function loadUsagePanel() {
  const onedriveAdoption = await get("/api/operations/adoption/onedrive").catch(() => null);
  const kpiOnedrive = window.dashboardData?.onedrive || {};
  const adoptionOnedrive = onedriveAdoption?.data;
  const onedriveOwnedFields = ["capacity_usage", "data_last_refreshed", "account_details", "total_storage_used", "total_file_count"];
  const mergedOnedrive = { ...kpiOnedrive };
  if (adoptionOnedrive && typeof adoptionOnedrive === "object") {
    onedriveOwnedFields.forEach((field) => {
      if (Object.prototype.hasOwnProperty.call(adoptionOnedrive, field)) mergedOnedrive[field] = adoptionOnedrive[field];
    });
  }
  window.dashboardOnedrive = mergedOnedrive;
  renderWorkloads({ onedrive: mergedOnedrive });
}

async function loadLicensesPanel() {
  const data = window.dashboardData || {};
  renderLicenses(data, !!Object.keys(data.license || {}).length || data.license_status === "READY");
}

async function loadOptimizerPanel() {
  optimizerReport = await get("/api/license/optimizer-report").catch(() => null);
  renderOptimizer();
}

async function loadSharePointPanel() {
  const [sharepointAdoption, orphanedSites, externalSharing] = await Promise.all([
    get("/api/operations/adoption/sharepoint/sites").catch(() => null),
    get("/api/operations/sharepoint/orphaned-sites").catch(() => null),
    get("/api/operations/sharepoint/external-sharing").catch(() => null),
  ]);
  const siteData = sharepointAdoption?.data || sharepointAdoption || {};
  const adoptionSites = Array.isArray(siteData.sites) ? siteData.sites : [];
  sharepointData = {
    sites: adoptionSites,
    orphaned: orphanedSites?.data?.sites || orphanedSites?.sites || [],
    external: new Set((externalSharing?.data?.tenants || []).flatMap((item) => Array.from({ length: Number(item.sites_with_external_shares || 0) }, (_, index) => `${item.tenant_id}-${index}`))),
  };
  renderSharePoint();
}

function loadPanelsProgressively(keys) {
  let index = 0;
  const runNext = () => {
    if (index >= keys.length) return;
    const key = keys[index++];
    loadPanel(key).finally(() => setTimeout(runNext, STAGGER_DELAY));
  };
  runNext();
}

async function initAuth() {
  const emailEl = $("#user-email");
  const wrapEl = $("#user-logout-wrap");
  const logoutBtn = $("#logout-btn");
  if (logoutBtn) {
    logoutBtn.addEventListener("click", async () => {
      try {
        await fetch("/api/auth/logout", {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "X-API-Key": window.API_KEY || "",
            "X-Session-ID": sid
          }
        });
      } catch (_) {}
      sessionStorage.removeItem("session_id");
      window.location.href = "/login.html";
    });
  }
  try {
    const res = await get("/api/auth/me");
if (res && res.user && res.user.email) {
       if (emailEl) emailEl.textContent = res.user.email;
       if (wrapEl) wrapEl.classList.remove("hidden");
       if (res.user.role === "SUPER_ADMIN") document.getElementById("admin-link")?.classList.remove("hidden");
     }
  } catch (_) {}
}

async function start() {
  initAuth().catch(() => {});
  loadExecSummary().catch(() => {});
  let dashboardReady = false;
  try {
    await get("/health");
    setHealth(true);
    const [kpi, correlation] = await Promise.all([
      get("/api/operations/kpi"),
      get("/api/operations/correlation/users"),
    ]);
    const dashboardData = kpi.data || {};
    window.dashboardData = dashboardData;
    window.dashboardAsOf = kpi.as_of || correlation.as_of || "--";
    $("#as-of").textContent = window.dashboardAsOf;
    correlationUsers = correlation.data?.users || [];
    renderSummary(dashboardData);
     showLoadButtons();
     dashboardReady = true;
  } catch (_) {
    setHealth(false);
    showUnavailable();
  } finally {
    $("#loading").classList.add("hidden");
    if (dashboardReady) $("#dashboard").classList.remove("hidden");
  }
}
document.querySelectorAll("[data-days]").forEach((button) => button.addEventListener("click", () => { document.querySelectorAll("[data-days]").forEach((item) => item.classList.remove("active")); button.classList.add("active"); renderInactivity(button.dataset.days); }));
start().catch(() => { $("#loading").classList.add("hidden"); setHealth(false); showUnavailable(); });