# OD-P06E OneDrive audit direct transport retry correction

TASK_ID: OD-P06E-ONEDRIVE-AUDIT-DIRECT-TRANSPORT-RETRY-CORRECTION-001
RESULT: OD_P06E_PASS
DATE: 2026-08-29

ROOT_CAUSE:
- function: `ManagementActivityTransport._get`
- uninitialized_variable: `error`
- failing_path: Direct `AuditTransportError` raised for HTTP 429, transient 5xx, 401/403, and blob/source failures.
- reason: `except AuditTransportError as error: pass` allowed CPython to clear the exception target after the clause, before retry classification dereferenced it.

CORRECTION:
- exact_change: Changed the handler to `except AuditTransportError as exc: error = exc`.
- semantics_changed: None beyond correcting the proven crash; existing retry, status, Retry-After, exhaustion, permission, source, HTTPError, and timeout semantics remain.
- unrelated_refactor: None.

RETRY_MATRIX:
- direct_429: retryable and bounded; eventual success passes.
- retry_after: direct 429 Retry-After path exercised and delay captured.
- direct_5xx: retryable and eventual success passes.
- retry_exhaustion: repeated direct 429/5xx return RETRY_EXHAUSTED after four attempts.
- direct_401: PERMISSION_REQUIRED, one attempt.
- direct_403: PERMISSION_REQUIRED, one attempt.
- source_failure: original direct source failure remains authoritative through bounded retry classification; no UnboundLocalError.
- urllib_HTTPError: existing 429 bounded path passes.
- timeout: existing bounded path passes.

UNBOUNDLOCALERROR:
- reproduced_before: YES, proven by OD-P06D.
- reproduced_after: NO.

TESTS:
- environment: host Python 3.13 equivalent; runtime bind mount verified in graph-agent-collector-dev.
- focused: `tests.integration.test_onedrive_audit_transport_retry` — PASS.
- integration: `tests.integration.test_onedrive_audit_production_path` — PASS.
- regression: Focused command 10/10 PASS; direct auth/persistence regression not rerun because this transport-only correction does not alter those paths; no broad regression.
- result: PASS.

RUNTIME_PARITY:
- source_hash: `9fb4e4d28dfb6ab3b9819b95c901b4e7f22439491447f4ff0e3921ffa5e368a2`
- runtime_hash: `9fb4e4d28dfb6ab3b9819b95c901b4e7f22439491447f4ff0e3921ffa5e368a2`
- result: PASS; bind-mounted runtime already matched, so no recreation performed.

PRODUCTION_CODE_CHANGED: YES
FILES_CHANGED:
- collectors/onedrive_audit.py
- tests/integration/test_onedrive_audit_transport_retry.py
- docs/evidence/OD-P06E-ONEDRIVE-AUDIT-DIRECT-TRANSPORT-RETRY-CORRECTION-001.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md

REAL_DEFECT_CORRECTED: YES
READY_FOR_OD_P06_ACCEPTANCE_RESUME: YES
FINAL_STATUS: OD_P06E_PASS
