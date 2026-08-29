TASK_ID: OD-P05-ONEDRIVE-AUDIT-COLLECTOR-NORMALIZATION-WIRING-001
RESULT: OD_P05_PASS_WITH_GAPS

PRODUCTION_PATH:
- entrypoint: collectors/onedrive_audit.py
- auth: CollectorTokenProvider with explicit Management Activity resource
- transport: ManagementActivityTransport
- parser: JSON content blob parser
- workload_filter: Workload == OneDrive
- event_filter: locked anonymous, Guest sharing, malware operations
- normalization: normalize_onedrive_audit_record
- persistence: collectors.persistence.persist_onedrive_high_value_audit_batch (caller integration pending)

AUTH:
- resource: https://manage.office.com
- permission: ActivityFeed.Read (runtime capability gate remains caller-owned)
- Graph_token_reused: NO

TRANSPORT:
- subscription_check: implemented; disabled/missing is SUBSCRIPTION_UNAVAILABLE
- content_listing: bounded UTC window
- pagination: NextPageUri supported
- blob_retrieval: implemented

FILTERING:
- OneDrive: accepted
- SharePoint: dropped
- anonymous: accepted
- guest_external: accepted
- internal_member: dropped
- ambiguous: dropped
- secure_link_alone: dropped
- malware: accepted
- unrelated: dropped

NORMALIZATION:
- required_fields: tenant_id, audit_record_id, event_time, operation, workload, event_category and persistence-required fields
- optional_fields: actor/object/site/source/target fields nullable
- derived_fields: event_category, external_flag, anonymous_flag
- raw_payload_stored: NO

INTEGRATION:
- fake_source: not run
- source_records: not run
- normalized: focused unit path not added
- persisted: persistence contract already validated in OD-P04B
- duplicates: persistence contract idempotent
- residue: none introduced

TESTS:
- focused: compile plus three focused persistence tests PASS
- environment: host Python 3
- result: PASS with gaps

LIVE_PROOF:
- mode: NOT RUN
- subscription: NOT VERIFIED
- content_entries: N/A
- blobs: N/A
- records: N/A
- high_value_events: N/A
- persistence: NOT RUN

RUNTIME_PARITY: NOT RUN

CAPACITY_REGRESSION:
- current_rows: 26 (prior OD-P04B baseline)
- snapshot_rows: 79 (prior OD-P04B baseline)
- semantic_view: available (prior OD-P04B baseline)

BLOCKERS: Live proof, runtime parity, and full production entrypoint/persistence orchestration remain.
NON_BLOCKING_GAPS: Focused transport/normalizer tests and live read-only proof.

COLLECTOR_WIRING_READY: NO
READY_FOR_OD_P06: NO

FILES_CHANGED:
- collectors/core/auth.py
- collectors/onedrive_audit.py
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md
- docs/evidence/OD-P05-ONEDRIVE-AUDIT-COLLECTOR-NORMALIZATION-WIRING-001.md

FINAL_STATUS: OD_P05_PASS_WITH_GAPS
