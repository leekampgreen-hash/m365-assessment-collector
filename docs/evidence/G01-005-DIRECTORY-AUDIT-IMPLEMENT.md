# G01-005 Directory Audit Implementation Evidence

- **Usage mark:** `G01-005-DIRECTORY-AUDIT-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/auditLogs/directoryAudits`.
- Permission: `AuditLog.Read.All`.
- Inventory contract: application auth, paginated collection, `$top=100`, and approved `$select` fields.
- Adapter: `collectors/workloads/security_service/adapters.py`, function `adapt_directory_audit_logs`.
- Registry: `G01-005` -> `EVENT`, owner `security_service`, target `core.audit_event`, event source `DIRECTORY_AUDIT`, retention `HIGH_SENSITIVITY`.
- Persistence: existing `dispatch_persistence`, security boundary, `write_event_record`, and transactional `CollectionWriter`; no new writer, migration, or dispatcher redesign.
- Conflict key: `(tenant_id, event_source, source_object_id)` with `ON CONFLICT DO NOTHING` replay semantics.

## Field and Security Boundary

The adapter projects only `id`, `activityDateTime`, `activityDisplayName`, `category`, `result`, and `loggedByService` into the approved event row shape. It forces `event_source` to `DIRECTORY_AUDIT`; input event-source values cannot spoof another stream. Missing IDs and non-mapping records fail closed. Unknown fields, tokens, credentials, and authorization material are not copied.

The registry controls the endpoint, persistence mode, target table, and event-source discriminator. Persistence uses closed SQL mappings and driver-bound values. Tenant IDs are validated against the trusted collection tenant before transaction start. A writer failure rolls the complete batch back.

## Pagination and Failure Semantics

The existing paginator follows every string `@odata.nextLink` and does not infer completion from page size. It now rejects missing/non-list `value` and non-string `@odata.nextLink` fields as API errors. A failed page leaves the collection unsuccessful, so the runtime does not normalize or persist a partial successful batch.

## Tests Executed

```text
python3 -m unittest tests.workloads.security_service.test_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core tests.persistence.test_g01_015_event
```

Result: **248 tests passed**.

Coverage includes pagination, empty result, malformed response, missing ID, unknown-field exclusion, credential exclusion, event-source spoofing, duplicate replay, tenant mismatch, parameter-bound SQL, registry alignment, and rollback. Full test discovery ran 599 tests with 596 passing and 3 unrelated `scenario.live` interactive-auth/network failures (`AUTH_DEVICE_CODE_ERROR` plus mocked socket/request expectation failures); no G01-005 test failed.

## Retention Metadata

The existing `HIGH_SENSITIVITY` registry retention value was preserved. No retention discrepancy was silently changed.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
