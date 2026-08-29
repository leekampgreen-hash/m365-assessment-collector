# Microsoft Graph Data Catalog

> **G03-001 — Data Catalog Foundation**
> **Baseline:** G01 API Inventory (COMPLETE, 19 endpoints) + G02 Permission Matrix (COMPLETE)
> **Inputs:** `config/api_inventory.json`, `docs/api-inventory.md`, `docs/permission-matrix.md`, `data/discovery/discovery-state.json`
> **Mode:** OFFLINE — no Microsoft Graph calls, no token acquisition, no state/evidence modification
> **Scope:** Defines WHAT the future Collector (G05) should retain from each discovered endpoint. Not a physical database schema (G06).

---

## 1. Endpoint Data Catalog

One catalog row per discovered endpoint. Controlled values are used for
Collection Pattern, History Requirement, Sensitivity Class, and Recommended
Retention Class.

| Inventory ID | Workload | Endpoint | Data Domain | Collection Purpose | Collection Pattern | Expected Cardinality | History Requirement | Sensitivity Class | Recommended Retention Class | Primary Business Key | Timestamp / Watermark Candidate | KPI / Operational Use | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| G01-001 | Entra ID | Users (`/v1.0/users`) | Identity | Tenant user inventory and identity posture | SNAPSHOT | Medium (39 at discovery; grows with tenant) | CURRENT_ONLY | SENSITIVE | REFERENCE | `id` | `createdDateTime` (also `modifiedDateTime` available via `$select`) | User counts by type, new-user growth, disabled/missing-account anomalies | PII (displayName, UPN) — store selected operational fields only; no full `otherMails`/free-text attributes |
| G01-002 | Entra ID | Groups (`/v1.0/groups`) | Identity | Group inventory and distribution-type mix | SNAPSHOT | Low (17 at discovery) | CURRENT_ONLY | INTERNAL | REFERENCE | `id` | `createdDateTime` (add to `$select` if needed) | Security vs mail vs role-assignable group counts, group growth | `groupTypes` distinguishes group flavors; exclude membership payloads |
| G01-003 | Entra ID | Organization (`/v1.0/organization`) | Identity | Tenant profile and verified-domain posture | SNAPSHOT | Fixed single row (1 at discovery) | CURRENT_ONLY | INTERNAL | REFERENCE | `id` | NONE (no reliable change timestamp exposed) | Tenant type, verified domains, country/region profile | Single-row tenant snapshot; G01-003 permission behavior finding is preserved in G02 — no catalog impact |
| G01-004 | Microsoft 365 Licensing | Subscribed SKUs (`/v1.0/subscribedSkus`) | Licensing | Licensed SKU inventory and consumption trend | SNAPSHOT | Low (3 at discovery; bounded by SKU set) | HISTORICAL_WITH_SNAPSHOT | INTERNAL | STANDARD | `id` | NONE (no modification timestamp exposed; consumption is a point-in-time measure) | License utilization (consumed vs prepaid), service plan activation | Keep SKU id/part number/status and unit counters; flatten `servicePlans` to needed fields only |
| G01-005 | Microsoft Entra ID | Directory Audit Logs (`/v1.0/auditLogs/directoryAudits`) | Security — Audit & Authentication | Directory-change audit trail for detection and forensics | EVENT_LOG | High (321 at discovery; continuous growth) | HISTORICAL | HIGH_SENSITIVITY | LONG | `id` | `activityDateTime` | Admin activity volume by category/service, high-risk change detection, anomaly review | Append-only; keep actor/target **ids** and result/status; exclude free-text target details and any raw payload |
| G01-006 | Microsoft Entra ID | Sign-in Logs (`/v1.0/auditLogs/signIns`) | Security — Audit & Authentication | Authentication event stream for access analytics | EVENT_LOG | Medium (55 at discovery; continuous growth) | HISTORICAL | HIGH_SENSITIVITY | LONG | `id` | `createdDateTime` | Sign-in volume, failure rate, interactive vs non-interactive, app usage | Exclude IP/location/user-agent/correlation data unless later justified; keep userId, appId, status field, clientAppUsed, isInteractive |
| G01-007 | Microsoft Entra ID | Applications (`/v1.0/applications`) | Identity | Application registration inventory | SNAPSHOT | Low (5 at discovery) | CURRENT_ONLY | SENSITIVE | REFERENCE | `id` | `createdDateTime` | Registered-app count, sign-in audience mix, app age | `appId` is a public-ish identifier — treat as internal; no keys/credentials fields |
| G01-008 | Microsoft Entra ID | Service Principals (`/v1.0/servicePrincipals`) | Identity | Service-account / SPN inventory and attack-surface visibility | SNAPSHOT | High (216 at discovery; grows with integrations) | CURRENT_ONLY | SENSITIVE | REFERENCE | `id` | NONE (no reliable change timestamp exposed by SPN in v1.0) | SPN count, enabled vs disabled, type mix, orphaned-app SPNs | Largest directory object discovered; no `appRoleAssignment`/permission payloads |
| G01-009 | Microsoft Entra ID | Devices (`/v1.0/devices`) | Identity | Device inventory and estate hygiene | SNAPSHOT | Low (1 at discovery; grows with enrollment) | CURRENT_ONLY | SENSITIVE | REFERENCE | `id` | NONE (no reliable change watermark; `approximateLastSignInDateTime` is operational only) | OS/version distribution, trust-type mix, stale-device detection | `approximateLastSignInDateTime` supports stale-device KPI but is not a collection watermark |
| G01-010 | Microsoft Entra ID Governance | Administrative Units (`/v1.0/directory/administrativeUnits`) | Identity | Administrative-unit inventory for delegated-scope context | SNAPSHOT | Low (0 at discovery; near-zero expected) | CURRENT_ONLY | INTERNAL | REFERENCE | `id` | NONE (no modification timestamp exposed) | AU count, visibility mix, scoped-admin coverage | 0 rows at discovery is expected state; collector must handle empty results |
| G01-011 | Microsoft Entra Conditional Access | Conditional Access Policies (`/v1.0/identity/conditionalAccess/policies`) | Governance — Conditional Access | CA policy inventory and configuration-change awareness | SNAPSHOT | Low (3 at discovery) | HISTORICAL_WITH_SNAPSHOT | SENSITIVE | REFERENCE | `id` | `modifiedDateTime` (also `createdDateTime`) | Enabled vs disabled policies, policy state changes, coverage baseline | Store metadata + state only; **no** conditions/grants policy bodies; versioned snapshots give policy-change history |
| G01-012 | Microsoft Entra Conditional Access | Conditional Access Named Locations (`/v1.0/identity/conditionalAccess/namedLocations`) | Governance — Conditional Access | Named-location inventory to validate CA scope | SNAPSHOT | Low (4 at discovery) | CURRENT_ONLY | SENSITIVE | REFERENCE | `id` | `modifiedDateTime` (also `createdDateTime`) | Location count and type mix (IP vs country) referenced by policies | Default: metadata + type only; raw `ipRanges`/country lists excluded unless a later requirement justifies them |
| G01-013 | Microsoft Entra ID Protection | Risky Users (`/v1.0/identityProtection/riskyUsers`) | Security — Identity Protection | User risk-state tracking for risk remediation | SNAPSHOT | Low (1 at discovery; scales with risk activity) | HISTORICAL_WITH_SNAPSHOT | HIGH_SENSITIVITY | LONG | `id` | `riskLastUpdatedDateTime` | High-risk user count, risk-level distribution, risk-state remediation progress | Versioned per-risk-state snapshots enable risk-evolution analytics; keep ids + risk fields, no risk-event detail bodies |
| G01-014 | Microsoft Entra ID Protection | Risk Detections (`/v1.0/identityProtection/riskDetections`) | Security — Identity Protection | Risk-event detection stream | EVENT_LOG | Low (1 at discovery; grows within retention window) | HISTORICAL | HIGH_SENSITIVITY | LONG | `id` | `detectedDateTime` (also `activityDateTime`) | Risk event volume by type/timing, risk-level and state trends, detection coverage | Keep event id, timestamps, risk type/level/state; exclude user location/IP/user-agent fields |
| G01-015 | Microsoft 365 Service Health | Service Health Overview (`/v1.0/admin/serviceAnnouncement/healthOverviews`) | Service Health | Service status posture snapshot | SNAPSHOT | Low (27 at discovery; bounded by service catalog) | HISTORICAL_WITH_SNAPSHOT | INTERNAL | STANDARD | `id` | NONE (no timestamp in selected fields) | Per-service availability posture, status-change count | Status-only snapshot per run; change detection via cross-run comparison rather than watermark |
| G01-016 | Microsoft 365 Service Health | Service Health Issues (`/v1.0/admin/serviceAnnouncement/issues`) | Service Health | Service incident lifecycle tracking | INCREMENTAL | Medium (100 at discovery; bounded by active/recent issues) | HISTORICAL | INTERNAL | STANDARD | `id` | `lastModifiedDateTime` (also `startDateTime`, `endDateTime`) | Incident count, MTTR, open-vs-resolved by service/classification | Upsert by issue id on watermark; exclude incident body/notes/details — metadata + status/dates only |
| G01-017 | Microsoft 365 Message Center | Service Update Messages (`/v1.0/admin/serviceAnnouncement/messages`) | Change Communications | Change/communication lifecycle tracking | INCREMENTAL | Medium (100 at discovery; grows over time) | HISTORICAL | INTERNAL | STANDARD | `id` | `lastModifiedDateTime` (also `startDateTime`, `endDateTime`, `actionRequiredByDateTime`) | Message volume by category/severity, major-change count, pending action items | Upsert by message id on watermark; exclude message body/content — metadata + category/severity/dates/services only |
| G01-018 | Microsoft Entra RBAC | Directory Role Definitions (`/v1.0/roleManagement/directory/roleDefinitions`) | RBAC | Directory role catalog for privilege context | REFERENCE | High (145 at discovery; bounded built-in + custom roles) | CURRENT_ONLY | INTERNAL | REFERENCE | `id` | NONE (no modification timestamp exposed) | Role inventory, built-in vs custom mix, privilege-surface reference | No `rolePermissions` payloads in production storage — keep id + displayName + description + isBuiltIn as justified; collector currently has no `$select` for this endpoint |
| G01-019 | Microsoft Entra RBAC | Directory Role Assignments (`/v1.0/roleManagement/directory/roleAssignments`) | RBAC | Privileged role-assignment state and coverage | SNAPSHOT | Low (11 at discovery; grows with delegation) | HISTORICAL_WITH_SNAPSHOT | HIGH_SENSITIVITY | LONG | `id` | NONE (no timestamp exposed on assignment) | Privileged access coverage, standing-role sprawl, who-has-what (by ID) | Keep assignment id + roleDefinitionId + principalId + directoryScopeId; versioned snapshots give assignment-change history; no principal display data |

