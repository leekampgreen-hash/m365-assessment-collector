# OD-P06A OneDrive audit runtime parity correction

TASK_ID: OD-P06A-ONEDRIVE-AUDIT-RUNTIME-PARITY-CORRECTION-001
RESULT: OD_P06A_PASS
DATE: 2026-08-29

## Root cause

- classification: STALE_CONTAINER
- authoritative_source: `/opt/docker/graph-agent/collectors`
- runtime_path: `/workspace/collectors`
- compose_service: `collector`
- container: `graph-agent-collector-dev`
- exact_issue: The existing collector container instance was stale per OD-P06 evidence. Current Compose wiring is correct and bind-mounts the complete collectors directory. `Dockerfile.collector` also copies collectors into the image, but the bind mount at the same runtime path is active and authoritative; no image shadowing defect was found.

The documented OD-P06 pre-correction state reported a `collectors/persistence/core.py` mismatch. An immediate pre-recreation inspection in this session already showed matching bind-mounted bytes, so the stale state was not reproducible at that instant. The smallest corrective action was nevertheless to recreate only the collector container.

## Parity before correction

The OD-P06 evidence recorded the following historical state:

- collectors/onedrive_audit.py: not included in the prior parity helper; historical runtime refresh required
- collectors/run_collector.py: not included in the prior parity helper; historical runtime refresh required
- collectors/persistence/core.py: MISMATCH reported by OD-P06
- collectors/core/errors.py: not previously recorded

Immediate pre-recreation SHA-256 inspection showed all checked files matching, but the container was recreated to clear the documented stale runtime instance.

## Correction

- action: `docker compose up -d --force-recreate --no-deps collector`
- compose_changed: NO
- service_recreated: YES, collector only
- image_rebuilt: NO

## Parity after correction

SHA-256 source/runtime pairs:

| Artifact | SOURCE_HASH | RUNTIME_HASH | MATCH |
|---|---|---|---|
| collectors/onedrive_audit.py | 9dbec44e35d5a24d9c72286ba478dcf044d9effbe358ea1c43cd7b594a08d015 | 9dbec44e35d5a24d9c72286ba478dcf044d9effbe358ea1c43cd7b594a08d015 | YES |
| collectors/run_collector.py | 5867d0a1e1f863f81fe9af54385e02daa74040752be37708e442026690228565 | 5867d0a1e1f863f81fe9af54385e02daa74040752be37708e442026690228565 | YES |
| collectors/persistence/core.py | a7e8afacca353cb25ff73e2e93cd590435cd1f4a9631ccf41d50d9227cb1b9d7 | a7e8afacca353cb25ff73e2e93cd590435cd1f4a9631ccf41d50d9227cb1b9d7 | YES |
| collectors/core/errors.py | cab699b81045a2f0c4e71632d418da6b4914dec35370525777e70ad975e41cb3 | cab699b81045a2f0c4e71632d418da6b4914dec35370525777e70ad975e41cb3 | YES |

Overall: PASS.

## Runtime

- service: `graph-agent-collector-dev` running; restart count 0 after recreation and observation
- mounts: expected `/opt/docker/graph-agent/collectors:/workspace/collectors` bind mount active; expected project source visible
- import_smoke: PASS; `collectors.onedrive_audit`, `collectors.run_collector`, `collectors.persistence.core`, and `collectors.core.errors` imported after source compilation with Python `-B`
- health: running, not restarting; collector command is the expected idle command

No live Management Activity collection was invoked.

## Semantic changes

NONE. No business code, OD-P03 contract, OD-P04 persistence semantics, OD-P05 lineage semantics, OD-P06 behavior, schema, or tenant configuration was changed.

FILES_CHANGED:
- docs/evidence/OD-P06A-ONEDRIVE-AUDIT-RUNTIME-PARITY-CORRECTION-001.md
- docs/PROJECT_PROGRESS.md
- docs/AI_USAGE_LOG.md

RUNTIME_PARITY: PASS
READY_FOR_OD_P06B: YES
FINAL_STATUS: OD_P06A_PASS
