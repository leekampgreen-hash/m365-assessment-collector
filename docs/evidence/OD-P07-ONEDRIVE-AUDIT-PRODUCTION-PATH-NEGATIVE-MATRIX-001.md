# OD-P07 OneDrive audit PRODUCTION-PATH negative matrix

**Task:** `OD-P07-ONEDRIVE-AUDIT-PRODUCTION-PATH-NEGATIVE-MATRIX-001`
**Date:** 2026-08-29
**Result:** `OD_P07_BLOCKED` — REAL_DEFECT_FOUND = YES
**Final status rationale:** One REAL production observability/classification defect is
found in `collectors/onedrive_audit.py`. Per the task instruction (section 17) it is
reported and **not auto-fixed**. Every business-persistence, checkpoint, lifecycle,
tenant-isolation, and no-false-success gate PASSES; the single failing gate is the
safe-drop observability classification.

## 1. PRODUCTION-PATH FIXTURE

- FAKE Management Activity API (`url_open` injectable fake, including token,
  subscriptions/list, content listing, content blob)
- REAL production orchestration `collect_and_persist_onedrive_audit`
- REAL `ManagementActivityTransport` + `normalize_onedrive_audit_record`
- REAL `CollectionWriter` lifecycle (`begin_collection_run` →
  `begin_endpoint_run` → `collect_and_persist` → `complete_endpoint_run` →
  `complete_collection_run`)
- REAL PostgreSQL (`graph_agent`), REAL `control.collector_checkpoint`,
  REAL `core.onedrive_high_value_audit_event` persistence
- No live Microsoft 365 call.
- Dedicated suite: `tests/integration/test_onedrive_audit_production_path_matrix.py`
  (data-driven; 18 tests).

Synthetic tenant fixtures `555001`/`555002` are used so the live tenant (id=2) is
never written by the matrix. The suite connects as `graph_agent_bootstrap` for
fixture setup/cleanup (runtime role has no DELETE on the audit table) and as
`graph_agent_runtime` for the production-path persistence (proving runtime-role
operation).

## 2. POSITIVE MATRIX (PASS)

Proves end-to-end persistence for `AnonymousLinkCreated`, structured Guest
external `SharingInvitationCreated`, and `FileMalwareDetected`.

- anonymous: EXTERNAL_SHARING, external=true, anonymous=true — PASS (exactly one
  business row, lineage non-null, tenant correct)
- guest_external: EXTERNAL_SHARING, external=true, anonymous=false — PASS
- malware: MALWARE_DETECTED, external=false, anonymous=false, no invented malware
  metadata — PASS
- result: **PASS** (persisted=3, checkpoint advanced)

## 3. SAFE-DROP MATRIX (BUSINESS PASS / CLASSIFICATION DEFECT)

- SharePoint workload external sharing → not persisted (PASS)
- OneDrive Member/internal sharing → not persisted (PASS business; **mis-counted
  as malformed**)
- ambiguous sharing target → not persisted (PASS business; **mis-counted as
  malformed**)
- SecureLinkCreated alone → not persisted (PASS)
- unrelated OneDrive operation → not persisted (PASS)
- generic file access/download/upload/modify → not persisted (PASS)

Business outcome PASS: normalized=0, persisted=0, no business rows, checkpoint
advances (successful source processing). **REAL DEFECT:** `malformed_records=2`
for the Member + ambiguous sharing records, where the locked contract requires
these to be classified as `records_dropped_out_of_scope` (not malformed). See
REAL_DEFECT_FOUND below.

## 4. MALFORMED LOCKED-CANDIDATE MATRIX (PASS)

Deterministically high-value candidates (Workload=OneDrive, Operation in locked
set) missing authoritative fields → `SCHEMA_CONTRACT_FAILURE`:
- missing audit Id → SCHEMA_CONTRACT_FAILURE (no row, no false SUCCESS, no
  checkpoint advance)