---

## Data Minimization Principles

Project-wide rules applied to all collection decisions in this catalog, driven
by the **default to DATA MINIMIZATION** directive:

1. **Field minimization.** The Collector may **only** retain fields that have a
   stated operational or KPI purpose in this catalog. Fields absent from the
   G01 `$select` lists or from the Notes/KPI columns are out of scope by
   default. Do not store the full discovered object.

2. **Identity handling.** Store identifiers (`id`, `appId`, `userId`, etc.) for
   correlation and deduplication. Store the minimum display attributes needed
   for dashboards (e.g., `displayName`, `userPrincipalName` for Users). Do not
   store free-text attributes, alternate identifiers, or profile enrichment
   fields without a stated purpose. Human PII in Users is limited to the
   selected identity fields already listed.

3. **Sensitive telemetry.** Sign-in, audit, and risk streams keep event id,
   timestamps, status/result, and the explicit KPI fields named in their rows.
   Excluded by default: IP addresses, geo/location details, user agents,
   correlation IDs, device/browser detail fields, and risk-event detail
   bodies. These may only be added later with an explicit, documented
   justification in this catalog.

4. **Raw payload avoidance.** Never store raw Graph payloads, message bodies,
   service-incident bodies, policy/conditions bodies, named-location IP
   ranges, or role-permission payloads in production collection. Only the
   enumerated metadata/state fields per row are retained.

