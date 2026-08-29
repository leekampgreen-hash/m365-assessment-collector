# TD-005 Rejection Metrics and Tracing Improvement Plan

- **Usage mark:** `TD-005-REJECTION-METRICS-TRACING-PLAN-001`
- **Session:** `NEW`
- **Model:** `kl/gpt-5.6-luna`
- **Purpose:** `OPERATIONAL_DESIGN`
- **Status:** `DOCUMENTED / PLANNED`

## 1. Objective

Improve operational visibility into rejected records from the G01-002 through G01-012 workloads while preserving fail-closed validation and preventing sensitive data exposure. The future capability should make rejection volume, classification, location, and severity queryable without recording tokens, secrets, credentials, or raw sensitive payloads.

This document is a design plan only. It does not authorize changes to collectors, adapters, persistence runtime, or database migrations.

## 2. Current Problem

Validation exists across the collection, adapter, security-boundary, and persistence flows, and invalid records are rejected rather than silently accepted. However, detailed operational classification of those rejections is limited. Operators may be able to observe that a batch or operation failed, but cannot consistently determine:

- why records were rejected;
- which endpoint or collection run is affected;
- whether a rejection is a one-off or an increasing trend; and
- whether failures represent data quality, security, or system conditions.

The improvement must add visibility around existing fail-closed outcomes, not weaken validation or create an alternate path to persistence.

## 3. Rejection Categories

Every future rejection evidence event should use one controlled top-level category and a bounded reason code. Free-form diagnostic text may be retained only after redaction and normalization.

### DATA_VALIDATION

Use for records that do not satisfy the approved input or normalized data contract:

- `MISSING_REQUIRED_FIELD`
- `INVALID_TYPE`
- `MALFORMED_FORMAT`
- `INVALID_STRUCTURE`

### SECURITY_VALIDATION

Use for records or operations rejected at the security boundary:

- `TENANT_MISMATCH`
- `FORBIDDEN_FIELD`
- `UNAUTHORIZED_SOURCE`

### SYSTEM

Use for operational failures that prevent a valid operation from completing:

- `PERSISTENCE_FAILURE`
- `TRANSACTION_FAILURE`

The category and reason should describe the first authoritative rejection point. A downstream transaction failure must not be relabeled as a data-validation failure merely because invalid input was present earlier.

## 4. Evidence Fields

The minimum future rejection event or trace annotation should contain:

- `timestamp` in UTC;
- `endpoint` from a code-owned endpoint identity;
- `collection_run_id` when a collection run exists;
- `source_object_id` if available and safe to retain;
- `rejection_category`;
- `rejection_reason` using the bounded reason codes above;
- `affected_field` when a specific approved field is known; and
- `severity` using a documented bounded scale such as `INFO`, `WARNING`, or `ERROR`.

Recommended operational dimensions are endpoint, rejection category, rejection reason, and severity. `tenant_id` may be represented only by an approved non-sensitive tenant reference or redacted correlation value where operational policy permits; it must not become an unrestricted analytics dimension.

Do not capture or derive evidence containing:

- tokens;
- secrets;
- credentials; or
- raw sensitive payload.

Field names and identifiers must be allowlisted. Error text, exception details, URLs, headers, SQL parameters, and payload fragments require redaction before they can enter evidence. High-cardinality or sensitive values should be replaced with a stable redacted indicator or omitted.

## 5. Trace and Metric Design

The future implementation should emit a rejection counter and a trace event at the existing rejection boundary. The counter should use bounded labels only:

```text
records_rejected_total{
  endpoint,
  rejection_category,
  rejection_reason,
  severity
}
```

The trace event should carry the evidence fields in Section 4, plus a redacted correlation context sufficient to connect the rejection to its collection run. It should record outcome and classification, not the rejected object. Batch-level traces should preserve no-partial-write semantics and distinguish a rejected record from a failed collection or rolled-back transaction.

Success criteria for the future instrumentation include consistent reason-code coverage, no sensitive label values, stable endpoint identity, and the ability to correlate a rejection to a run without reconstructing the raw payload.

## 6. Agentic Analytics Use Case

With the bounded metrics and redacted trace evidence, a future agent can answer operational questions by aggregating counters and joining them to trace metadata:

- **Why were records rejected?** Group `rejection_category` and `rejection_reason`, then show affected endpoint and safe field metadata.
- **Is rejection increasing?** Compare rejection counts and rates over time by endpoint and reason, using collection-run totals as the denominator when available.
- **Which endpoint has quality issues?** Rank endpoints by rejection rate and absolute count, separate data-validation failures from security and system failures, and identify sustained changes rather than isolated events.

The agent should report uncertainty when denominators, collection-run identifiers, or source object identifiers are unavailable. It should never answer by exposing the rejected payload or secret-bearing diagnostics.

## 7. Integration Approach

Reuse the existing boundaries and flow:

```text
Existing collector framework
        |
        v
Existing adapter validation
        |
        v
Existing security boundary
        |
        v
Redacted rejection metric/trace emission
```

Instrumentation should observe existing validation and rejection outcomes at the narrowest authoritative boundary. Endpoint identity should come from the existing registry/framework context, adapter field names should come from approved contracts, and security classifications should remain owned by the security boundary. No new collection path, validation bypass, or alternate persistence route is required.

Before implementation, confirm whether the existing logging/telemetry facility can accept bounded metrics and structured redacted events. Select the smallest compatible extension; introduce no new architecture unless the existing facility cannot carry the required evidence safely.

## 8. Future Implementation Scope

The following are possible follow-up deliverables and are not implemented by this plan:

### Rejection table

A separately approved schema design may define a retention-controlled rejection table for the minimum evidence fields. Any table would require explicit data classification, access controls, retention, redaction, and migration review. It must not store raw rejected payloads or credentials.

### Metrics dashboard

A dashboard could show rejection count and rate by endpoint, category, reason, severity, and time window. It should provide collection-run context and distinguish record rejection from batch rollback or persistence failure.

### Alerting

Alerts could detect sustained increases, threshold breaches, new rejection reasons, or repeated system failures. Alert payloads must contain only bounded classifications and redacted identifiers, with deduplication to avoid leaking high-cardinality source data.

Implementation must include a test and evidence plan for reason-code mapping, metric labels, trace redaction, tenant isolation, rollback distinction, and no-sensitive-data assertions. None of these implementation items is part of TD-005 documentation completion.

## 9. Limitations and Decision

TD-005 is **DOCUMENTED / PLANNED**. The current limitation remains until an approved implementation adds operational metrics and redacted tracing. This plan intentionally makes no runtime, collector, adapter, persistence, or migration change and does not claim that metrics, dashboards, alerts, or a rejection table currently exist.
