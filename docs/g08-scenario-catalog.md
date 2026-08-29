# G08-B Scenario Catalog

> **Authority:** `config/scenarios/catalog.json` (machine-readable index).
> **Design-only task.** No live Graph calls, no tenant writes, no permission grants.
> **Workflow State:** DESIGN COMPLETE — catalog defined, tests passing, registration unmodified.

---

## 1. Purpose

The scenario catalog is the controlled set of Microsoft 365 actions that the future Scenario Agent can execute against dedicated test users. Each scenario is designed to be:

- **Reversible** — every persistent artifact has a documented cleanup path.
- **Low-risk** — no tenant-administration or destructive scenarios are enabled.
- **Observable** — every scenario declares what the G01 collector inventory can (and cannot) observe.
- **Least-privilege** — every permission requirement is a single, narrowly-scoped delegated permission.

The catalog is **only a design artifact**. The Scenario Agent runs no scenario as part of this task.

---

## 2. Catalog Summary

| Metric | Value |
|---|---|
| Total scenarios | **9** |
| Enabled scenarios | **1** |
| Disabled scenarios | **8** |
| Destructive scenarios enabled | **0** |
| Domains | MAIL, CALENDAR, FILES, AUTH |
| Domains explicitly excluded | TEAMS, ADMIN, DESTRUCTIVE_TENANT_OPERATIONS |
| Total scenarios by risk — LOW | 9 |
| Total scenarios by risk — MODERATE | 0 |
| Total scenarios by risk — HIGH | 0 |
| Total scenarios — directly observable by G01 | 1 |
| Total scenarios — indirectly observable by G01 | 8 |
| Total scenarios — not covered by G01 | 0 |

---

## 3. Scenario List

| ID | Name | Domain | Action | Actor | Peer | Risk | Cleanup | Enabled |
|---|---|---|---|---|---|---|---|---|
| `SCN-MAIL-001` | Send test email between two test users | MAIL | `SEND_MAIL` | test-user-01 | test-user-02 | LOW | MANUAL_CLEANUP | No |
| `SCN-MAIL-002` | Send correlation-tagged test email to peer | MAIL | `SEND_MAIL` | test-user-01 | test-user-02 | LOW | MANUAL_CLEANUP | No |
| `SCN-CALENDAR-001` | Create test calendar event in actor calendar | CALENDAR | `CREATE_EVENT` | test-user-01 | — | LOW | AUTO_CLEANUP_SUPPORTED | No |
| `SCN-CALENDAR-002` | Update test calendar event | CALENDAR | `UPDATE_EVENT` | test-user-01 | — | LOW | AUTO_CLEANUP_SUPPORTED | No |
| `SCN-CALENDAR-003` | Delete / cleanup test calendar event | CALENDAR | `DELETE_EVENT` | test-user-01 | — | LOW | NO_CLEANUP_REQUIRED | No |
| `SCN-FILE-001` | Create small test file in actor OneDrive | FILES | `CREATE_FILE` | test-user-01 | — | LOW | AUTO_CLEANUP_SUPPORTED | No |
| `SCN-FILE-002` | Update test file metadata/content | FILES | `UPDATE_FILE` | test-user-01 | — | LOW | AUTO_CLEANUP_SUPPORTED | No |
| `SCN-FILE-003` | Delete / cleanup test file in actor OneDrive | FILES | `DELETE_FILE` | test-user-01 | — | LOW | NO_CLEANUP_REQUIRED | No |
| `SCN-AUTH-001` | Operator-driven test user sign-in | AUTH | `INTERACTIVE_SIGNIN` | test-user-01 | — | LOW | NO_CLEANUP_REQUIRED | **Yes** |

---

## 4. Business / Testing Purpose