5. **Evidence vs production storage.** Discovery evidence (raw responses,
   pagination pages, discovery batches) belongs to the discovery evidence
   store and the `data/discovery/` state. Production catalog data is
   restricted to the fields defined in Section 1 and must never be populated
   by copying raw evidence blobs.

6. **Sensitivity-aware retention.** HIGH_SENSITIVITY data (audits, sign-ins,
   risk, role assignments) maps to the LONG retention class. INTERNAL
   operational data maps to STANDARD. Reference/master data maps to
   REFERENCE. No field with a HIGH_SENSITIVITY classification is stored
   without the identity-minimization rules above.

---

## 2. Data Domain Summary

| Data Domain | Endpoint IDs | Endpoint Count | Primary Operational Purpose |
|---|---|---|---|
| Identity | G01-001, G01-002, G01-003, G01-007, G01-008, G01-009, G01-010 | 7 | Directory inventory of users, groups, tenant profile, applications, service principals, devices, and administrative units |
| Licensing | G01-004 | 1 | Licensed SKU inventory and license consumption/enablement posture |
| Security — Audit & Authentication | G01-005, G01-006 | 2 | Directory change audit trail and sign-in event stream for detection, forensics, and access analytics |
| Security — Identity Protection | G01-013, G01-014 | 2 | User risk-state tracking and risk-event detection for identity threat monitoring |
| Governance — Conditional Access | G01-011, G01-012 | 2 | CA policy inventory/change awareness and named-location reference for access-policy posture |
| RBAC | G01-018, G01-019 | 2 | Directory role catalog and privileged role-assignment coverage |
| Service Health | G01-015, G01-016 | 2 | Per-service health posture and service-incident lifecycle tracking |
| Change Communications | G01-017 | 1 | Message Center update lifecycle tracking for change awareness and action items |

