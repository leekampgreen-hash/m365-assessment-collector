# EX-P02A Exchange Basic Protection Scope Closure

- **Task ID:** `EX-P02A-BASIC-PROTECTION-SCOPE-CLOSURE-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Role:** DOCUMENTATION_HANDOVER
- **Result:** `EX_P02A_PASS`

## Decision

Exchange Basic Protection aggregate expansion is **DEFERRED**. No supported Microsoft Graph aggregate or low-volume source passed the Basic architecture gate.

The earlier `EX-P02 BLOCKED_AUTH` classification is superseded for quarantine by `EX-P02C`: quarantine is a `BASIC/EOP` service capability, while unattended app-only collection is `ARCHITECTURE_BLOCKED` at the supported-platform boundary. It is not unfinished implementation or technical debt.

## Quarantine architecture disposition

- `service_capability`: `BASIC/EOP`
- `collector_status`: `ARCHITECTURE_BLOCKED`
- `blocker_type`: `SUPPORTED_PLATFORM_BOUNDARY`
- `technical_debt`: `NO`
- `future_reopen_condition`: Microsoft provides a supported app-only quarantine authorization/API, or the project explicitly approves delegated-user collection.

Exchange Online PowerShell app-only authentication supports `Exchange.ManageAsApp`, but that permission does not itself authorize quarantine access. Read-only quarantine authorization is documented for Security Reader, Global Reader, or Security Operator user/admin access; no documented supported service-principal authorization model exists for `Get-QuarantineMessage`. Exchange custom RBAC quarantine permissions are obsolete/unsupported, and no documented GA Exchange Admin API quarantine endpoint is available. Undocumented or Preview workarounds are excluded.

No dedicated EXO app, certificate, `Exchange.ManageAsApp` grant, broad Entra role, or PowerShell adapter is to be created for this closure.

## Capability disposition

| Capability | Basic disposition | Reason or future phase |
|---|---|---|
| Spam Filtered | DEFER | No supported Basic aggregate source passed the gate |
| Quarantined | ARCHITECTURE_BLOCKED | BASIC/EOP capability; unattended app-only collection lacks a documented supported authorization/API; reopen only for supported app-only authorization/API or explicitly approved delegated-user collection |
| Phishing Detected | DEFER | Defender phase |
| Malware Detected | DEFER | Defender phase |
| Spoof Detected | DEFER | Defender phase |
| Top Senders | DROP | Message-level source required |
| Top Sender Domains | DROP | Message-level source required |
| Top Recipients | DROP | Message-level source required |
| Top Threat Recipients | DEFER | Defender phase |
| Top Source IP | DROP | Message-level source required |

## Locked Exchange Basic capability

The following capability is locked, implemented, and accepted:

- Storage Used
- Mailbox Capacity / Quota
- Utilization %
- LOW / MEDIUM / HIGH / NO DATA
- Report Refresh Date

## Follow-up accounting

EX-P03 through EX-P09 are **NOT REQUIRED** for Basic because no new protection source passed the data-source gate. Exchange Online PowerShell quarantine integration and Defender telemetry remain future/deferred work.

This record is documentation-only. No implementation, UX, permission, authentication, or source behavior changed. No token or credit data is recorded.

## Final status

`EX_P02A_PASS`
