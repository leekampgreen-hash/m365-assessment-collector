# Microsoft Graph Permission Matrix

> **Baseline:** G01 API Inventory (COMPLETE)
> **Generated from:** Offline analysis of G01 discovery evidence
> **Workflow State:** COMPLETE — 19 PASS, 0 PERMISSION_REQUIRED, 0 THROTTLED, 0 API_ERROR

---

## Endpoint Permission Matrix

| Inventory ID | Workload | Endpoint | Auth Type | Documented Application Permission | Observed Runtime Permission | Permission Present in Collector | Final HTTP | Final Classification | Permission Status | Notes |
|---|---|---|---|---|---|---|---|---|---|---|
| G01-001 | Entra ID | Users | application | User.Read.All | User.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained User.Read.All; returned 4 pages, 39 rows |
| G01-002 | Entra ID | Groups | application | Group.Read.All | Group.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained Group.Read.All; returned 2 pages, 17 rows |
| G01-003 | Entra ID | Organization | application | Organization.Read.All | Organization.Read.All | **No** | 200 | PASS | **OBSERVED_WITHOUT_DOCUMENTED_ROLE** | HTTP 200 returned despite Organization.Read.All absent from Collector token at time of discovery |
| G01-004 | Microsoft 365 Licensing | Subscribed SKUs | application | LicenseAssignment.Read.All | LicenseAssignment.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained LicenseAssignment.Read.All; returned 1 page, 3 rows |
| G01-005 | Microsoft Entra ID | Directory Audit Logs | application | AuditLog.Read.All | AuditLog.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained AuditLog.Read.All; returned 4 pages, 321 rows |
| G01-006 | Microsoft Entra ID | Sign-in Logs | application | AuditLog.Read.All | AuditLog.Read.All | Yes | 200 | PASS | SHARED_PERMISSION | Shares AuditLog.Read.All with G01-005; returned 6 pages, 55 rows |
| G01-007 | Microsoft Entra ID | Applications | application | Application.Read.All | Application.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained Application.Read.All; returned 1 page, 5 rows |
| G01-008 | Microsoft Entra ID | Service Principals | application | Application.Read.All | Application.Read.All | Yes | 200 | PASS | SHARED_PERMISSION | Shares Application.Read.All with G01-007; returned 22 pages, 216 rows |
| G01-009 | Microsoft Entra ID | Devices | application | Device.Read.All | Device.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained Device.Read.All; returned 1 page, 1 row |
| G01-010 | Microsoft Entra ID Governance | Administrative Units | application | AdministrativeUnit.Read.All | AdministrativeUnit.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained AdministrativeUnit.Read.All; returned 1 page, 0 rows |
| G01-011 | Microsoft Entra Conditional Access | Conditional Access Policies | application | Policy.Read.All | Policy.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained Policy.Read.All; returned 1 page, 3 rows |
| G01-012 | Microsoft Entra Conditional Access | Conditional Access Named Locations | application | Policy.Read.All | Policy.Read.All | Yes | 200 | PASS | SHARED_PERMISSION | Shares Policy.Read.All with G01-011; returned 1 page, 4 rows |
| G01-013 | Microsoft Entra ID Protection | Risky Users | application | IdentityRiskyUser.Read.All | IdentityRiskyUser.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained IdentityRiskyUser.Read.All; returned 1 page, 1 row |
| G01-014 | Microsoft Entra ID Protection | Risk Detections | application | IdentityRiskEvent.Read.All | IdentityRiskEvent.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained IdentityRiskEvent.Read.All; returned 1 page, 1 row |
| G01-015 | Microsoft 365 Service Health | Service Health Overview | application | ServiceHealth.Read.All | ServiceHealth.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained ServiceHealth.Read.All; returned 1 page, 27 rows |
| G01-016 | Microsoft 365 Service Health | Service Health Issues | application | ServiceHealth.Read.All | ServiceHealth.Read.All | Yes | 200 | PASS | SHARED_PERMISSION | Shares ServiceHealth.Read.All with G01-015; returned 1 page, 100 rows |
| G01-017 | Microsoft 365 Message Center | Service Update Messages | application | ServiceMessage.Read.All | ServiceMessage.Read.All | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained ServiceMessage.Read.All; returned 1 page, 100 rows |
| G01-018 | Microsoft Entra RBAC | Directory Role Definitions | application | RoleManagement.Read.Directory | RoleManagement.Read.Directory | Yes | 200 | PASS | CONFIRMED_REQUIRED | Token contained RoleManagement.Read.Directory; returned 1 page, 145 rows |
| G01-019 | Microsoft Entra RBAC | Directory Role Assignments | application | RoleManagement.Read.Directory | RoleManagement.Read.Directory | Yes | 200 | PASS | SHARED_PERMISSION | Shares RoleManagement.Read.Directory with G01-018; returned 1 page, 11 rows |

---

## Permission Consolidation

