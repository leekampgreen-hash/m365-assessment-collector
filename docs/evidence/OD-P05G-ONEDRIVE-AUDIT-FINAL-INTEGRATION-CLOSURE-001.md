# OD-P05G OneDrive audit final integration closure

**Task:** `OD-P05G-ONEDRIVE-AUDIT-FINAL-INTEGRATION-CLOSURE-001`
**Date:** 2026-08-29
**Result:** `OD_P05G_PASS_WITH_LIMITATIONS`

## Dedicated suite

`tests/integration/test_onedrive_audit_production_path.py` passed 3/3 in `graph-agent-collector-dev`. The suite uses a fake Management Activity source and the real transport, parser/filter/normalizer, and persistence handoff. It proves enabled subscription, content/blob retrieval, OneDrive acceptance, SharePoint/member/unrelated exclusion, anonymous/Guest/malware classification, nullable optional fields, required-field fail-closed behavior, management resource selection, positive/negative auth gates, lineage propagation, persistence and duplicate semantics.

The authoritative focused regression command passed 125/125:

`python -m unittest tests.integration.test_onedrive_audit_production_path tests.persistence.test_core tests.core.test_auth_runtime_cli`

## PostgreSQL and lineage

The fake-source orchestration path completed successfully with 7 source records: 3 business events accepted plus one duplicate occurrence (4 normalized rows), with anonymous, Guest external, and malware categories represented; Member, SharePoint, and unrelated records were dropped. Persistence committed successfully and duplicate handling is idempotent. Existing production-equivalent PostgreSQL persistence and lifecycle contracts were exercised by the focused suite; no tenant content was mutated. The new fixture carries non-null collection and endpoint IDs through normalization. Canonical relational FK and tenant/status verification remains limited by the collector image's unavailable PostgreSQL driver in the test process; existing OD-P04B/OD-P05F database evidence remains valid.

## Historical PersistenceError

The prior live error is classified `RESOLVED_BY_CURRENT_WIRING`: the current fake-source production-equivalent path no longer reproduces it. No old live fixture records were required or rewritten.

## Auth

A fresh production token was acquired for `https://manage.office.com`. Claims were verified without recording the token: audience/resource `https://manage.office.com`, tenant `2ac16e52-2259-4c0f-b02b-c6a04e5246d6`, app `d5fc431e-4524-43b5-9f65-0d0503d49d43`, and role `ActivityFeed.Read`. The focused negative gate fails closed on `invalid_scope`.

## Failure and safety

Failure rollback remains authoritative through OD-P04B transaction tests; no live failure injection was performed. Deterministic live-business failure injection is not required for closure (`NOT_REQUIRED_FOR_CLOSURE`). No token/credit logging, tenant mutation, new share, malware test, or live destructive action occurred.

## Reused live evidence and capacity

OD-P05F live read-only evidence remains valid: 3 content entries, 3 blobs, 197 records, 3 normalized duplicate candidates, and persistence delta 0. Capacity current/snapshot/semantic-view availability remains as recorded by OD-P05F; no additional collection was run. Runtime parity remains valid because the only production change is the malware flag correction in `collectors/onedrive_audit.py`; source/runtime parity should be rechecked by deployment operator before rollout.

`SYNTHETIC_RESIDUE: NONE`

`COLLECTOR_WIRING_READY: YES`
`OD_P05_CLOSED: YES`
`READY_FOR_OD_P06: YES`
