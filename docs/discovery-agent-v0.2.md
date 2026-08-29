# Discovery Agent v0.2 — Autonomous Batch Discovery

## Commands

| Command | Description |
|---------|-------------|
| `--batch` | Autonomous batch discovery: test all enabled endpoints, classify, group permission gaps, produce approval recommendation |
| `--resume` | Continue discovery after human grants missing permissions; reruns only affected endpoints |
| `--status` | Show persisted discovery state from `discovery-state.json`; makes no network calls |

## Human Approval Boundary

When `--batch` encounters endpoints with HTTP 403 (missing privileges), the agent:

1. Classifies them as `PERMISSION_REQUIRED`
2. Groups them by documented permission
3. Produces a `HUMAN APPROVAL REQUIRED` console section
4. Sets workflow state to `AWAITING_APPROVAL`
5. Exits with code 0 (successful orchestration)

The agent **never** grants permissions, modifies Entra ID, or increases its own privilege.

## State File

`data/discovery/discovery-state.json` — latest orchestration state (not historical evidence).

Contains: agent version, workflow state, token roles, endpoint results, permission groups.

Written atomically (write temp file, then rename).

## Evidence

Every `--batch` and `--resume` creates a timestamped evidence file:

- `data/discovery/discovery-batch-YYYYMMDD-HHMMSS.json`
- `data/discovery/discovery-resume-YYYYMMDD-HHMMSS.json`

Evidence contains endpoint results, classifications, permission groups, and duration.
Evidence does **not** contain credentials, tokens, or full Graph response objects.

## Workflow States

- `COMPLETE` — every enabled endpoint PASS
- `AWAITING_APPROVAL` — discovery succeeded but permissions are missing
- `PARTIAL` — some endpoints throttled or errored
- `FAIL` — authentication or framework failure