- missing CreationTime/event_time → SCHEMA_CONTRACT_FAILURE
- structurally invalid locked candidate → SCHEMA_CONTRACT_FAILURE
- missing Workload → locked OD-P03 fail-closed exclusion (safe drop, not
  persisted, not malformed) — PASS
- checkpoint: unchanged on every malformed failure — PASS

## 5. AUTH FAILURE (PASS)

Fake 403 on ActivityFeed.Read gate:
- classification: PERMISSION_REQUIRED
- persistence: none
- checkpoint: unchanged
- lifecycle: collection FAILED / endpoint ERROR; no false SUCCESS

## 6. SUBSCRIPTION FAILURE (PASS)

Fake Audit.SharePoint absent/disabled:
- classification: SUBSCRIPTION_UNAVAILABLE
- persistence: none
- checkpoint: unchanged
- lifecycle: failure recorded (control-state uses the documented OD-P06F
  `API_ERROR` workaround because SUBSCRIPTION_UNAVAILABLE is outside the closed
  `CLASSIFICATIONS` vocabulary; true classification proven at orchestration
  boundary)

## 7. SOURCE / TRANSPORT FAILURE (PASS)

One representative end-to-end case per class:
- retry exhaustion (repeated 5xx) → RETRY_EXHAUSTED, checkpoint unchanged
- malformed content blob (non-array) → SCHEMA_CONTRACT_FAILURE, checkpoint unchanged
- source failure before complete processing (2 blobs, second 503) → RETRY_EXHAUSTED,
  no false SUCCESS, checkpoint does not over-advance, no corrupted partial row,
  already-legitimate committed records remain replay-safe

## 8. PERSISTENCE FAILURE (PASS)

Deterministic fault injection at the production batch-INSERT boundary
(`_FailBatchConnection` proxy raising on the audit INSERT):
- classification: PERSISTENCE_ERROR
- partial_rows: NONE (no partial invalid business transaction)
- checkpoint: unchanged
- lifecycle: collection FAILED / endpoint ERROR

## 9. DUPLICATE / REPLAY MATRIX (PASS)

- same audit Id twice in same blob → one business row
- same audit Id across two blobs → one business row
- same audit Id across overlapping runs → one business row (duplicate skip)
- same timestamp/object different audit IDs → two independent business rows
- unseen older event during overlap → INSERT

## 10. TENANT ISOLATION (PASS)

At contract/DB level with synthetic tenants 555001/555002:
- same `audit_record_id` exists for different tenants (unique `(tenant_id, audit_record_id)`)
- checkpoint key is tenant scoped (`(tenant_id, collector_id)`)
- collection/endpoint lineage remains tenant consistent
- one tenant's checkpoint does not advance/regress another's

## 11. RUN LIFECYCLE (PASS)

- success → collection SUCCESS / endpoint PASS, lineage points to the correct run
- safe-drop success → collection SUCCESS / endpoint PASS
- auth failure → collection FAILED / endpoint ERROR
- subscription failure → collection FAILED / endpoint ERROR
- schema failure → collection FAILED / endpoint ERROR
- source failure → collection FAILED / endpoint ERROR
- persistence failure → collection FAILED / endpoint ERROR
- no false SUCCESS; row/result counts sensible

## 12. CHECKPOINT MATRIX (PASS)

- successful positive run → advances
- successful all-out-of-scope run → advances
- duplicate-only run → advances
- auth failure → unchanged
- subscription failure → unchanged
- schema failure → unchanged
- source failure → unchanged
- persistence failure → unchanged

## 13. OBSERVABILITY SANITY (PASS for all except the safe-drop malformed mis-count)

Distinguishes records_parsed / onedrive_records / high_value_candidates /
normalized / inserted / duplicate_skips / records_dropped_out_of_scope /
malformed_records / retries / checkpoint_before-after / final status. The only
ambiguity that blocks operations is the safe-drop `malformed_records` mis-count
(REAL DEFECT below). No new metrics were added.

