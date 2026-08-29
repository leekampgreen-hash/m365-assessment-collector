# TD-006 Retry Recovery Hardening Plan

- **Usage mark:** `TD-006-RETRY-RECOVERY-HARDENING-PLAN-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `OPERATIONAL_DESIGN`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Improve operational resilience and recovery visibility for the G01-002 through G01-012 workloads. The future capability should make transient failures distinguishable from permanent failures, show whether recovery was attempted, and provide enough bounded evidence for an operator or future agent to determine the next action.

Retry behavior already exists in the collection flow, but recovery evidence and operational guidance are limited. This plan hardens the policy and evidence contract around that behavior; it does not change the current retry implementation.

This is a documentation and design plan only. It does not authorize changes to collectors, adapters, registry, persistence runtime, or database migrations.

## 2. Failure Classification

Classification must be assigned at the authoritative failure boundary and must not be inferred from free-form exception text alone. A retry is appropriate only when the failure category is explicitly retryable and the operation remains within its time and attempt budget.

### Retryable

The following conditions may be retried when the request or transaction has not produced an acknowledged durable result:

- **HTTP throttling:** Graph responses such as HTTP 429, honoring `Retry-After` when present.
- **Temporary Graph availability issue:** transient service-side failures such as HTTP 5xx or an explicitly classified temporary availability response.
- **Transient network failure:** connection reset, timeout during an otherwise safe request, DNS/connectivity interruption, or equivalent transport failure.
- **Temporary database connection issue:** recoverable connection acquisition or connection-loss failure before the collection result is durably committed.

Retry evidence must preserve the original category even when all attempts are exhausted. A retry must not be used to bypass validation, tenant checks, authorization checks, transaction boundaries, or idempotency rules.

### Permanent

The following conditions must fail without retry unless a separately approved operator workflow changes the underlying configuration or input:

- **Invalid permission:** the application lacks the required Graph permission or consent.
- **Tenant mismatch:** trusted runtime tenant lineage does not match the expected tenant.
- **Malformed data:** response, page, record, or normalized input violates the approved structure or required-field contract.
- **Schema violation:** a normalized record cannot satisfy the approved persistence schema or closed mapping.

Permanent failures require correction, review, or a controlled re-run. Repeatedly retrying them would add load, obscure the cause, and could produce misleading recovery status.

## 3. Retry Strategy

The following policy is the proposed baseline for future implementation. Exact values must be confirmed against service limits, workload duration, and the existing runtime's configuration before implementation.

### Retry count

- Allow a bounded maximum of **3 retries after the initial attempt**, for at most **4 total attempts** for one retryable operation.
- Count attempts per endpoint operation and collection run, not globally across unrelated workloads.
- Do not reset the counter merely because a page, connection, or sub-operation changes; the evidence must retain the complete run-level attempt history.
- A permanent failure consumes no retry budget.

### Backoff concept

- Use bounded exponential backoff with jitter to avoid synchronized retries.
- Prefer the server-provided `Retry-After` delay for HTTP throttling when valid, subject to an approved maximum wait.
- Apply a maximum backoff and a total retry time budget so a run cannot wait indefinitely.
- Record the delay decision as bounded metadata, such as delay class or duration, rather than copying response headers or diagnostic payloads.

### Timeout handling

- Apply an explicit request, connection, and overall operation timeout.
- Treat a timeout as retryable only when it is classified as a transient network or temporary service condition and the operation has not been durably acknowledged.
- Stop retrying when the overall timeout or run deadline is reached, even if retry attempts remain.
- Ensure timeout and cancellation paths release resources and preserve transaction rollback and no-partial-write behavior.

### Failure escalation

- After the retry budget or time budget is exhausted, mark the operation as failed with its final failure category and `RETRY_EXHAUSTED` or `TIMEOUT_BUDGET_EXCEEDED` outcome.
- Escalate permanent failures immediately with a corrective action appropriate to the category.
- Escalate repeated retry exhaustion for the same endpoint or tenant through future alert integration, using bounded dimensions and redacted identifiers.
- A recovery workflow or manual re-run must be idempotent and must use the existing tenant, validation, and persistence safeguards.

## 4. Recovery Evidence

Each failed or recovered operation should produce a structured, redacted recovery record. The minimum evidence contract is:

- `endpoint`: stable endpoint identity from the registry or collector context;
- `execution_id` or `collection_run_id`: identifier for the execution/run;
- `failure_category`: controlled retryable or permanent category;
- `retry_attempts`: initial attempt plus retry count, bounded to the configured maximum;
- `final_status`: for example `RECOVERED`, `FAILED_RETRY_EXHAUSTED`, `FAILED_PERMANENT`, or `CANCELLED`;
- `recommended_action`: bounded operator guidance, such as `RETRY_RUN`, `CHECK_GRAPH_PERMISSION`, `VERIFY_TENANT_CONTEXT`, `INSPECT_INPUT_CONTRACT`, or `CHECK_DATABASE_AVAILABILITY`.

Optional safe fields may include UTC timestamps, bounded duration, final HTTP status class, timeout indicator, and a redacted correlation identifier. Evidence should also distinguish a failed page/request from a rolled-back collection transaction and from a successful recovery after retry.

Do not capture:

- tokens;
- credentials;
- secrets;
- authorization headers or connection strings; or
- sensitive or raw payload data.

Endpoint names, categories, statuses, action codes, and error classifications must be allowlisted. Free-form exception messages, URLs with query data, SQL parameters, response bodies, and headers require redaction and normalization before any future telemetry or evidence sink accepts them.

## 5. Agentic Operations Use Case

A future operations agent can answer the following questions by querying bounded recovery evidence and correlating it with collection-run metadata:

- **Why did collection fail?** Identify the endpoint and final failure category, then report the normalized failure reason and whether the failure was retryable or permanent. For a retryable failure, include whether the service, network, or database exhausted its budget. For a permanent failure, provide the corresponding corrective action.
- **Was retry attempted?** Compare the recorded initial attempt and retry count, report the final attempt number, and distinguish `RECOVERED` from exhausted or cancelled outcomes.
- **Is manual intervention required?** Recommend automatic re-run for an exhausted transient condition when policy permits; require manual correction for invalid permission, tenant mismatch, malformed data, or schema violation. The agent should state when evidence is incomplete rather than infer a cause.

The agent must never answer these questions by exposing tokens, credentials, secrets, raw payloads, or unrestricted exception text. It should provide endpoint, run, category, attempt, status, and action evidence only.

## 6. Implementation Considerations

Possible future implementation work, each requiring separate approval and validation, includes:

- **Retry metrics:** counters for attempts, recoveries, exhausted retries, permanent failures, and timeout outcomes with bounded labels for endpoint and failure category.
- **Failure dashboard:** views for retry rate, recovery rate, retry exhaustion, permanent failure trends, and oldest unresolved recovery evidence.
- **Alert integration:** alerts for sustained throttling, Graph availability degradation, repeated network/database failures, and new permanent-failure patterns, with deduplication and redacted content.
- **Recovery workflow:** controlled re-run or operator workflow that validates classification, preserves idempotency, enforces tenant boundaries, and records the resulting status.

Implementation should first confirm where the existing retry and collection-run context can safely emit structured evidence. The smallest compatible extension is preferred. Any persistence of recovery evidence requires separate retention, access-control, classification, and migration review. None of these items is implemented by this plan.

## 7. Limitations and Decision

TD-006 is **DOCUMENTED / PLANNED**. Retry behavior exists, but the proposed retry-count baseline, bounded backoff and timeout policy, structured recovery evidence, metrics, dashboard, alerting, and recovery workflow are not claimed to exist. Production implementation requires a separately approved task and must preserve fail-closed validation, tenant isolation, transaction safety, and sensitive-data exclusion.
