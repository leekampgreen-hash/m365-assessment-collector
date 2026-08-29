# STD-15G2 Exchange quota wiring

- **Task:** `STD-15G2-EXCHANGE-QUOTA-WIRING-IMPLEMENTATION-001`
- **Result:** `STD_15G2B_BLOCKED`
- **Data contract:** `mailbox_capacity` is `prohibit_send_receive_quota`; utilization is `storage_used / mailbox_capacity * 100`.
- **Classification:** LOW `<50%`, MEDIUM `>=50% and <80%`, HIGH `>=80%`, NO DATA for missing/zero/invalid quota.
- **Implementation:** USAGE-003 normalization preserves all three quota fields as nullable numeric values; migration 014 adds nullable BIGINT fields to current and snapshot Exchange mailbox tables; persistence includes them; analytics exposes capacity buckets, authoritative report refresh date, totals, and detail rows.
- **Production validation:** Migration 014 applied successfully with `graph_agent_migrator`; USAGE-003 ran in `graph-agent-collector-dev` with `PASS`, 30 source rows, and 30 persisted rows. Focused tests ran in the collector runtime (43 tests, one pre-existing contract failure because normalized numeric values are integers rather than strings). Full host test discovery is not applicable; host tests are executed in the runtime container.
- **Runtime parity:** Rebuild/recreate completed for collector, operations API, and UI. Required parity PASS: analytics, registry, API, persistence, and runtime modules match after recreation. UI syntax was not runnable because Node is unavailable in the container.
- **Database/API validation:** Migration 014 source is exact and runtime DML columns are wired; the configured development PostgreSQL instance returned no matching Exchange columns under the supplied bootstrap database, so production database row/field reconciliation remains blocked. Boundary analytics validation passed: 49.99 LOW, 50 MEDIUM, 79.99 MEDIUM, 80 HIGH, zero quota NO DATA.
- **UI contract:** Exchange overview and detail wiring now expose LOW/MEDIUM/HIGH/NO DATA, refresh date, storage/item totals, storage used, mailbox capacity, utilization %, licensing, SKUs, and email activity; sorting is utilization descending with capacity classes available as filters. Browser acceptance remains deferred to STD-15G3.
- **Scope:** Exchange only. No browser acceptance; deferred to STD-15G3.