**Total: 8 data domains covering 19 endpoints.**

---

## 3. Collection Strategy Summary

| Collection Pattern | Endpoint IDs | Count |
|---|---|---|
| SNAPSHOT | G01-001, G01-002, G01-003, G01-004, G01-007, G01-008, G01-009, G01-010, G01-011, G01-012, G01-013, G01-015, G01-019 | 13 |
| EVENT_LOG | G01-005, G01-006, G01-014 | 3 |
| INCREMENTAL | G01-016, G01-017 | 2 |
| REFERENCE | G01-018 | 1 |

**Architecture implication:** a single snapshot-oriented collector framework
(with id-keyed upsert) covers 14 of 19 endpoints; a small append-only event
collector covers the 3 log streams; an incremental watermark collector covers
the 2 lifecycle endpoints (service issues, message center).

---

## 4. History Requirement Summary

| History Requirement | Endpoint IDs | Count |
|---|---|---|
| CURRENT_ONLY | G01-001, G01-002, G01-003, G01-007, G01-008, G01-009, G01-010, G01-012, G01-018 | 9 |
| HISTORICAL | G01-005, G01-006, G01-014, G01-016, G01-017 | 5 |
| HISTORICAL_WITH_SNAPSHOT | G01-004, G01-011, G01-013, G01-015, G01-019 | 5 |

**Architecture implication:** 5 endpoints require versioning of current-state
data (snapshot history), 5 require pure event/history retention, and 9 can be
maintained as current-state tables with configurable pruning — shaping how G06
splits fact/history stores from current-state/reference stores.

---

## 5. Database Design Inputs

Conceptual implications for G06. **No schemas or physical tables are defined
here.**

### Likely need history / fact-style storage (append or versioned)
- **Append-only event streams:** Directory Audit Logs (G01-005), Sign-in Logs
  (G01-006), Risk Detections (G01-014). High insert volume; dedupe by event
  `id`; LOW-to-LONG retention governs size.
