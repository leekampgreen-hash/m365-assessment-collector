const $ = (selector) => document.querySelector(selector);
const metric = (object) => object && typeof object === "object" ? object : {};
const value = (object) => metric(object).status === "READY" ? metric(object).value : null;
const display = (object, suffix = "") => { const result = value(object); return result === null || result === undefined ? "Data currently unavailable" : `${result}${suffix}`; };
const storage = (number) => { if (number === null || number === undefined || number === "") return "Data currently unavailable"; const units = ["B", "KB", "MB", "GB", "TB"]; let value = Number(number); let index = 0; while (Math.abs(value) >= 1024 && index < units.length - 1) { value /= 1024; index += 1; } return `${value.toFixed(index ? 2 : 0)} ${units[index]}`; };
const source = (object) => metric(object).source_refresh_date ? `Source refreshed ${metric(object).source_refresh_date}` : "Source refresh unavailable";
const status = (object) => metric(object).status === "READY" ? "Ready" : "Data currently unavailable";
// Render an explicit primitive (plain number/string) field without metric-object semantics.
const primitive = (value) => value === null || value === undefined || value === "" ? "Data currently unavailable" : `${value}`;
// Apply the storage() formatter to a value that may arrive as a metric object or a raw byte number.
const storageValue = (object) => storage(metric(object).value ?? object);
const DASHBOARD_FETCH_TIMEOUT_MS = 10000;
const escapeHtml = (item) => String(item ?? "—").replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);