| Scenario | Purpose |
|---|---|
| `SCN-MAIL-001` | Validate that a delegated `Mail.Send` action is correctly attributed to test-user-01 in the tenant sign-in log. Establishes the baseline mail-delegation evidence chain. |
| `SCN-MAIL-002` | Validate that a deterministic correlation token in the mail subject can be used to map a scenario run to a downstream evidence record. |
| `SCN-CALENDAR-001` | Validate that a delegate can create a calendar event in the actor's calendar and that the action is attributed to test-user-01. |
| `SCN-CALENDAR-002` | Validate that a delegate can update a previously created event. Tests the write-then-update lifecycle. |
| `SCN-CALENDAR-003` | Cleanup of the calendar event created by `SCN-CALENDAR-001`. |
| `SCN-FILE-001` | Validate that a delegate can create a small file in the actor's OneDrive and that the action is attributed to test-user-01. |
| `SCN-FILE-002` | Validate that a delegate can update an existing file. Tests the write-then-update lifecycle. |
| `SCN-FILE-003` | Cleanup of the file created by `SCN-FILE-001`. |
| `SCN-AUTH-001` | The only scenario that is directly observable through the existing G01-006 (sign-in logs) endpoint. Establishes the minimum-viable attribution chain. |

---

## 5. Observability Mapping

The full machine-readable mapping is in `config/scenarios/observability_map.json`. The summary is:

| Scenario | Classification | Evidence Endpoints | Notes |
|---|---|---|---|
| `SCN-MAIL-001` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event for test-user-01 is expected. Mail content is NOT collected. |
| `SCN-MAIL-002` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event for test-user-01. Subject text is not visible to the collector. |
| `SCN-CALENDAR-001` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. The event itself is not collected. |
| `SCN-CALENDAR-002` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. |
| `SCN-CALENDAR-003` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. |
| `SCN-FILE-001` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. The file content is not collected. |
| `SCN-FILE-002` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. |
| `SCN-FILE-003` | INDIRECTLY_OBSERVABLE | G01-006, G01-005 | Sign-in event only. |
| `SCN-AUTH-001` | **DIRECTLY_OBSERVABLE** | G01-006 | The sign-in event itself is expected to appear in G01-006. |

### 5.1 Critical Disclaimer

**Sending mail does NOT automatically cause the action to appear in any G01 endpoint.** The only event consistently captured by the current G01 inventory is the sign-in event itself (G01-006). All other claims of observability are downstream side-effects at best. The full evidence is the sign-in log; the scenario artifact (mail, calendar event, file) is not part of G01.

> **No scenario is currently classified as `NOT_COVERED_BY_CURRENT_G01_INVENTORY`** because every scenario is expected to produce a sign-in event. However, the strong-form claim "this scenario is observable" should be qualified: observability is via the sign-in log, not via the workload-specific G01 endpoint.

---

## 6. Actor Requirements

The catalog uses a closed set of logical actor aliases. UPN resolution is deferred to runtime configuration. Passwords, secrets, and actual UPNs are not stored in the catalog.

| Alias | Role | Used By |
|---|---|---|
| `test-user-01` | Primary actor | All scenarios |
| `test-user-02` | Peer actor | `SCN-MAIL-001`, `SCN-MAIL-002` |
| `test-user-03` | Reserved | (unused) |

The full actor model is in `config/scenarios/actor_model.json`.

---

## 7. Correlation Strategy

Each scenario declares a `correlation_strategy` and a `correlation_token_field`. The runner is responsible for generating the actual token value; the catalog only declares its location.

| Scenario | Correlation Token Field | Purpose |
|---|---|---|
| `SCN-MAIL-001` | `subject_prefix` | Marker in the subject line that lets the operator identify the scenario run. |
| `SCN-MAIL-002` | `subject_line` | Full subject line carries the correlation token. |
| `SCN-CALENDAR-001` | `event_subject` | Event subject carries the token. |
| `SCN-CALENDAR-002` | `event_subject` | Updated subject retains the token with an `updated` marker. |
| `SCN-CALENDAR-003` | `event_subject` | Identifier used to match the event to delete. |
| `SCN-FILE-001` | `file_name` | File name carries the token. |
| `SCN-FILE-002` | `file_name` | File name is preserved; content is updated. |
| `SCN-FILE-003` | `file_name` | Identifier used to match the file to delete. |
| `SCN-AUTH-001` | `signin_event_id` | Pair `(event_time, user_id)` from G01-006. |

