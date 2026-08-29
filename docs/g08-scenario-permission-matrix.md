# G08-B Scenario Permission Matrix

> **Baseline:** Scenario Agent App current state = delegated `User.Read` only.
> **Authority:** `docs/auth-app-registration-design.md` §4 ("Scenario Agent Permission Model").
> **Catalog source:** `config/scenarios/catalog.json` and `config/scenarios/permission_packs.json`.
> **Workflow State:** OFFLINE DESIGN — no permissions have been granted, modified, or expanded by this task.

---

## 1. Scenario Agent App — Current Delegated Permissions

The Scenario Agent App registration is **not modified by this task**. Its current delegated permission state, derived from the authority document above, is:

| Permission | Type | Source | Consent | Status |
|---|---|---|---|---|
| `User.Read` | Delegated | Scenario Agent App baseline (G04-001) | Individual user consent | GRANTED (baseline) |

There are no other delegated or application permissions currently on the Scenario Agent App.

The Collector App permission set (`docs/permission-matrix.md`) is **not** relevant to this matrix. The Scenario Agent App is a separate registration.

---

## 2. Per-Scenario Permission Requirement

| Scenario ID | Delegated Permission Required | Why It Is Required | Current Scenario App Has It | Consent Impact | Permission Expansion Required | Pack |
|---|---|---|---|---|---|---|
| `SCN-MAIL-001` | `Mail.Send` | Send a test email on behalf of test-user-01. `Mail.Send` is the minimum scope that permits `POST /me/sendMail`. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-MAIL` |
| `SCN-MAIL-002` | `Mail.Send` | Send a correlation-tagged test email on behalf of test-user-01. Same justification as `SCN-MAIL-001`. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-MAIL` |
| `SCN-CALENDAR-001` | `Calendars.ReadWrite` | Create a calendar event in test-user-01's calendar. `Calendars.Read` is insufficient because the action is a write. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-CALENDAR` |
| `SCN-CALENDAR-002` | `Calendars.ReadWrite` | Update an existing calendar event. Write is required. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-CALENDAR` |
| `SCN-CALENDAR-003` | `Calendars.ReadWrite` | Delete a scenario-created calendar event. Write is required. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-CALENDAR` |
| `SCN-FILE-001` | `Files.ReadWrite` | Create a small file in test-user-01's OneDrive. `Files.Read` is insufficient. `Sites.ReadWrite.All` is not required because the action is scoped to the user's own drive. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-FILES` |
| `SCN-FILE-002` | `Files.ReadWrite` | Update an existing test file in test-user-01's OneDrive. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-FILES` |
| `SCN-FILE-003` | `Files.ReadWrite` | Delete a scenario-created test file in test-user-01's OneDrive. | No | Requires new delegated grant | YES — REQUIRED_NOT_GRANTED | `PACK-FILES` |
| `SCN-AUTH-001` | _(none — `User.Read` baseline is sufficient)_ | Operator-driven interactive sign-in. The scenario itself performs no programmatic Graph action. Observability flows through `G01-006`, captured by the Collector App (not the Scenario Agent App). | Yes (baseline sufficient) | None | NO — NO_EXPANSION_REQUIRED | `PACK-AUTH` |

**Total new delegated permissions required across all scenarios: 3**

1. `Mail.Send`
2. `Calendars.ReadWrite`
3. `Files.ReadWrite`

All three are flagged `REQUIRED_NOT_GRANTED` in `config/scenarios/catalog.json` and `config/scenarios/permission_packs.json`. None of them are granted by this task.

---

## 3. Permission Packs

Permissions are grouped into small, additive, least-privilege packs. No single pack is a broad wildcard bundle.