- **Lifecycle entities with change state:** Service Health Issues (G01-016)
  and Service Update Messages (G01-017) — upserted entities whose state
  changes over time (status/resolution); retain full history of status
  transitions or keep entity rows with watermark metadata.
- **Versioned snapshot history (`HISTORICAL_WITH_SNAPSHOT`):** Subscribed SKUs
  (G01-004), CA Policies (G01-011), Risky Users (G01-013), Service Health
  Overview (G01-015), Role Assignments (G01-019) — each collection run creates
  a new version of the current state; prior versions retained for trend/audit.

### Likely need current-state / reference tables
- **Current-state directory tables:** Users (G01-001), Groups (G01-002),
  Organization (G01-003), Applications (G01-007), Service Principals
  (G01-008), Devices (G01-009), Administrative Units (G01-010), Named
  Locations (G01-012). Id-keyed inserts/updates; replace-in-place semantics.
- **Reference data:** Role Definitions (G01-018) — stable catalog, effectively
  static; join target for role assignments.

### Upsert vs append-only semantics
- **Upsert (by `id`):** 16 endpoints — all 13 SNAPSHOT endpoints, the 1 REFERENCE
  endpoint (G01-018), and the 2 INCREMENTAL lifecycle endpoints (G01-016,
  G01-017); `HISTORICAL_WITH_SNAPSHOT` snapshot rows are keyed on `id` + run
  /effective timestamp.
- **Append-only:** 3 EVENT_LOG endpoints (G01-005, G01-006, G01-014) —
  inserts only, deduplicated on event `id`.

### Deduplication requirements
- Event streams: dedupe on Graph event `id` (G01-005, G01-006, G01-014).
- All other endpoints: `id` is the natural upsert key; for
  `HISTORICAL_WITH_SNAPSHOT` sets, dedupe key is `id` + snapshot version,
  preventing duplicate versions from re-runs.
- Watermark-backed incremental endpoints (G01-016, G01-017) rely on `id`
  upsert in addition to watermark filtering.

### Where retention policy will matter most
- **LONG (5 endpoints):** Audit Logs, Sign-ins, Risk Detections, Risky Users,
  Role Assignments — largest and most sensitive; explicit lifecycle/archive
  policy required before G06 design.
- **STANDARD (4 endpoints):** Subscribed SKUs, Health Overview, Health Issues,
  Update Messages — time-boxed value; pruning windows can be aggressive.
- **REFERENCE (10 endpoints):** master/config data — retained while the
  object or configuration is relevant; delete-on-absent semantics tied to
  directory removal signals (where available).
- **SHORT:** currently unused — no endpoint was classified as ephemeral;
  SHORT may still be introduced in G06 if a telemetry subset is separated out.

---

## Validation

| Check | Result |
|---|---|
| Endpoint row count | 19 (G01-001 through G01-019) |
| All endpoints represented exactly once | ✓ — G01-001..G01-019 each present once |
| No endpoint invented | ✓ — all 19 rows trace to `config/api_inventory.json` |
| No endpoint omitted | ✓ |
| Classifications use controlled values | ✓ — Collection Pattern {SNAPSHOT, INCREMENTAL, EVENT_LOG, REFERENCE}; History {CURRENT_ONLY, HISTORICAL, HISTORICAL_WITH_SNAPSHOT}; Sensitivity {LOW, INTERNAL, SENSITIVE, HIGH_SENSITIVITY}; Retention {SHORT, STANDARD, LONG, REFERENCE} |
| No database DDL | ✓ — Section 5 is conceptual only |
| No Graph execution / token acquisition | ✓ — offline analysis of existing artifacts only |
| No source/state/evidence modified | ✓ — only `docs/data-catalog.md` created |

## Source Files Modified

**Expected: NONE** — `config/api_inventory.json`, `docs/api-inventory.md`,
`docs/permission-matrix.md`, `data/discovery/discovery-state.json`, and all
other existing project artifacts are unchanged.

## Blockers

**None.** All 19 endpoints are cataloged with controlled classifications,
watermark and key candidates are assigned per endpoint, and no input
dependency is missing.