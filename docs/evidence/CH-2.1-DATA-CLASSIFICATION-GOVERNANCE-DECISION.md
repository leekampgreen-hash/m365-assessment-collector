# CH-2.1 Data Classification Governance Decision

**Usage mark:** `CH-2.1-DATA-CLASSIFICATION-GOVERNANCE-001`  
**Date:** 2026-08-23  
**Purpose:** `GOVERNANCE_DECISION`  
**Scope:** Offline documentation review of registry, catalog, schema design, and migration metadata for four affected G01 endpoints.

## 1. Background

TD-001 identified metadata drift between the workload registry and the
catalog/schema contract. The registry entries for G01-005 Directory Audit Logs,
G01-006 Sign-in Logs, G01-013 Risky Users, and G01-014 Risk Detections use
`HIGH_SENSITIVITY` in the `retention_class` field. The data catalog and database
schema design classify those same endpoints as `HIGH_SENSITIVITY` for
sensitivity and `LONG` for retention. The corresponding security migration
tables default their `retention_class` to `LONG` and constrain it to the
retention vocabulary.

This review determines whether the two values are competing values for one
dimension or values from two separate governance dimensions. It is a
documentation-only decision. No registry, collector, adapter, persistence,
or migration value is changed by this review.

## 2. Metadata Dimension Analysis

### Sensitivity classification

Sensitivity describes the harm, access-control, and minimization posture of the
data. The catalog controlled vocabulary includes `LOW`, `INTERNAL`, `SENSITIVE`,
and `HIGH_SENSITIVITY`. The schema design maps `HIGH_SENSITIVITY` to restricted
database access, minimized field selection, exclusion of raw or high-risk
detail fields, and related privacy controls.

`HIGH_SENSITIVITY` therefore answers: **how sensitive is the retained data and
what protections govern access and field selection?**

### Retention duration

Retention describes how long the normalized data is retained and is a separate
lifecycle-policy input. The catalog and schema controlled vocabulary includes
`SHORT`, `STANDARD`, `LONG`, and `REFERENCE`. The schema design explicitly
states that this value is stored in each operational or snapshot table and is
consumed by a future configurable retention policy process. It does not itself
define an exact number of days.

`LONG` therefore answers: **which retention policy class applies to the data?**

### Decision on the dimensions

`HIGH_SENSITIVITY` and `LONG` represent **different governance dimensions**.
They are not interchangeable labels and must not occupy the same semantic
field. A high-sensitivity dataset may require long retention in this catalog,
but that relationship is a governance mapping, not evidence that sensitivity
and retention are the same attribute. The registry's use of
`HIGH_SENSITIVITY` as `retention_class` is consequently a metadata contract
error, not an intentional alternate retention vocabulary.

## 3. Affected Endpoint Review

| Endpoint | Current registry value | Catalog sensitivity | Catalog/schema retention | Decision |
|---|---|---|---|---|
| G01-005 Directory Audit Logs | `retention_class=HIGH_SENSITIVITY` | `HIGH_SENSITIVITY` | `LONG` | Preserve sensitivity as `HIGH_SENSITIVITY`; interpret retention as `LONG`; registry field is drift and requires later correction |
| G01-006 Sign-in Logs | `retention_class=HIGH_SENSITIVITY` | `HIGH_SENSITIVITY` | `LONG` | Preserve sensitivity as `HIGH_SENSITIVITY`; interpret retention as `LONG`; registry field is drift and requires later correction |
| G01-013 Risky Users | `retention_class=HIGH_SENSITIVITY` | `HIGH_SENSITIVITY` | `LONG` | Preserve sensitivity as `HIGH_SENSITIVITY`; interpret retention as `LONG`; registry field is drift and requires later correction |
| G01-014 Risk Detections | `retention_class=HIGH_SENSITIVITY` | `HIGH_SENSITIVITY` | `LONG` | Preserve sensitivity as `HIGH_SENSITIVITY`; interpret retention as `LONG`; registry field is drift and requires later correction |

The catalog rows independently show `HIGH_SENSITIVITY` in the Sensitivity
Class column and `LONG` in the Recommended Retention Class column. The schema
retention table repeats `LONG` for all four endpoints. Migration 004 uses
`LONG` defaults for `core.audit_event`, `core.risk_detection`,
`core.risky_user`, and `core.risky_user_snapshot`.

## 4. Governance Decision

**Decision: A — keep both values as different dimensions.**

The authoritative interpretation is:

- `HIGH_SENSITIVITY` is the sensitivity classification for G01-005, G01-006,
  G01-013, and G01-014.
- `LONG` is the retention class for those endpoints and their applicable
  current, snapshot, or event tables.
- The four registry `retention_class=HIGH_SENSITIVITY` values are confirmed
  metadata drift and require correction in a separately approved implementation
  task. This decision does not authorize that implementation.

This is not a request to change catalog sensitivity values to `LONG`, nor to
expand the schema retention vocabulary to include sensitivity labels.

## 5. Impact Analysis

### Registry

The registry currently conflates the dimensions by placing the sensitivity
label in `retention_class` for four entries. The registry remains unchanged in
this documentation-only review. A future controlled implementation should set
the affected registry retention value to `LONG` and preserve sensitivity in its
own documented metadata dimension wherever that metadata is represented. Any
tests or generated contracts that assert registry retention must be updated in
that same implementation task.

### Catalog

The catalog is internally consistent and remains authoritative for the semantic
distinction: `Sensitivity Class=HIGH_SENSITIVITY` and
`Recommended Retention Class=LONG`. No catalog correction is required. Its
sensitivity-aware retention principle is understood as a mapping from one
dimension to another, not as a shared field vocabulary.

### Schema

The schema design is consistent with the decision. Its retention model uses a
per-table `retention_class` with the `SHORT`/`STANDARD`/`LONG`/`REFERENCE`
vocabulary, while its security section separately describes sensitivity-driven
access and minimization behavior. No schema redesign or column change is
required.

### Future retention policy

Future policy automation must consume `retention_class` only for lifecycle
decisions. It must not infer retention by reading a sensitivity label from that
field. The policy engine may use sensitivity as an independent input to access
controls, minimization, monitoring, or approval requirements. Exact durations
remain a future policy/configuration decision; this review establishes only
that these four endpoint datasets belong to the `LONG` class.

## 6. Recommendation

Adopt the following authoritative contract for future reviews and
implementation work:

1. Sensitivity classification and retention class are separate governance
   dimensions with separate controlled vocabularies.
2. For G01-005, G01-006, G01-013, and G01-014, the authoritative pair is
   `sensitivity=HIGH_SENSITIVITY` and `retention_class=LONG`.
3. Treat any `HIGH_SENSITIVITY` value found in a `retention_class` field as
   invalid metadata, not as a new retention class.
4. Correct the four registry values in a separately approved implementation
   task, then run registry/catalog/schema/migration consistency validation.

## Validation

- Reviewed `collectors/workloads/registry.py`, `docs/data-catalog.md`,
  `docs/database-schema-design.md`, and `database/migrations/`.
- Confirmed the four registry values, catalog sensitivity/retention columns,
  schema retention table, and migration defaults are consistent with this
  decision.
- No production code changes were made.
- No collectors, adapters, registry runtime, persistence runtime, or database
  migrations were modified.
- Review was offline; no live Graph or database validation was performed.

## Blockers

None for the governance decision. The four registry corrections remain a
separate implementation task and were intentionally not performed here.