| Pack | Delegated Permissions | Scenarios Enabled | Expected Blast Radius | Status |
|---|---|---|---|---|
| `PACK-AUTH` | _(none — baseline only)_ | `SCN-AUTH-001` | One operator sign-in event attributed to a test user. | NO_EXPANSION_REQUIRED |
| `PACK-MAIL` | `Mail.Send` | `SCN-MAIL-001`, `SCN-MAIL-002` | test-user-01 can send mail from their own mailbox to peers defined by the scenario. No mailbox read/write. | REQUIRED_NOT_GRANTED |
| `PACK-CALENDAR` | `Calendars.ReadWrite` | `SCN-CALENDAR-001`, `SCN-CALENDAR-002`, `SCN-CALENDAR-003` | test-user-01 can create, update, and delete events in their own calendar. | REQUIRED_NOT_GRANTED |
| `PACK-FILES` | `Files.ReadWrite` | `SCN-FILE-001`, `SCN-FILE-002`, `SCN-FILE-003` | test-user-01 can create, update, and delete small files in their own OneDrive. Does not include `Sites.ReadWrite.All`. | REQUIRED_NOT_GRANTED |
| `PACK-TEAMS` | _(reserved)_ `ChatMessage.Send`, `ChannelMessage.Send` | _(no scenarios enabled)_ | Reserved. Not activated; not requested. | DEFERRED |

### 3.1 Pack Activation Policy

- Packs are activated **one at a time**.
- A pack is activated only by a separate, approved task that explicitly amends the Scenario Agent App registration.
- This task does not activate any pack.
- `PACK-TEAMS` is reserved; it must not be activated until observability evidence for Teams activity is added to the G01 inventory.

---

## 4. Least-Privilege Notes

- **No wildcard scopes.** No pack requests `*.ReadWrite.All`, `Directory.*`, or any tenant-wide scope.
- **No broad bundles.** `Mail.Send` is not bundled with `Mail.Read` or `Mail.ReadWrite`. `Calendars.ReadWrite` is not bundled with `Mail.*` or `Files.*`.
- **No mailbox read access.** `Mail.Send` is the only mail-related permission requested; the scenarios never read another user's mailbox.
- **No tenant write access.** No pack requests `Directory.ReadWrite.All`, `RoleManagement.ReadWrite.Directory`, or any administrative scope.
- **No application permissions.** All requested scopes are *delegated*, not application. The Scenario Agent App does not request application permissions.
- **No admin accounts.** No scenario uses Global Administrator, Privileged Role Administrator, or any privileged role holder.

---

## 5. Permission Status Vocabulary

| Status | Meaning |
|---|---|
| `GRANTED` | The Scenario Agent App currently has the permission. |
| `REQUIRED_NOT_GRANTED` | The scenario requires the permission, but the Scenario Agent App does not have it. This is the only truthful state for `Mail.Send`, `Calendars.ReadWrite`, and `Files.ReadWrite`. |
| `NO_EXPANSION_REQUIRED` | The scenario requires no additional permission beyond the `User.Read` baseline. |
| `DEFERRED` | The pack exists in the catalog for future expansion but no scenario in the current catalog requires it. |

---

## 6. Validation

| Check | Result |
|---|---|
| Current Scenario App permissions listed | ✓ — `User.Read` only |
| Every scenario lists its permission requirement | ✓ — 9 scenarios |
| No permission is marked `GRANTED` unless supported by evidence | ✓ — only `User.Read` is granted; all others are `REQUIRED_NOT_GRANTED` |
| No broad wildcard bundle present | ✓ — no `*.ReadWrite.All`, no `Directory.*` |
| Pack activation policy is additive and one-at-a-time | ✓ — see §3.1 |
| Scenario Agent App registration not modified | ✓ — this task is design-only |
| Tenant / Entra ID not modified | ✓ — this task is offline |
| No secrets, credentials, tokens, or UPNs stored | ✓ — see `config/scenarios/actor_model.json` |

---

## 7. Blockers

**None.** All required permissions are clearly identified. The Scenario Agent App registration is unmodified. No live consent flow is initiated. Pack activation is explicitly deferred to a separate, approved task.