async function get(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DASHBOARD_FETCH_TIMEOUT_MS);
  try {
    const response = await fetch(path, { headers: { Accept: "application/json", "X-API-Key": window.API_KEY || "" }, signal: controller.signal });
    if (!response.ok) throw new Error("request failed");
    return await response.json();
  } finally {
    clearTimeout(timeout);
  }
}
function setHealth(ready) { $("#health-dot").className = `dot ${ready ? "ready" : "error"}`; $("#health-label").textContent = ready ? "Analytics service healthy" : "Analytics service unavailable"; }
function showUnavailable() { $("#error-banner").textContent = "Analytics service unavailable"; $("#error-banner").classList.remove("hidden"); }
function metricCard(label, item, icon, iconClass, sublabel) { return `<article class="card"><div class="kpi-icon ${iconClass}">${icon}</div><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value">${value(item) === null ? "Data currently unavailable" : escapeHtml(display(item))}</div><div class="status ${value(item) === null ? "unavailable" : "ready"}">${escapeHtml(sublabel || status(item))}</div></article>`; }
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
    $("#exec-summary-icon").textContent = "✅";
    $("#exec-summary-count").textContent = "No issues found — tenant looks healthy";
    $("#exec-summary-items").innerHTML = "";
  } else {
    $("#exec-summary-icon").textContent = count >= 3 ? "🔴" : "⚠️";
    $("#exec-summary-count").textContent = count >= 3 ? `${count} items require your attention` : `⚠️ ${count} item${count === 1 ? "" : "s"} require your attention`;
    $("#exec-summary-items").innerHTML = findings.map((finding) => { const risk = String(finding.risk || "LOW").toLowerCase(); const icon = risk === "high" ? "🔴" : risk === "medium" ? "🟡" : "🟢"; return `<div class="exec-summary-item ${["high", "medium", "low"].includes(risk) ? risk : "low"}"><span>${icon}</span><span>${escapeHtml(finding.finding)}</span></div>`; }).join("");
  }
  panel.style.display = "block";
}
function renderSummary(data) { const totalUsers = data.tenant?.total_users; const highCount = Number(data.exchange?.capacity_usage?.high ?? 0); const licenseAttention = data.license_attention_count; const card = (label, number, emphasized, icon, iconClass) => `<article class="card"><div class="kpi-icon ${iconClass}">${icon}</div><div class="summary-label">${escapeHtml(label)}</div><div class="summary-value">${escapeHtml(number)}</div><div class="status ${emphasized ? "unavailable" : "ready"}">${emphasized ? "Attention" : "Normal"}</div></article>`; const personIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="8" r="3.5" fill="currentColor"></circle><path d="M5 20c.7-3.5 3.1-5.5 7-5.5s6.3 2 7 5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"></path></svg>'; const inboxIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H4z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M4 16h4l1.5-3h5L16 16h4" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"></path></svg>'; const badgeIcon = '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M7 4h10v4a5 5 0 0 1-10 0V4Z" fill="none" stroke="currentColor" stroke-width="2"></path><path d="M9 14h6v6H9z" fill="none" stroke="currentColor" stroke-width="2"></path></svg>'; $("#summary-cards").innerHTML = [metricCard("Directory Users", totalUsers, personIcon, "kpi-users", "Active in tenant"), card("Mailbox Capacity Risk", `${highCount} HIGH`, highCount > 0, inboxIcon, "kpi-risk"), card("License Attention", licenseAttention ?? "Data currently unavailable", Number(licenseAttention) > 0, badgeIcon, "kpi-license")].join(""); }
function renderLicenses(data, ready = true) { const rows = ready ? Object.entries(data.license || {}) : []; $("#licenses").innerHTML = rows.length ? `<table><thead><tr><th>SKU</th><th>Purchased</th><th>Consumed</th><th>Available</th><th>Utilization</th><th>Assigned users</th></tr></thead><tbody>${rows.map(([sku, item]) => `<tr><th>${escapeHtml(sku)}</th><td>${escapeHtml(item.purchased_units)}</td><td>${escapeHtml(item.consumed_units)}</td><td class="${Number(item.available_units) === 0 ? "available-zero" : ""}">${escapeHtml(item.available_units)}</td><td><span class="utilization-pill utilization-${Number(item.utilization_percent) === 100 ? "full" : Number(item.utilization_percent) <= 10 ? "low" : "mid"}">${escapeHtml(item.utilization_percent)}%</span></td><td>${escapeHtml(item.assigned_user_count)}</td></tr>`).join("")}</tbody></table>` : `<p class="empty-state">License data currently unavailable</p>`; }
function workloadCard(name, item, fields) { return `<article class="card"><div class="card-head"><h3>${name}</h3></div>${fields.map(([label, key, suffix, kind]) => { const rendered = kind === "primitive" ? primitive(item[key]) : kind === "storage" ? storageValue(item[key]) : display(item[key], suffix); return `<div class="detail-row"><span class="detail-label">${label}</span><strong>${rendered}</strong></div>`; }).join("")}</article>`; }
function renderWorkloads(data) { window.dashboardOnedrive = data.onedrive || {}; renderUsageSummaries(); }
let optimizerReport = null;
const confidenceRank = { high: 0, medium: 1, low: 2 };
function renderOptimizer() {
  const report = optimizerReport || { summary: { flagged_users: 0, by_category: {} }, recommendations: [] };
  const categories = Object.entries(report.summary.by_category || {});
  $("#license-optimizer-summary").innerHTML = `<div class="summary-value">${escapeHtml(report.summary.flagged_users ?? 0)}</div><div class="optimizer-badges">${categories.map(([key, count]) => `<span class="badge optimizer-${key}">${escapeHtml(key.replaceAll("_", " "))}: ${escapeHtml(count)}</span>`).join("")}</div>`;
  const category = $("#optimizer-category")?.value || "ALL", confidence = $("#optimizer-confidence")?.value || "ALL";
  const rows = (report.recommendations || []).flatMap((user) => user.flags.map((flag) => ({ ...user, flag }))).filter((row) => (category === "ALL" || row.flag.flag === category) && (confidence === "ALL" || row.flag.confidence === confidence)).sort((a, b) => confidenceRank[a.flag.confidence] - confidenceRank[b.flag.confidence] || a.flag.flag.localeCompare(b.flag.flag));
  $("#license-optimizer-controls").innerHTML = `<label>Category <select id="optimizer-category"><option value="ALL">All</option>${categories.map(([key]) => `<option value="${escapeHtml(key)}">${escapeHtml(key.replaceAll("_", " "))}</option>`).join("")}</select></label><label>Confidence <select id="optimizer-confidence"><option value="ALL">All</option><option>high</option><option>medium</option><option>low</option></select></label>`;
  $("#optimizer-category").value = category; $("#optimizer-confidence").value = confidence;
  $("#license-optimizer-table").innerHTML = rows.length ? `<table><thead><tr><th>Display Name</th><th>UPN</th><th>Licenses</th><th>Flag</th><th>Confidence</th><th>Detail</th><th>Recommended Action</th></tr></thead><tbody>${rows.map((row) => `<tr><th>${escapeHtml(row.display_name)}</th><td>${escapeHtml(row.user_principal_name)}</td><td>${escapeHtml(row.licenses.join(", "))}</td><td>${escapeHtml(row.flag.flag)}</td><td><span class="badge confidence-${escapeHtml(row.flag.confidence)}">${escapeHtml(row.flag.confidence)}</span></td><td>${escapeHtml(row.flag.detail)}</td><td>${escapeHtml(row.recommended_action)}</td></tr>`).join("")}</tbody></table>` : `<p class="empty-state">No flagged users found</p>`;
  $("#optimizer-category").addEventListener("change", renderOptimizer); $("#optimizer-confidence").addEventListener("change", renderOptimizer);
}
const workloadNames = { exchange: '<i class="ti ti-mail" aria-hidden="true"></i>', onedrive: '<i class="ti ti-cloud" aria-hidden="true"></i>', sharepoint: '<i class="ti ti-layout-grid" aria-hidden="true"></i>' };
const usageLevel = (date, reference) => { if (!date || date === "UNKNOWN") return "NO DATA"; const age = Math.floor((new Date(reference) - new Date(date)) / 86400000); return age <= 1 ? "HIGH" : age <= 7 ? "MEDIUM" : age > 7 ? "LOW" : "NO DATA"; };
// Exchange capacity presentation is active-only. The authoritative usage_level
// (LOW/MEDIUM/HIGH/NO DATA) comes from the analytics view per user; we only
// surface ACTIVE Exchange users in customer-facing capacity views. INACTIVE and
// UNKNOWN users are excluded from detail + summary while remaining in the
// backend evidence.
const exchangeLevel = (u) => (u.exchange_usage_level || "no_data").replace("no_data", "NO DATA").toUpperCase();
const exchangeBucket = (u) => { const level = exchangeLevel(u); return level === "NO DATA" ? "no_data" : level.toLowerCase(); };
const exchangeActiveUsers = () => correlationUsers.filter((u) => u.exchange_status === "ACTIVE");
const onedriveDetails = () => (window.dashboardOnedrive?.account_details || []);
const onedriveLevel = (u) => String(u.usage_level || "NO_DATA").replace("no_data", "NO DATA").toUpperCase();
let correlationUsers = [];
function usageSummary(workload) { const pool = workload === "exchange" ? exchangeActiveUsers() : workload === "onedrive" ? onedriveDetails() : correlationUsers; const levelOf = workload === "exchange" ? exchangeLevel : workload === "onedrive" ? onedriveLevel : (u) => usageLevel(u[`${workload}_last_activity`], window.dashboardAsOf); const counts = ["HIGH","MEDIUM","LOW","NO DATA"].map((level) => pool.filter((u) => levelOf(u) === level).length); return `<button class="card usage-card" data-workload="${workload}" type="button"><div class="summary-label">${workloadNames[workload]}</div>${counts.map((n,i) => `<div class="usage-count"><span>${["High","Medium","Low","No Data"][i]}</span><strong>${n}</strong></div>`).join("")}</button>`; }
function renderUsageSummaries() { $("#usage-summaries").innerHTML = Object.keys(workloadNames).map(usageSummary).join(""); document.querySelectorAll("[data-workload]").forEach((b) => b.addEventListener("click", () => renderDetail(b.dataset.workload))); }
const formatGb = (number) => { if (number === null || number === undefined || number === "") return "Data currently unavailable"; const gb = Number(number) / (1024 ** 3); return `${gb >= 100 ? gb.toFixed(0) : gb.toFixed(2).replace(/\.00$/, "")} GB`; };
const formatPercent = (number) => number === null || number === undefined || number === "" ? "—" : `${Number(number).toFixed(2).replace(/\.00$/, "")}%`;
const formatFiles = (number) => { if (number === null || number === undefined || number === "") return "—"; const value = Number(number); return value >= 1000 ? `${(value / 1000).toFixed(value >= 10000 ? 0 : 1).replace(/\.0$/, "")}K` : String(value); };
const assignedSkus = (u) => { const skus = u.assigned_skus || u.assignedSkus || []; const items = Array.isArray(skus) ? skus : [skus]; const labels = items.map((sku) => typeof sku === "object" ? (sku.sku_part_number || sku.skuPartNumber || sku.display_name || sku.displayName || sku.product_name || sku.productName || sku.id || "") : sku).map((sku) => String(sku || "").trim()).filter(Boolean); return labels.length ? labels.map(escapeHtml).join("<br>") : "—"; };
let detailState = { workload: null, filter: "ALL", search: "", page: 1, pageSize: 25 };
function renderDetail(workload, filter = detailState.filter, page = 1) {
  detailState = { ...detailState, workload, filter, page };
  $("#usage-detail").classList.remove("hidden"); $("#detail-title").textContent = workloadNames[workload];
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
  $("#detail-users").innerHTML = `<table><thead><tr><th>Display Name</th><th>User / UPN</th><th>Usage Level</th>${headers}${onedriveTable ? "" : `<th>${workload === "exchange" ? "Last Email Activity" : "Last Activity"}</th><th>Days Since Activity</th>${workload === "exchange" ? "" : `<th>SharePoint Status</th>`}<th>Licensed</th><th>Assigned SKUs</th>`}</tr></thead><tbody>${shown.map((u) => { const date=u[`${workload}_last_activity`], days=date ? Math.floor((new Date(window.dashboardAsOf)-new Date(date))/86400000) : "—"; const cells = workload === "exchange" ? `<td>${formatGb(u.exchange_storage_used ?? u.storage_used)}</td><td>${formatGb(u.mailbox_capacity)}</td><td>${formatPercent(u.exchange_utilization_percent)}</td>` : onedriveTable ? `<td>${escapeHtml(storage(u.storage_used))}</td><td>${escapeHtml(storage(u.storage_allocated))}</td><td>${formatPercent(u.utilization_percent)}</td><td>${formatFiles(u.file_count)}</td>` : ""; return `<tr><th>${escapeHtml(u.display_name || u.user_principal_name)}</th><td>${escapeHtml(u.user_principal_name)}</td><td>${escapeHtml(levelOf(u))}</td>${cells}${onedriveTable ? "" : `<td>${escapeHtml(date)}</td><td>${days}</td>${workload === "exchange" ? "" : `<td>${escapeHtml(u[`${workload}_status`])}</td>`}<td>${escapeHtml(u.licensed)}</td><td class="sku-cell">${assignedSkus(u)}</td>`}</tr>`; }).join("")}</tbody></table><div class="pagination"><span>Showing ${first}–${last} of ${sorted.length}</span><button class="plain-button" id="detail-prev" ${detailState.page <= 1 ? "disabled" : ""}>Previous</button><span>Page ${detailState.page} of ${pages}</span><button class="plain-button" id="detail-next" ${detailState.page >= pages ? "disabled" : ""}>Next</button></div>`;
  $("#detail-search").addEventListener("input", (e) => { detailState.search = e.target.value; renderDetail(workload, detailState.filter, 1); }); $("#detail-page-size").addEventListener("change", (e) => { detailState.pageSize = Number(e.target.value); renderDetail(workload, detailState.filter, 1); }); document.querySelectorAll(".filter-button").forEach((button) => button.addEventListener("click", () => renderDetail(workload, button.dataset.filter, 1))); $("#detail-prev").addEventListener("click", () => renderDetail(workload, detailState.filter, detailState.page - 1)); $("#detail-next").addEventListener("click", () => renderDetail(workload, detailState.filter, detailState.page + 1));
}
$("#back-overview").addEventListener("click", () => { $("#usage-detail").classList.add("hidden"); });
async function renderInactivity(days = 30) { try { const data = await get(`/api/operations/inactivity?days=${days}`); const item = data.status === "READY" ? (data.data || {}) : {}; $("#inactivity").innerHTML = [["Inactive users", item.inactive_users], ["Active users", item.active_users], ["Insufficient evidence", item.unknown_users], ["Workload inactivity signals", item.multi_workload_inactive_users]].map(([label, number], index) => `<div class="inactivity-cell"><div class="inactivity-number">${data.status === "READY" ? (number ?? 0) : "Data currently unavailable"}</div><div class="inactivity-label">${label}</div>${index === 3 ? '<div class="inactivity-caption">Users with inactivity evidence across evaluated workloads.</div>' : ""}</div>`).join(""); } catch (_) { showUnavailable(); $("#inactivity").innerHTML = `<div class="inactivity-cell">Data currently unavailable</div>`; } }
async function start() {
  loadExecSummary().catch(() => {});
  let dashboardReady = false;
  try {
    await get("/health");
    setHealth(true);
    const [kpi, correlation, onedriveAdoption, licenseOptimizer] = await Promise.all([
      get("/api/operations/kpi"),
      get("/api/operations/correlation/users"),
       get("/api/operations/adoption/onedrive").catch(() => null),
       get("/api/license/optimizer-report").catch(() => null),

    ]);
    const dashboardData = kpi.data || {};
    const kpiOnedrive = dashboardData.onedrive || {};
    const adoptionOnedrive = onedriveAdoption?.data;
    const onedriveOwnedFields = ["capacity_usage", "data_last_refreshed", "account_details", "total_storage_used", "total_file_count"];
    const mergedOnedrive = { ...kpiOnedrive };
    if (adoptionOnedrive && typeof adoptionOnedrive === "object") {
      onedriveOwnedFields.forEach((field) => {
        if (Object.prototype.hasOwnProperty.call(adoptionOnedrive, field)) mergedOnedrive[field] = adoptionOnedrive[field];
      });
    }
    const renderData = { ...dashboardData, onedrive: mergedOnedrive };
    window.dashboardOnedrive = mergedOnedrive;
    window.dashboardAsOf = kpi.as_of || correlation.as_of || "--";
    $("#as-of").textContent = window.dashboardAsOf;
    correlationUsers = correlation.data?.users || [];
    renderSummary(renderData);
    renderWorkloads(renderData);
    renderLicenses(renderData, kpi.status === "READY");
    optimizerReport = licenseOptimizer;
    renderOptimizer();
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
