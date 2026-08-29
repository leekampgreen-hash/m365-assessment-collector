# STD-15G Exchange Storage Usage Correction

- **Task ID:** `STD-15G-EXCHANGE-STORAGE-USAGE-CORRECTION-001`
- **Date:** 2026-08-28
- **Project:** graph-agent
- **Role:** `EXCHANGE_USAGE_CAPACITY_CORRECTION`
- **Result:** `STD_15G2_READY`

## Live source inspection

The earlier absence statement is superseded by this bounded read-only inspection through `graph-agent-collector-dev`, using the configured production auth path and `getMailboxUsageDetail(period='D7')`. The live CSV contained 30 rows and the following sanitized evidence:

| Field | Header | Populated | Blank | Numeric when populated |
|---|---|---:|---:|---:|
| Report Refresh Date | YES | 30 | 0 | N/A |
| Storage Used (Byte) | YES | 30 | 0 | 30/30 |
| Issue Warning Quota (Byte) | YES | 30 | 0 | 30/30 |
| Prohibit Send Quota (Byte) | YES | 30 | 0 | 30/30 |
| Prohibit Send/Receive Quota (Byte) | YES | 30 | 0 | 30/30 |

`Report Refresh Date` was `2026-08-25` for all populated rows. No identities or raw CSV rows were printed. The established collector CLI also completed `USAGE-003` with `status=PASS`, `source_rows=30`, and `persisted_rows=30`.

This live evidence supersedes the earlier statement that the quota fields were absent. `Prohibit Send/Receive Quota (Byte)` is reliably populated and numerically parseable, so the source is ready for STD-15G2 wiring.

## Decision

No denominator can be proven. Mailbox capacity cannot be inferred from SKU/license type. Therefore LOW/MEDIUM/HIGH storage-utilization classification was not implemented, and no Exchange, OneDrive, SharePoint, SEND_MAIL, license, or unrelated backend semantics were changed.

## Required semantics status

- Storage used source: `USAGE-003` / `Storage Used` -> `storage_used`
- Capacity source: unavailable in accepted authoritative evidence
- Denominator semantics: no proven per-mailbox quota/capacity denominator
- Reliability: insufficient; fail closed as `NO DATA`
- License inference used: `NO`
- Refresh/as-of correction: not implemented because the capacity contract is blocked

## Files changed

- `docs/evidence/STD-15G-EXCHANGE-STORAGE-USAGE-CORRECTION-001.md`
- `docs/PROJECT_PROGRESS.md`
- `docs/AI_USAGE_LOG.md`

No production code was changed.
