# EX-P10 Exchange Basic Seal

- **Task ID:** `EX-P10-EXCHANGE-BASIC-SEAL-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Model:** `9router/my_ulti`
- **Result:** `EX_P10_SEALED`

## Final workstream status

- EX-P01: PASS
- EX-P02: CLOSED — quarantine architecture/platform boundary proven
- EX-P03: PASS
- EX-P04: PASS
- EX-P05: PASS
- EX-P06: PASS after validation closure
- EX-P07: PASS
- EX-P08: PASS
- EX-P09: PASS
- EX-R01: PASS_WITH_NON_BLOCKING_FINDING

**EXCHANGE BASIC:** SEALED / ACCEPTED

## Supported capability

- mailbox identity / UPN
- storage used
- mailbox capacity = `prohibit_send_receive_quota`
- utilization percentage
- `LOW` / `MEDIUM` / `HIGH` / `NO_DATA`
- report refresh date

## Protection boundary

- Spam: BASIC/EOP capability; `DATA_SOURCE_PENDING`.
- Quarantine: BASIC/EOP capability; `ARCHITECTURE_BLOCKED` by the supported platform boundary; not technical debt.
- Phishing, Malware, and Spoof: Basic EOP protection capability acknowledged; aggregate collector source pending; richer Defender telemetry deferred.

## Exclusions

Raw Message Trace; per-message lifecycle/event/action; per-user sent/read/received activity; Top Senders; Top Sender Domains; Top Recipients; Top Source IP.

## Accepted production evidence

The latest accepted state is 30 current Exchange rows and 30 semantic rows: `LOW=30`, `MEDIUM=0`, `HIGH=0`, `NO_DATA=0`, refresh `2026-08-26`, and Mailbox Capacity Risk `0`. Runtime parity is PASS and the production API is READY. These counts and the timestamp are acceptance evidence, not hardcoded future expectations.

## EX-P06 reconciliation

EX-P06 initially remained BLOCKED at validation. Validation subsequently CLOSED/PASS through EX-P06A and later EX-P07B integration and EX-P08 live evidence; production behavior is confirmed correct. The original EX-P06 evidence remains historically truthful and is not rewritten as an original pass.

## Scope accounting

Documentation/handover only. No production code, tests, UX, feature, permission, tenant, or token/credit behavior changed.
