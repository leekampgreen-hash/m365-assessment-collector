# Exchange Progress

Exchange phases and related Exchange Standard progress.

## EX-P10 Exchange Basic seal / handover

**Task:** `EX-P10-EXCHANGE-BASIC-SEAL-001`
**Status:** `EXCHANGE BASIC: SEALED / ACCEPTED`

Final status: EX-P01 PASS; EX-P02 CLOSED/PASS; EX-P03 PASS; EX-P04 PASS;
EX-P05 PASS; EX-P06 PASS AFTER VALIDATION CLOSURE; EX-P07 PASS; EX-P08 PASS;
EX-P09 PASS; EX-R01 `PASS_WITH_NON_BLOCKING_FINDING`. There is no open
production blocker.

Supported Exchange Basic contract: mailbox identity/UPN, storage used, mailbox
capacity from `prohibit_send_receive_quota`, utilization percentage,
`LOW`/`MEDIUM`/`HIGH`/`NO_DATA`, and report refresh date. The authoritative
semantic layer is `analytics.exchange_mailbox_capacity`; Mailbox Capacity Risk
is `count(usage_level = HIGH)`.

Protection boundary: Spam is BASIC/EOP and `DATA_SOURCE_PENDING`; Quarantine is
BASIC/EOP and `ARCHITECTURE_BLOCKED` by the supported platform boundary, not
technical debt; Phishing/Malware/Spoof have Basic EOP capability acknowledged,
with aggregate collector source pending and advanced Defender telemetry
 deferred. These are not Exchange Basic closure blockers.

Exclusions remain raw Message Trace, per-message lifecycle/event/action,
per-user sent/read/received activity, Top Senders, Top Sender Domains,
Top Recipients, Top Source IP, advanced Defender telemetry, and UX redesign.

Accepted evidence: current rows 30, semantic rows 30, duplicate rows 0,
LOW=30, MEDIUM=0, HIGH=0, NO_DATA=0, latest refresh `2026-08-26`, Mailbox
Capacity Risk=0, runtime parity PASS, production API READY, and bounded live
Graph acceptance PASS. These counts and timestamp are acceptance evidence, not
hardcoded future expectations.

EX-P06 chronology is preserved: implemented; initial validation blocked; validation
subsequently CLOSED/PASS through EX-P06A; production behavior later re-proven by
EX-P07B/EX-P08. EX-R01 found no dropped capability, production wiring regression,
persistence regression, runtime drift, or deferred-feature dependency. Its sole
NON_BLOCKING finding was EX-P06 documentation-status drift, closed by EX-P10.

Scope: documentation/handover only; no production source, tests, UX, feature, or
service rebuild changed.

## EX-P02C Exchange quarantine architecture closure

**Task:** `EX-P02C-QUARANTINE-ARCHITECTURE-CLOSURE-001`  
**Status:** `EX_P02C_PASS`

Quarantine is a **BASIC/EOP service capability**, but unattended app-only collection is **ARCHITECTURE_BLOCKED** under the currently supported Microsoft interfaces. This is a supported-platform boundary, not unfinished implementation and not technical debt.

**Authorization and interface evidence:**

- Exchange Online PowerShell app-only authentication supports `Exchange.ManageAsApp`.
- `Exchange.ManageAsApp` does not itself authorize quarantine access.
- Documented read-only quarantine authorization is available to Security Reader, Global Reader, or Security Operator user/admin access.
- No documented supported service-principal authorization model exists for `Get-QuarantineMessage`.
- Exchange custom RBAC quarantine permissions are obsolete/unsupported.
- No documented GA Exchange Admin API quarantine endpoint is available.
- Undocumented or Preview workarounds are excluded.

**Quarantine lock:**

- Service capability: `BASIC/EOP`
- Collector status: `ARCHITECTURE_BLOCKED`
- Blocker type: `SUPPORTED_PLATFORM_BOUNDARY`
- Technical debt: `NO`
- Future reopen condition: Microsoft provides a supported app-only quarantine authorization/API, or the project explicitly approves delegated-user collection.

No dedicated EXO app, certificate, `Exchange.ManageAsApp` grant, broad Entra role, or PowerShell adapter is to be created for this closure. EX-P02 is closed; EX-P03 through EX-P09 remain not required for Basic. No implementation, UX, tenant mutation, permission, credential, or source behavior changed.

Evidence: `docs/evidence/EX-P02A-BASIC-PROTECTION-SCOPE-CLOSURE-001.md`.
