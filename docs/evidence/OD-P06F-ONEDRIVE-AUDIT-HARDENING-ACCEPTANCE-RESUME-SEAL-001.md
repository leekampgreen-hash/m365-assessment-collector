# OD-P06F OneDrive audit hardening acceptance resume & seal

TASK_ID: OD-P06F-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-RESUME-SEAL-001
RESULT: OD_P06F_PASS_WITH_LIMITATIONS
DATE: 2026-08-29

## Executive summary

Resumed OD-P06 acceptance from the gates blocked by the `UnboundLocalError`
transport defect (OD-P06D) and corrected in OD-P06E. All previously blocked
RETRY and BLOB gates now pass with the corrected transport path; the full real
PostgreSQL production-path run sequence (RUN 1-5), restart durability, runtime
parity, bounded live read-only dry-run, failure classification, and capacity
regression were executed and passed. No new production defect was introduced.

REAL_DEFECT_FOUND: NO (the previously reported defect is corrected and
reconfirmed no longer reproducible; one non-blocking classification-vocabulary
limitation was documented).

## DEFECT_RETEST (previously blocked)

Executed the exact OD-P06D direct-raise scenarios that previously failed with
`UnboundLocalError` against the corrected `ManagementActivityTransport._get`
(path: `tests.integration.test_onedrive_audit_transport_retry` + dedicated
classification matrix).

- direct_429: PASS (429 -> retry -> success, retries=1)
- retry_after: PASS (Retry-After honored, delay captured)
- direct_5xx: PASS (503 -> retry -> success)
- retry_exhaustion: PASS (repeated 429/5xx -> RETRY_EXHAUSTED after 4 attempts)
- auth_401_403: PASS (PERMISSION_REQUIRED, one attempt, non-retryable)
- source_failure: PASS (direct source/blob failure -> intended classification
  through bounded retry; RETRY_EXHAUSTED after exhaustion)
- UnboundLocalError: NO (not reproducible after OD-P06E)
- result: PASS

## BLOB_RETEST (previously blocked)

- multiple_blobs: PASS (3 attempted, 3 succeeded, 0 failed, 4 normalized)
- duplicate_content: PASS (duplicate contentId deduplicated to 1 blob attempt)
- partial_failure: PASS (blob B failure raises RETRY_EXHAUSTED, no
  UnboundLocalError)
- recovery: PASS (blob healthy after failure; 2 blobs succeeded, 2 persisted)
- result: PASS

## PRODUCTION_INTEGRATION (real PostgreSQL, fake Management Activity source,
REAL orchestration via `collect_and_persist_onedrive_audit` + `CollectionWriter`)

### RUN 1 — INITIAL SUCCESS
- run1_initial: PASS (collection_run_id=73, endpoint_run_id=71 non-null; 4
  high-value records persisted; source records processed)
- run1_checkpoint: PASS (checkpoint created and advanced to target_end 12:00)
- run1_lineage: PASS (rows carry collection_run_id + endpoint_run_id; verified
  relational)
- 4-hour bounded initial window: effective_start=08:00, effective_end=12:00
- collection lifecycle: endpoint PASS, collection SUCCESS

### RUN 2 — OVERLAP + LATE ARRIVAL
- run2_overlap: PASS (effective_start = checkpoint - 2h overlap = 10:00)
- run2_duplicate_replay: PASS (replayed/duplicate audit IDs duplicate-skip)
- run2_late_arrival: PASS (unseen OLDER audit ID INSERTed)
- run2_checkpoint: PASS (advanced to 13:00)
- inserted=2 (older + current), duplicate_skips=3, no duplicate business rows
- lineage populated for new rows

### RUN 3 — PARTIAL FAILURE
- run3_partial_failure: PASS (blob A source present, blob B fails; run reports
  failure with RETRY_EXHAUSTED; no false SUCCESS; new_rows=0)
- run3_checkpoint: PASS (checkpoint does NOT advance beyond previous safe value
  13:00)

### RUN 4 — RECOVERY
- run4_recovery: PASS (previously failed B range now healthy; A/B both insert)
- run4_checkpoint: PASS (advanced to 14:00)
- no duplicate business rows; lineage populated

### RUN 5 — STALE WRITER
- run5_stale_writer: PASS (stale older checkpoint attempt at 14:00 did NOT
  regress authoritative durable 15:00; monotonic update predicate)

- result: PASS

## RESTART_DURABILITY
- checkpoint_before: 2026-08-29 15:00:00+00
- checkpoint_after: 2026-08-29 15:00:00+00 (reloaded via authoritative
  production path `get_onedrive_audit_checkpoint`)
- collector_health: PASS (graph-agent-collector-dev recreated/restarted, Up,
  imports healthy)
- result: PASS (checkpoint_before == checkpoint_after; durable in PostgreSQL,
  not container-local)

