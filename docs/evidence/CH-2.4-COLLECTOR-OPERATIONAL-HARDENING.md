# CH-2.4 Collector Operational Hardening Design

- **Usage mark:** `CH-2.4-COLLECTOR-OPERATIONAL-HARDENING-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `OPERATIONAL_HARDENING`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Define the operational maturity target for the G01-002 through G01-012
collectors. The foundation already validates and rejects unsafe or malformed
input, but mature operations also require bounded evidence explaining what was
accepted, what was rejected, why collection failed, whether recovery was
attempted, and what action should happen next.

The target is observable, classifiable, recoverable collector operation without
weakening fail-closed validation, tenant isolation, transaction safety, or
sensitive-data controls. This document is a design only. It authorizes no
changes to collectors, adapters, registry runtime, persistence runtime, or
database migrations.

## 2. Current Limitation

Validation exists across the collector, adapter, security-boundary, and
persistence flows. Invalid records and unsafe operations are rejected rather
than silently accepted, and existing retry behavior handles eligible transient
conditions.

The operational limitation is visibility. Failure classification and recovery
context are not yet consistently exposed as bounded operational evidence. An
operator may know that a run failed without being able to reliably determine
whether the cause was data quality, security validation, throttling, a temporary
dependency issue, or a permanent configuration/input problem. Rejection trends,
retry outcomes, and recommended actions therefore remain difficult to measure
and automate.

## 3. Rejection Visibility Model

Future operational evidence should distinguish record outcomes from collection
and transaction outcomes. A record is **accepted** when it passes the approved
validation and security boundaries and is eligible for the existing persistence
flow. An accepted count should represent records handed forward by the
validated collection flow, not records inferred from raw payload size.

A record is **rejected** when it fails an authoritative validation or security
boundary and is not handed to persistence. Rejection evidence describes the
classification and safe reason, not the rejected object. A rejected record must
remain distinct from a failed batch, a rolled-back transaction, and a request
that ultimately recovers after retry.

Every rejection should use one controlled top-level category:

### DATA_VALIDATION

The record does not satisfy the approved input or normalized data contract,
including a missing required field, invalid type, malformed format, or invalid
structure.

### SECURITY_VALIDATION

The record or operation is rejected by a security boundary, including tenant
mismatch, forbidden field, or unauthorized source.

### SYSTEM

An operational condition prevents completion, such as a persistence or
transaction failure. System evidence must not relabel an earlier authoritative
data or security rejection.

Category and reason codes should be allowlisted and bounded. Free-form error
text may be retained only after redaction and normalization.

## 4. Retry Recovery Model

Classification must be assigned at the authoritative failure boundary. Retry is
permitted only for an explicitly retryable condition, while the operation is
within its attempt and time budgets and has not produced an acknowledged durable
result. Retry must never bypass validation, authorization, tenant checks,
transaction boundaries, or idempotency safeguards.

### Retryable

- **Throttling:** Graph rate limiting, such as HTTP 429, subject to bounded
  backoff and any valid `Retry-After` value.
- **Temporary Graph failure:** transient Graph service availability failures,
  such as classified HTTP 5xx responses.
- **Network issue:** transient connection reset, timeout, DNS, or equivalent
  transport failure.
- **Temporary database issue:** recoverable connection acquisition or connection
  loss before durable commit.

The original failure category must be retained when retries are exhausted. A
future implementation should use bounded exponential backoff with jitter,
explicit request/connection/operation timeouts, and a bounded total retry
budget.

### Permanent

- **Permission issue:** required Graph permission or consent is unavailable.
- **Tenant mismatch:** trusted runtime tenant lineage does not match the
  expected tenant.
- **Schema issue:** normalized data cannot satisfy the approved persistence
  schema or closed mapping.
- **Invalid data:** response, page, record, or normalized input violates the
  approved data contract.

Permanent failures should not consume retry budget. They require correction,
review, or a controlled re-run. A future recovery workflow must be idempotent
and retain the existing tenant and validation safeguards.

## 5. Operational Evidence

Future rejection and recovery evidence should use a common, structured,
redacted contract. Required fields are:

| Field | Meaning |
| --- | --- |
| `execution_id` | Stable identifier for the collector execution or run. |
| `endpoint` | Code-owned endpoint identity from collector or registry context. |
| `timestamp` | UTC time at which the operational outcome was recorded. |
| `failure_category` | Controlled rejection, retryable, permanent, or system category. |
| `failure_reason` | Bounded, normalized reason code or safe explanation. |
| `retry_attempts` | Initial attempt plus bounded retry count. |
| `final_status` | Outcome such as `ACCEPTED`, `REJECTED`, `RECOVERED`, `FAILED_RETRY_EXHAUSTED`, or `FAILED_PERMANENT`. |
| `recommended_action` | Bounded next action, such as `RETRY_RUN`, `CHECK_GRAPH_PERMISSION`, `VERIFY_TENANT_CONTEXT`, `INSPECT_INPUT_CONTRACT`, or `CHECK_DATABASE_AVAILABILITY`. |

Where useful, safe optional metadata may include a redacted correlation value,
bounded duration, HTTP status class, timeout indicator, accepted/rejected
counts, and a distinction between record rejection, request failure, and
transaction rollback. High-cardinality values should be omitted or replaced by
approved redacted references.

Evidence must exclude:

- tokens;
- secrets;
- credentials;
- authorization headers or connection strings; and
- raw sensitive payload or payload fragments.

URLs with query data, SQL parameters, exception text, response bodies, and
headers require redaction and normalization before any future evidence sink
accepts them.

## 6. Agentic Operations Readiness

The bounded rejection and recovery model establishes a safe foundation for a
future operations agent. By correlating `execution_id`, endpoint, timestamps,
categories, reasons, attempts, and final status, the agent could provide:

- **Failure explanation:** summarize whether the outcome was data validation,
  security validation, system, retryable, or permanent, with the normalized
  reason and affected execution.
- **Trend analysis:** compare accepted and rejected counts, rejection rates,
  retry attempts, recoveries, and exhausted failures over time by endpoint and
  bounded category/reason.
- **Recovery recommendation:** identify whether an automatic re-run is allowed
  or whether an operator must correct permission, tenant context, input, schema,
  or database availability first.

The agent must report incomplete evidence rather than infer a cause. It must
never answer by exposing tokens, secrets, credentials, raw payloads, or
unredacted diagnostic text.

## 7. Future Implementation Scope

Possible separately approved implementation deliverables include:

- **Metrics table:** retention-controlled storage for accepted/rejected and
  retry/recovery counters with bounded dimensions and explicit classification.
- **Dashboard:** views for rejection rate, category/reason trends, retry rate,
  recovery rate, exhausted retries, permanent failures, and unresolved work.
- **Alerting:** threshold or trend alerts for sustained rejection increases,
  throttling, dependency degradation, retry exhaustion, and new permanent
  failure patterns using redacted content and deduplication.
- **Recovery workflow:** a controlled, idempotent re-run or operator workflow
  that validates classification, preserves tenant boundaries, respects retry and
  timeout budgets, and records the resulting final status.

Implementation must first identify the smallest compatible telemetry and
collection-run extension. Any persisted evidence requires separate review of
schema, retention, access control, data classification, migration, and
redaction tests. None of these deliverables is implemented by CH-2.4.

## 8. Decision and Limitations

CH-2.4 is **DOCUMENTED / PLANNED**. It consolidates the operational visibility
and retry recovery direction in TD-005 and TD-006; metrics, dashboards,
alerting, persisted evidence, and recovery workflows remain future work.
Offline documentation review was performed only. No live Graph or PostgreSQL
execution was performed, and no production code or runtime behavior changed.
