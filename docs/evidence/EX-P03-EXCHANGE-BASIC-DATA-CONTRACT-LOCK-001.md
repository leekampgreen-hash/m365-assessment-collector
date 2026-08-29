# EX-P03 Exchange Basic Data Contract Lock

- **Task ID:** `EX-P03-EXCHANGE-BASIC-DATA-CONTRACT-LOCK-001`
- **Date:** 2026-08-29
- **Project:** graph-agent
- **Role:** `ARCHITECTURE`
- **Result:** `EX_P03_PASS`

## Supported data contract

The canonical Exchange Basic record is one mailbox per tenant and normalized mailbox identity, sourced from the accepted Microsoft Graph usage report `getMailboxUsageDetail(period=D7)` (`USAGE-003`). The current accepted production path is the report collector, normalization, current persistence, snapshot persistence, and capacity semantic view.

| Field | Source/report | Source field | Normalized field | Datatype | Grain | Authority | Null semantics | Timestamp semantics |
|---|---|---|---|---|---|---|---|---|
| Mailbox identity / UPN | Graph Exchange mailbox usage detail (`USAGE-003`) | `User Principal Name` | `identity_value` / `user_principal_name` | text | one mailbox/user per tenant | authoritative | required for resolvable identity; masked/unavailable identity remains unresolved and is not fabricated | no event timestamp implied |
| Storage used | same report | `Storage Used (Byte)` | `storage_used` | BIGINT bytes | one mailbox per tenant | authoritative | NULL when absent or invalid; never coerced from invalid input | observed collection time is `observed_at`; not report freshness |
| Mailbox capacity / quota | same report | `Prohibit Send/Receive Quota (Byte)` | `mailbox_capacity` derived from `prohibit_send_receive_quota` | BIGINT bytes | one mailbox per tenant | source quota authoritative; normalized capacity projection | NULL when absent or invalid; Send/Receive Quota is prohibited as denominator | observed collection time is `observed_at`; not report freshness |
| Utilization | capacity semantic layer `analytics.exchange_mailbox_capacity` | derived from valid source values | `utilization_percent` | numeric percentage | one mailbox per tenant | derived | NULL when storage or capacity is missing/invalid or capacity <= 0 | uses the source report generation, not activity time |
| Usage level | capacity semantic layer | derived from utilization | `usage_level` enum text: LOW/MEDIUM/HIGH/NO_DATA | text enum | one mailbox per tenant | derived | `NO_DATA` when required source values are missing/invalid or capacity <= 0 | uses the source report generation, not activity time |
| Report refresh date | same report | `Report Refresh Date` / `Data Last Refreshed` | `report_refresh_date` | date | report generation applied to each mailbox row | authoritative source/report freshness | NULL when source field is absent or invalid | source/report freshness date; do not replace with `last_activity_date` / Last Activity |

`last_activity_date` remains a separate activity field and is not part of the capacity refresh timestamp contract.

## Capacity semantics

- **Authoritative denominator:** `mailbox_capacity = prohibit_send_receive_quota`.
- **Prohibited denominator:** `prohibit_send_quota` / Send/Receive Quota is not an acceptable substitute.
- **Utilization:** `storage_used / mailbox_capacity * 100`.
- **Thresholds:** `LOW < 50%`; `MEDIUM >= 50% and < 80%`; `HIGH >= 80%`.
- **NO_DATA:** required source values missing/invalid or `mailbox_capacity <= 0`.
- No license-based quota inference is permitted.
- `report_refresh_date` is source/report freshness. Last Activity must not be substituted as refresh timestamp.

## Basic protection gap register

| Metric | Service capability | Collector status | Blocker / disposition | Gap class |
|---|---|---|---|---|
| Spam Filtered | BASIC/EOP | `DATA_SOURCE_PENDING` | No approved aggregate Microsoft Graph path or other approved low-volume source | DATA_SOURCE_PENDING |
| Quarantine | BASIC/EOP | `ARCHITECTURE_BLOCKED` | Supported Microsoft app-only authorization/API unavailable; delegated collection is not approved | PLATFORM_BLOCKED |
| Phishing | BASIC/EOP capability; richer telemetry is Defender | `DATA_SOURCE_PENDING` | Current approved Basic collector source unavailable; Defender telemetry is outside Basic | DATA_SOURCE_PENDING |
| Malware | BASIC/EOP capability; richer telemetry is Defender | `DATA_SOURCE_PENDING` | Current approved Basic collector source unavailable; Defender telemetry is outside Basic | DATA_SOURCE_PENDING |
| Spoof | BASIC/EOP capability; richer telemetry is Defender | `DATA_SOURCE_PENDING` | Current approved Basic collector source unavailable; Defender telemetry is outside Basic | DATA_SOURCE_PENDING |

Basic EOP capability is not mislabeled as Defender-only. Defender telemetry remains a separate richer-data phase.

## Message-level exclusions

The Basic collector is explicitly locked out of raw Message Trace, per-message lifecycle/event/action, per-user sent/read/received activity, Top Senders, Top Sender Domains, Top Recipients, and Top Source IP. These require message-level/high-volume ingestion and are `EXCLUDED_BY_SCOPE`, not missing Basic implementation.

## Current production path

`Graph usage report (USAGE-003 / getMailboxUsageDetail D7)` → `collector` → `normalization` → `core.usage_exchange_mailbox_usage` current table → `core.usage_exchange_mailbox_usage_snapshot` snapshot table → `analytics.exchange_mailbox_capacity` capacity semantic layer.

The current and snapshot tables are authoritative persistence; the analytical view is the single derived capacity contract. No UX, collector, permission, or API discovery work is introduced by this lock.

## Gap classification

- `SUPPORTED_READY`: mailbox identity/UPN, storage_used, mailbox_capacity, report_refresh_date, current/snapshot persistence, utilization, usage_level, and capacity semantic layer.
- `PLATFORM_BLOCKED`: Quarantine collection.
- `DATA_SOURCE_PENDING`: Spam Filtered, Phishing, Malware, Spoof aggregate collection.
- `EXCLUDED_BY_SCOPE`: all message-level exclusions listed above.
- `DEFERRED`: richer Defender telemetry and any future approved protection expansion.

## Final status

`EXCHANGE_DATA_CONTRACT_LOCKED: YES`

**Blockers:** Quarantine supported app-only authorization/API unavailable.

**Non-blocking:** Protection aggregate sources pending; excluded message-level metrics.

**Deferred:** Defender telemetry and future approved protection expansion.

**Next required task:** `EX-P04 persistence/current/history reconciliation`

No token or credit data is recorded.