The correlation token is **not** a G01 field. It is documented in the scenario evidence record written by the runner.

---

## 8. Cleanup Behavior

Every scenario that creates persistent content declares a cleanup behavior. No cleanup is executed by this task.

| Cleanup Behavior | Scenarios | Notes |
|---|---|---|
| `AUTO_CLEANUP_SUPPORTED` | `SCN-CALENDAR-001`, `SCN-CALENDAR-002`, `SCN-FILE-001`, `SCN-FILE-002` | A paired cleanup scenario exists (`SCN-CALENDAR-003`, `SCN-FILE-003`). |
| `MANUAL_CLEANUP` | `SCN-MAIL-001`, `SCN-MAIL-002` | The runner cannot reliably delete individual messages from another mailbox; the message is left in the recipient's mailbox and is documented in the scenario evidence record. |
| `NO_CLEANUP_REQUIRED` | `SCN-CALENDAR-003`, `SCN-FILE-003`, `SCN-AUTH-001` | The scenario is itself a cleanup, or the scenario creates no persistent content. |

---

## 9. Risk Classification

All scenarios are classified **LOW**. No `MODERATE` or `HIGH` scenarios are included in the initial catalog. The risk vocabulary is closed (`LOW`, `MODERATE`, `HIGH`).

| Scenario | Risk | Rationale |
|---|---|---|
| All 9 scenarios | LOW | Controlled, scoped to test-user-01's own resources. No privileged roles. No cross-user writes. No tenant administration. |

---

## 10. Enabled State

| Scenario | Enabled | Reason |
|---|---|---|
| `SCN-AUTH-001` | **Yes** | The only scenario that requires no additional delegated permission. Already supported by the `User.Read` baseline. |
| All other 8 scenarios | No | Each requires a `REQUIRED_NOT_GRANTED` permission. The app registration is not amended by this task. |

The Scenario Agent App registration is **not modified** by this task. Re-enabling the disabled scenarios requires a separate, approved permission grant task.

---

## 11. Items NOT Included

The following items are explicitly **not** in the catalog:

- **No Teams scenarios.** The G01 read-only inventory does not collect Teams messaging data. Observable evidence for a Teams scenario cannot be supported confidently from current project evidence. `PACK-TEAMS` is reserved but unused.
- **No admin / tenant-administration scenarios.** No directory mutation, no conditional access policy creation, no role assignment, no device management.
- **No destructive bulk operations.** No mailbox wipes, no mass file deletion, no bulk user removal.
- **No privileged role use.** No Global Administrator scenario, no Privileged Role Administrator scenario.
- **No offline scenario execution.** This task is design-only; no scenario is run.

---

## 12. Validation

| Check | Result |
|---|---|
| Catalog contains 8–12 scenarios | ✓ — 9 scenarios |
| Enabled scenarios are LOW risk only | ✓ — only `SCN-AUTH-001` is enabled |
| No destructive scenario is enabled | ✓ — 0 destructive scenarios enabled |
| Every scenario has a unique ID | ✓ |
| Every scenario has cleanup declared | ✓ |
| Every scenario has actor requirements | ✓ |
| Every scenario has correlation strategy | ✓ |
| Every scenario has observability classification | ✓ |
| No scenarios store credentials | ✓ |
| No wildcard / broad permission bundle | ✓ |
| Scenario Agent App registration unmodified | ✓ |

---

## 13. Blockers

**None.** The catalog is design-only. All required permissions are clearly identified. No live Graph calls, no tenant writes, no permission grants are performed by this task.