# OD-P06D OneDrive audit hardening acceptance execution

TASK_ID: OD-P06D-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-EXECUTION-001
RESULT: OD_P06D_BLOCKED
DATE: 2026-08-29

## Executive summary

Execution of the remaining OD-P06 acceptance gates began by exercising the
focused hardening matrix against the current production transport. A **REAL
production defect** was found in the Management Activity retry path that
blocks the RETRY and BLOB acceptance scenarios (and therefore also RUN 3
partial-failure / RUN 4 recovery production-path scenarios). Per task
instructions, implementation was **NOT** performed to correct it; this
evidence records the defect with an exact reproduction.

REAL_OD_P06_DEFECT_FOUND: YES

## Defect: UnboundLocalError in Management Activity retry handling

### Location

`collectors/onedrive_audit.py`, `ManagementActivityTransport._get`, lines
120-124.

```python
            except AuditTransportError as error:
                pass
            ...
            decision = self.retry_policy.should_retry(
                error.classification,
                retry_after=error.retry_after,
                attempts_so_far=attempts,
            )
```

### Root cause

CPython deletes the exception-target name bound by an `except X as name:`
clause as soon as that clause finishes executing (to break the reference
cycle). Because the throttled/transient error is bound directly to `error`
via `except AuditTransportError as error:`, `error` is unbound by the time
line 124 dereferences `error.classification`, raising `UnboundLocalError`.

This only affects the **direct-raise** path where `AuditTransportError` is
raised from the `status == 429` / `500 <= status < 600` / blob-failure
raises. The urllib `HTTPError` path binds `error` through assignment
(`error = AuditTransportError(...)`) and therefore works, which is why prior
focused tests that exercised retries through urllib-style `HTTPError`
responses passed and masked the defect.

### Reproduction (minimal)

A transport whose `url_open` returns a status-429 response (rather than
raising `urllib.error.HTTPError`) reproduces the crash:

```python
class StatusResponse:
    status = 200
    def __init__(self, status):
        self.status = status
    def read(self):
        return b"[{}]"

seq = {"n": 0}
def opener(request, timeout=None):
    if request.full_url.endswith("/token"):
        return StatusResponse(200)
    seq["n"] += 1
    if seq["n"] == 1:
        return StatusResponse(429)   # throttled
    return StatusResponse(200)

transport = ManagementActivityTransport("t", lambda: "tok", url_open=opener, sleep=lambda s: None)
transport._get("https://manage.office.com/api/v1.0/t/activity/feed/subscriptions/list")
```

Result:

```
Traceback (most recent call last):
  File "collectors/onedrive_audit.py", line 124, in _get
    decision = self.retry_policy.should_retry(error.classification, retry_after=error.retry_after, attempts_so_far=attempts)
              ^^^^^
UnboundLocalError: cannot access local variable 'error' where it is not associated with a value
```

### Affected required scenarios (all FAIL)

- RETRY: 429 then success -> FAIL (crashes before the second attempt)
- RETRY: Retry-After honored -> FAIL (decision never reached)
- RETRY: transient 5xx then success -> FAIL (same crash on status 503)
- RETRY: retry exhaustion bounded -> FAIL for the direct-raise path
- BLOB: partial blob failure / recovery-replay after failure -> FAIL (a
  blob `_get` that raises `AuditTransportError("SOURCE_FAILURE", ...)`
  crashes identically at `collectors/onedrive_audit.py:158 -> _get -> 124`)

### Not affected

- RETRY: 401/403 non-retryable -> the direct `status == 401/403` raise is
  never retried (the decision line is reached only if the error variable
  were bound; here it still raises UnboundLocalError before any retry, but
  the classification intent is non-retryable).
  NOTE: even for 401/403 the direct-raise path still crashes with
  UnboundLocalError rather than surfacing `PERMISSION_REQUIRED` cleanly.
- RETRY: transient timeout bounded -> works; `TimeoutError` is caught by the
  `except (TimeoutError, ...) as exc:` clause which binds `error` via
  assignment, so the timeout path retries then raises `RETRY_EXHAUSTED`
  correctly.
- ManagementActivityTransport and orchestration not reached by this defect
  (subscription enabled, pagination multi-page/cyclic/bound, duplicate
  contentId, malformed blob rejection, schema handling) were exercised and
  behaved correctly.

## Verified-pass matrix items (unaffected by the defect)

A TEST-ONLY harness (removed after use to preserve the 125/125 baseline)
confirmed the following current-code behaviors:

- WINDOW: no-checkpoint first run bounded to a 4-hour initial lookback; prior
  checkpoint yields `effective_start = checkpoint - 2h` overlap; malformed /
  reversed / naive UTC windows rejected with `SCHEMA_CONTRACT_FAILURE`;
  invalid overlap bounds rejected.
- CHECKPOINT: successful / empty / duplicate-only / out-of-scope-only runs
  advance; dry-run does not persist and does not advance; persistence failure
  does not advance; auth/subscription failure does not advance.
- LATE ARRIVAL: replayed audit IDs produce normalized candidates (dedup is
  authoritative at persistence `ON CONFLICT`); previously unseen older
  event_time records are normalized without watermark filtering.
- PAGINATION: multiple pages followed; cyclic NextPageUri rejected
  (`SCHEMA_CONTRACT_FAILURE`); page-count bound enforced (`SOURCE_FAILURE`).
- BLOB (non-failure): multiple blobs; duplicate contentId skipped; malformed
  blob rejected (`SCHEMA_CONTRACT_FAILURE`).
- SUBSCRIPTION: enabled accepted; absent/disabled -> `SUBSCRIPTION_UNAVAILABLE`.
- SCHEMA: malformed locked candidate -> `SCHEMA_CONTRACT_FAILURE`; normal
  out-of-scope OneDrive record drops to None.
- RETRY timeout path: bounded retries then `RETRY_EXHAUSTED`.

## Impact on remaining gates

Because the RETRY and BLOB-failure scenarios are required gates, and because
RUN 3 (partial failure) and RUN 4 (recovery) production-path scenarios depend
on correct blob-failure handling through the same `_get` path, the real
PostgreSQL production-path runs 1-5, restart durability, live read-only
dry-run, and closure gates remain BLOCKED pending correction of this defect.

## Safety

- No production code was modified in this task.
- A TEST-ONLY harness was used to exercise the matrix and then removed;
  `tests.integration.test_onedrive_audit_production_path` still passes 3/3.
- No synthetic residue, tenant mutation, permission/subscription change,
  sharing event, malware generation, or token/credit logging.

## Decision

OD_P06_CLOSED: NO
DATA_HANDLING_READY: NO
READY_FOR_OD_P07: NO
FINAL_STATUS: OD_P06D_BLOCKED

FILES_CHANGED:
- docs/evidence/OD-P06D-ONEDRIVE-AUDIT-HARDENING-ACCEPTANCE-EXECUTION-001.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md