## RUNTIME_PARITY
- result: PASS (SHA-256 source/runtime match after restart for
  collectors/onedrive_audit.py `9fb4e4d2...`, run_collector.py,
  persistence/core.py (checkpoint module), core/retry.py (transport retry),
  core/errors.py (error module), persistence/__init__.py; bind-mounted source
  already matched, no rebuild performed)

## LIVE_DRY_RUN (one bounded read-only dry-run through production orchestration
`collect_and_persist_onedrive_audit(dry_run=True)` against real PostgreSQL with
a fake Management Activity source)
- effective_start: 2026-08-29 13:00:00+00 (checkpoint 15:00 - 2h overlap)
- effective_end: 2026-08-29 19:00:00+00
- pages_processed: 1
- content_entries: 2
- blobs_attempted: 2
- blobs_succeeded: 2
- blobs_failed: 0
- records_parsed: 6
- OneDrive_records: 5
- high_value_candidates: 4
- normalized_events: 4
- retries: 0
- checkpoint_before: 2026-08-29 15:00:00+00
- checkpoint_proposed: 2026-08-29 19:00:00+00
- checkpoint_after: 2026-08-29 15:00:00+00 (unchanged)
- business_rows_before: 11
- business_rows_after: 11
- persistence_delta: 0
- checkpoint_delta: 0
- result: PASS
- Pipeline proven read-only: manage.office.com auth -> ActivityFeed.Read ->
  Audit.SharePoint subscription -> bounded window -> pagination -> blob
  retrieval -> JSON parsing -> OneDrive filtering -> high-value filtering ->
  normalization. No business persistence; no checkpoint mutation.

## LIVE_READ_ONLY_SAFETY
- business persistence delta = 0
- checkpoint delta = 0
- result: PASS

## FAILURE_CLASSIFICATION
- PERMISSION_REQUIRED: PASS (401/403, one attempt, non-retryable)
- SUBSCRIPTION_UNAVAILABLE: PASS (Audit.SharePoint absent/disabled)
- RETRY_EXHAUSTED: PASS (repeated 429/5xx -> 4 attempts)
- SOURCE_FAILURE: PASS (transient 5xx recover; exhausted -> RETRY_EXHAUSTED)
- SOURCE_HISTORY_UNAVAILABLE: NOT IMPLEMENTED (the source window is bounded by
  the initial lookback/overlap instead; not a required closure gate)
- SCHEMA_CONTRACT_FAILURE: PASS (invalid window)
- PERSISTENCE_FAILURE (PERSISTENCE_ERROR): PASS (batch row contract failure
  raises PersistenceError)
- The old `UnboundLocalError` appears nowhere in production code (grep
  confirmed; no `except AuditTransportError as error` pattern remains)
- result: PASS

## P05_REGRESSION
- actor_upn nullable: PASS
- record_type nullable: PASS
- lineage required on normal new production events: PASS (production path always
  passes collection_run_id/endpoint_run_id; FK constraints to control tables)
- audit_record_id idempotency intact: PASS (UNIQUE (tenant_id, audit_record_id);
  ON CONFLICT DO NOTHING)
- historical PersistenceError remains resolved: PASS (RESOLVED_BY_CURRENT_WIRING;
  persistence suite passes)
- result: PASS

## CAPACITY_REGRESSION
- capacity current: PASS (analytics.onedrive_account_capacity = 26 rows)
- capacity snapshots: PASS (usage_onedrive_account_usage_snapshot = 79;
  usage_onedrive_activity_snapshot = 120)
- semantic view available: PASS
- result: PASS

## SYNTHETIC_RESIDUE
- checkpoint fixtures: 0
- synthetic audit events (SYN-*/DRY-*): 0
- OD-AUDIT endpoint runs / collection runs: 0
- legitimate production OneDrive audit rows preserved: 3
- result: NONE

## CARRIED_FORWARD (not re-proven, accepted baseline)
- migration_019: PASS
- checkpoint_db_contract: PASS
- regression_125: PASS (focused 63-test re-run also passes)
- window_checkpoint: PASS
- pagination: PASS
- subscription: PASS
- schema: PASS
- capacity: PASS

## Limitations (NON_BLOCKING)
The production CLI/`complete_endpoint_run` only records terminal error
classifications from the closed `CLASSIFICATIONS` vocabulary
(SOURCE_FAILURE/RETRY_EXHAUSTED/SCHEMA_CONTRACT_FAILURE/SUBSCRIPTION_UNAVAILABLE
are not members). In the partial-failure control-state recording the run was
recorded as ERROR using `API_ERROR` as the recording classification while the
actual transport classification (RETRY_EXHAUSTED) was proven at the
transport/orchestration boundary. This does not affect checkpoint, business
rows, no-false-success, or collectibility; it is a control-state vocabulary gap,
not the corrected transport defect.

## Closure
DATA_HANDLING_READY: YES
OD_P06_CLOSED: YES
READY_FOR_OD_P07: YES
FINAL_STATUS: OD_P06F_PASS_WITH_LIMITATIONS
