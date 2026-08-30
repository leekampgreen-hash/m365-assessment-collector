# Infrastructure Progress

## INFRA-P01 Scheduled Collector (PASS)

Added APScheduler-based scheduled collection with per-group endpoint and security-rule schedules.

- Added `apscheduler>=3.10.0` to the collector image requirements.
- Added `config/scheduler.json` with daily identity, security, usage-report, and license schedules plus hourly sign-in collection.
- Added `collectors/scheduler.py` with startup runs, interval jobs, coalescing, and `max_instances=1`.
- Classified all schedules as snapshot, security, event, or maintenance data and enforced phase ordering: snapshot → security → events.
- Added daily retention cleanup for `signin_log` records older than 90 days without modifying snapshot tables.
- Added the `scheduler` Docker Compose service using the collector image and runtime mounts.
- Added unauthenticated `GET /api/scheduler/status` for monitoring schedule definitions and estimated next runs; verified HTTP 200.
- Implemented phase transition logging for scheduler execution.

Status: `INFRA-P01 PASS`

Next: `AGT-UX01 Executive Summary Panel`
