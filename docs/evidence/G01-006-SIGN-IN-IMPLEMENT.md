# G01-006 Sign-In Logs Implementation Evidence

- **Usage mark:** `G01-006-SIGN-IN-IMPLEMENT-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Result:** `PASS`

## Contract Verified

- Graph endpoint: `GET /v1.0/auditLogs/signIns`.
- Permission: `AuditLog.Read.All`.
- Inventory contract: application auth, paginated collection, approved sign-in `$select` fields, and configured Graph `$top`.
- Adapter: `collectors/workloads/security_service/adapters.py`, function `adapt_sign_in_logs`.
- Registry: `G01-006` -> `EVENT`, owner `security_service`, target `core.audit_event`, event source `SIGN_IN`, retention `HIGH_SENSITIVITY`.
- Persistence: existing `dispatch_persistence`, security boundary, `write_event_record`, and transactional `CollectionWriter`; no new writer, migration, or dispatcher redesign.
- Conflict key: `(tenant_id, event_source, source_object_id)` with `ON CONFLICT DO NOTHING` replay semantics.

## Field And Security Boundary

The adapter projects only `id`, `createdDateTime`, `userId`, `appId`, `status.errorCode`, `status.failureReason`, `status.additionalDetails`, `clientAppUsed`, and `isInteractive` into the approved event row shape. `failureReason` takes precedence over `additionalDetails`; scalar numeric error codes are retained as text. `event_source` is always `SIGN_IN`, so input event-source values cannot spoof another stream.

Missing IDs and malformed non-mapping records fail closed. Unknown fields, IP/location data, user-agent data, correlation data, credentials, tokens, and authorization material are not copied. Tenant IDs are validated against the trusted collection tenant before transaction start.

## Pagination And Failure Semantics

The shared paginator follows every string `@odata.nextLink`, accepts an empty `value` list as a successful empty collection, and rejects missing/non-list `value` and malformed next-link fields. A failed page leaves the collection unsuccessful; the runtime does not normalize or persist a partial successful batch.

## Tests Executed

```text
python3 -m unittest tests.workloads.security_service.test_adapters tests.workloads.test_registry tests.workloads.test_integration tests.core.test_collector_framework tests.core.test_g09_r2_normalization_handoff tests.persistence.test_core tests.persistence.test_g01_015_event
```

Result: **256 tests passed**.

Coverage includes successful normalization, nested status mapping and fallback, pagination, empty result, malformed response, missing ID, approved-field projection, credential exclusion, event-source spoofing, duplicate replay, tenant boundary, parameter-bound SQL, and transactional rollback/no partial write behavior.

Full discovery ran 602 tests; 599 passed and 3 unrelated `scenario.live` interactive-auth/network tests failed (`AUTH_DEVICE_CODE_ERROR` plus mocked socket/request expectation failures). No G01-006 test failed.

## Limitations

The evidence is offline. It does not exercise live Microsoft Graph credentials or a live PostgreSQL instance.