| Permission | Affected Endpoint IDs | Endpoint Count | Current Collector Requirement | Evidence Status |
|---|---|---|---|---|
| AuditLog.Read.All | G01-005, G01-006 | 2 | Required | Confirmed — both endpoints returned HTTP 200 with this permission present |
| Application.Read.All | G01-007, G01-008 | 2 | Required | Confirmed — both endpoints returned HTTP 200 with this permission present |
| Policy.Read.All | G01-011, G01-012 | 2 | Required | Confirmed — both endpoints returned HTTP 200 with this permission present |
| ServiceHealth.Read.All | G01-015, G01-016 | 2 | Required | Confirmed — both endpoints returned HTTP 200 with this permission present |
| RoleManagement.Read.Directory | G01-018, G01-019 | 2 | Required | Confirmed — both endpoints returned HTTP 200 with this permission present |
| User.Read.All | G01-001 | 1 | Required | Confirmed |
| Group.Read.All | G01-002 | 1 | Required | Confirmed |
| Organization.Read.All | G01-003 | 1 | **Special Finding** | See G01-003 finding below |
| LicenseAssignment.Read.All | G01-004 | 1 | Required | Confirmed |
| Device.Read.All | G01-009 | 1 | Required | Confirmed |
| AdministrativeUnit.Read.All | G01-010 | 1 | Required | Confirmed |
| IdentityRiskyUser.Read.All | G01-013 | 1 | Required | Confirmed |
| IdentityRiskEvent.Read.All | G01-014 | 1 | Required | Confirmed |
| ServiceMessage.Read.All | G01-017 | 1 | Required | Confirmed |

---

## Current Collector Application Permissions

Derived from `discovery-state.json` token roles as of the final workflow state.

### 1. Confirmed Required by Runtime Testing

These permissions were present in the Collector token and all associated endpoints returned HTTP 200:

- AdministrativeUnit.Read.All
- Application.Read.All
- AuditLog.Read.All
- Device.Read.All
- Group.Read.All
- IdentityRiskEvent.Read.All
- IdentityRiskyUser.Read.All
- LicenseAssignment.Read.All
- Policy.Read.All
- RoleManagement.Read.Directory
- ServiceHealth.Read.All
- ServiceMessage.Read.All
- User.Read.All

### 2. Documented but Observed Behavior Differs

- **Organization.Read.All** — Documented as required for G01-003 (Organization), but the endpoint returned HTTP 200 without this permission present in the Collector token at the time of discovery. The Collector token still does not contain Organization.Read.All in the final state, yet the endpoint was classified PASS. This is a documented permission-behavior anomaly.

### 3. No Longer Pending

No permissions are currently pending. All 19 endpoints reached PASS classification with no THROTTLED, PERMISSION_REQUIRED, or API_ERROR states.

---

## G01-003 Finding (Preserved)

| Attribute | Value |
|---|---|
| Inventory ID | G01-003 |
| Endpoint | Organization (`/v1.0/organization`) |
| Documented Permission | Organization.Read.All |
| Token Roles at Discovery | Group.Read.All, LicenseAssignment.Read.All, User.Read.All |
| Organization.Read.All in Token? | **No** |
| HTTP Status | **200** |
| Classification | **PASS** |
| Permission Status | **OBSERVED_WITHOUT_DOCUMENTED_ROLE** |

**Observation:** The Organization endpoint returned HTTP 200 with full property access and a complete data row (1 page, 1 row) despite the Collector token not containing the documented Organization.Read.All application permission at the time of the original baseline test. This behavior was consistently observed across multiple early discovery runs (batch files `discovery-batch-20260819-003640` through `discovery-batch-20260819-004938` and manual runs `discovery-manual-20260819-004748` through `discovery-manual-20260819-004837`), all of which reported token roles of only `[Group.Read.All, LicenseAssignment.Read.All, User.Read.All]`.

The Collector token in the current final state (`discovery-state.json`) still does **not** list Organization.Read.All, yet the endpoint remains classified as PASS. This finding is preserved for G02 analysis and must not be erased or corrected.

---

## Validation

| Check | Result |
|---|---|
| **Endpoint row count** | 19 (G01-001 through G01-019) |
| **All endpoints represented exactly once** | ✓ |
| **Final state** | 19 PASS — no PERMISSION_REQUIRED, THROTTLED, or API_ERROR |
| **G01-003 finding preserved** | ✓ — documented as OBSERVED_WITHOUT_DOCUMENTED_ROLE |
| **Shared permission groups consolidated** | ✓ — 5 shared groups identified (AuditLog.Read.All, Application.Read.All, Policy.Read.All, ServiceHealth.Read.All, RoleManagement.Read.Directory) |
| **No historical evidence modified** | ✓ — analysis based solely on existing artifacts |
| **No source/config/state files modified** | ✓ — no changes to any existing files |
| **Security: no tenant ID, client ID, secret, token, JWT, GUID, or identity** | ✓ |
| **Permission status values controlled** | ✓ — only CONFIRMED_REQUIRED, OBSERVED_WITHOUT_DOCUMENTED_ROLE, SHARED_PERMISSION used |

---

## Unique Permissions Count

**14 unique documented permissions** across 19 endpoints:

1. User.Read.All
2. Group.Read.All
3. Organization.Read.All
4. LicenseAssignment.Read.All
5. AuditLog.Read.All
6. Application.Read.All
7. Device.Read.All
8. AdministrativeUnit.Read.All
9. Policy.Read.All
10. IdentityRiskyUser.Read.All
11. IdentityRiskEvent.Read.All
12. ServiceHealth.Read.All
13. ServiceMessage.Read.All
14. RoleManagement.Read.Directory

## Source Files Modified

**Expected: NONE** — No changes were made to `config/api_inventory.json`, `data/discovery/discovery-state.json`, `docs/api-inventory.md`, or any other existing project artifact.

## Blockers

**None.** All 19 endpoints are PASS, no permission gaps are pending, and no unresolved issues exist outside the documented G01-003 finding.