## 14. TEST EXECUTION

- environment: `graph-agent-collector-dev`
- suite: `tests.integration.test_onedrive_audit_production_path_matrix`
- count: 18 tests
- result: 17 PASS, 1 FAIL (`test_safe_drop_matrix` — the defect reproduction)
- Focused OneDrive audit regression `tests.integration.test_onedrive_audit_production_path`
  (3 tests) and `tests.integration.test_onedrive_audit_transport_retry` remain
  unchanged and pass. No broad unrelated regression was run.

## 15. REAL POSTGRESQL VERIFICATION (PASS)

Queried real PostgreSQL for persisted business row counts, categories, tenant IDs,
audit IDs, lineage IDs, checkpoint state, and collection/endpoint run states for
every matrix case (not just mocked call assertions). Verified the live tenant's 3
legitimate rows are preserved and the synthetic tenants are removed.

## 16. SYNTHETIC CLEANUP (PASS)

Removed only OD-P07 synthetic business rows, checkpoint rows, collection runs,
endpoint runs, and the two synthetic tenant fixture rows. Verified:
`SYNTHETIC_RESIDUE = NONE`. Live tenant rows (3) preserved.

## 17. RUNTIME PARITY

No production source was changed. The suite is tests-only. The single finding is a
REAL DEFECT (below); per task instruction it is **not** corrected here.

## 18. NO LIVE TENANT ACCEPTANCE

No live Management Activity API call was made. OD-P08 remains the bounded live
acceptance task.

---

## REAL_DEFECT_FOUND = YES

**File:** `collectors/onedrive_audit.py`, `collect_and_persist_onedrive_audit`
normalization/metric counting loop (the `else` branch).

**Reproduction (end-to-end, real orchestration + real PostgreSQL):**

Source blob contains exactly two safe-drop records:
- `Workload=OneDrive, Operation=SharingInvitationCreated, TargetUserOrGroupType=Member`
- `Workload=OneDrive, Operation=SharingSet, TargetUserOrGroupType=None`

Observed metrics: `normalized=0`, `records_dropped_out_of_scope=0`,
`malformed_records=2`.

These records are intentionally dropped (correctly not persisted, no false
SUCCESS, checkpoint advances) — the business guarantee is correct. But they are
counted as `malformed_records` instead of `records_dropped_out_of_scope`.

**Root cause:** In the counting loop:

```python
if row is not None: normalized.append(row); metrics.high_value_candidates += 1
elif record.get("Workload") != "OneDrive" or record.get("Operation") not in {...}: metrics.records_dropped_out_of_scope += 1
else: metrics.malformed_records += 1
```

For a OneDrive `SharingInvitationCreated`/`SharingSet` whose target is not `Guest`
(Member/ambiguous), `normalize` returns `None`, `Workload == "OneDrive"` and the
Operation IS in the locked set, so the `elif` is false and the record falls into
`else: malformed_records += 1`. Genuine schema defects (missing `Id`/`CreationTime`
on a locked candidate) already raise `SCHEMA_CONTRACT_FAILURE` inside `normalize`
and never reach this `else`, so the `else` branch only ever sees valid-but-out-of-
scope internal/ambiguous sharing.

**Why it matters:** The locked OD-P03 contract and OD-P07 sections 3 and 13 require
Member/internal and ambiguous sharing to be dropped as out-of-scope and NOT
classified as malformed merely because they are out of scope. The current counter
misclassifies them, so the observability does not clearly distinguish dropped-out-
of-scope from malformed.

**Smallest correction recommendation (not applied):** Route the valid-but-out-of-
scope OneDrive sharing records to `records_dropped_out_of_scope`. Because genuine
schema defects already fail closed via `SCHEMA_CONTRACT_FAILURE` at normalization,
the `else` branch can be folded into the dropped-out-of-scope accounting, e.g.
make the `else` increment `metrics.records_dropped_out_of_scope` (or add an
explicit internal/ambiguous sharing classification) so `malformed_records` stays
reserved for actual data/schema defects. No change to persistence, checkpoint, or
no-false-success behavior is needed.

