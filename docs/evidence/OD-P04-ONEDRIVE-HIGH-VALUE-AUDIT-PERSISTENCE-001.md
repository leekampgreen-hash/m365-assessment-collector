TASK_ID: OD-P04-ONEDRIVE-HIGH-VALUE-AUDIT-PERSISTENCE-001
RESULT: OD_P04_PASS_OFFLINE_PENDING_DB

IMPLEMENTATION:
- Migration 018 creates core.onedrive_high_value_audit_event.
- Required normalized fields follow the locked contract; record_type and actor_upn are nullable.
- event_category is EXTERNAL_SHARING or MALWARE_DETECTED.
- Only AnonymousLinkCreated, Guest-targeted SharingInvitationCreated/SharingSet, and FileMalwareDetected are accepted.
- SecureLinkCreated and all unknown operations fail closed.
- Timestamps are required and ISO-8601 validated before SQL execution.
- Inserts are parameter-bound, immutable, tenant-scoped, and idempotent on (tenant_id, audit_record_id).

ATOMICITY:
- persist_onedrive_high_value_audit_batch uses BEGIN, commit, and rollback.
- Validation completes before the first insert.
- Result reports attempted, inserted, duplicate_skips, and failure classification.

VALIDATION:
- Focused persistence and migration tests pass.
- Python compile checks pass.
- Production-equivalent PostgreSQL validation is blocked by unavailable configured role credentials.

SCOPE:
No collector, API, UX, analytics, permissions, tenant mutation, or raw payload retention change.

FILES_CHANGED:
- database/migrations/018_onedrive_high_value_audit_event.sql
- collectors/persistence/core.py
- collectors/persistence/__init__.py
- tests/persistence/test_core.py
- tests/database/test_migrations.py
- docs/database-schema-design.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md
- docs/evidence/OD-P04-ONEDRIVE-HIGH-VALUE-AUDIT-PERSISTENCE-001.md