---

## BLOCKERS

One REAL defect (observability mis-classification above). Because correcting it
requires a production file change, and per the task instruction this is reported
and not auto-fixed, OD-P07 cannot close.

## NON_BLOCKING_LIMITATIONS

- `complete_endpoint_run` records only the closed `CLASSIFICATIONS` vocabulary; for
  SUBSCRIPTION_UNAVAILABLE / SCHEMA_CONTRACT_FAILURE / SOURCE_FAILURE / RETRY_EXHAUSTED
  the control-state is recorded with the documented `API_ERROR` workaround while the
  true classification is proven at the orchestration boundary (carried forward from
  OD-P06F; no effect on checkpoint/business/no-false-success/collectibility).
- Two-tenant live fixture is not required; tenant isolation proven at contract/DB level.

## RESULTS SUMMARY

- POSITIVE_MATRIX: anonymous=EXTERNAL_SHARING(external,anonymous) PASS;
  guest_external=EXTERNAL_SHARING(external,not anonymous) PASS;
  malware=MALWARE_DETECTED PASS; result=PASS
- SAFE_DROP_MATRIX: SharePoint PASS; internal_member PASS(business)/DEFECT(class);
  ambiguous PASS(business)/DEFECT(class); secure_link_only PASS; unrelated PASS;
  generic_activity PASS; result=PARTIAL (business PASS, classification DEFECT)
- MALFORMED_MATRIX: missing_id SCHEMA_CONTRACT_FAILURE PASS; missing_time
  SCHEMA_CONTRACT_FAILURE PASS; missing_workload fail-closed exclusion PASS;
  invalid_candidate SCHEMA_CONTRACT_FAILURE PASS; checkpoint unchanged PASS;
  result=PASS
- AUTH_FAILURE: classification PERMISSION_REQUIRED; persistence none;
  checkpoint unchanged; lifecycle FAILED/ERROR; result=PASS
- SUBSCRIPTION_FAILURE: classification SUBSCRIPTION_UNAVAILABLE; persistence none;
  checkpoint unchanged; lifecycle failure; result=PASS
- SOURCE_FAILURE: classification RETRY_EXHAUSTED/SCHEMA_CONTRACT_FAILURE;
  checkpoint unchanged; lifecycle failure; result=PASS
- PERSISTENCE_FAILURE: classification PERSISTENCE_ERROR; partial_rows NONE;
  checkpoint unchanged; lifecycle FAILED/ERROR; result=PASS
- REPLAY_MATRIX: same_blob 1 row; cross_blob 1 row; overlap 1 row;
  distinct_ids 2 rows; late_arrival INSERT; result=PASS
- TENANT_ISOLATION: business_key unique(tenant,audit_id) PASS; checkpoint
  tenant-scoped PASS; lineage tenant-consistent PASS; result=PASS
- RUN_LIFECYCLE: success PASS; safe_drop PASS; failures PASS; result=PASS
- CHECKPOINT_MATRIX: positive/out_of_scope/duplicate_only advance; failures
  unchanged; result=PASS
- POSTGRES_VERIFICATION: result=PASS
- TESTS: environment graph-agent-collector-dev; suite
  tests.integration.test_onedrive_audit_production_path_matrix; count 18; result
  17 PASS / 1 FAIL (defect reproduction)
- RUNTIME_PARITY: no production change; PASS
- SYNTHETIC_RESIDUE: NONE

## CLOSURE

- PRODUCTION_PATH_INTEGRATION_READY: NO (pending defect correction)
- OD_P07_CLOSED: NO
- READY_FOR_OD_P08: NO (do not start OD-P08 until defect is corrected and OD-P07
  re-sealed)

FINAL_STATUS: OD_P07_BLOCKED
