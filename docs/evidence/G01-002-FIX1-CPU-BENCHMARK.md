# G01-002-FIX1 CPU Benchmark Evidence

**Usage mark:** G01-002-FIX1-RUNTIME-TENANT-WIRING-BENCHMARK-002  
**Session:** NEW  
**Model:** kl/gpt-5.6-luna  
**Purpose:** IMPLEMENTATION-BENCHMARK  
**Token mode:** NORMAL  
**Date:** 2026-08-23

## Result

**PASS**

## Environment

- Task metadata reports: 16 vCPU, 16 GB RAM, increased from the previous 8 vCPU baseline.
- Runtime observed by the benchmark process: 4 online CPUs (`0-3`).
- CPU model: Intel(R) Xeon(R) CPU E5-2640 v4 @ 2.40GHz.
- Kernel: Linux 6.8.0-137-generic x86_64.
- Python: 3.12.3.
- Workspace: `/opt/docker/graph-agent`.
- The workspace is not a Git repository; Git diff/status validation was unavailable.

## Workload

The unchanged focused validation command was:

```text
python3 -m unittest tests.core.test_auth_runtime_cli tests.core.test_g09_r2_normalization_handoff
```

This is the same scope recorded in `G01-002-FIX1-RUNTIME-TENANT-WIRING.md` and covers:

- Runtime CLI initialization.
- Trusted tenant resolver injection.
- Missing and malformed trusted tenant failure.
- Valid tenant collection flow.
- Tenant mismatch protection before writer invocation.

## Measurements

Two executions were collected with `/usr/bin/time`:

| Run | Tests | Test-reported duration | Wall duration | User CPU | System CPU | Process CPU | Max RSS |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1 | 70 passed | 1.381 s | 1.82 s | 1.40 s | 0.36 s | 96% | 26,880 KB |
| 2 | 70 passed | 1.474 s | 1.85 s | 1.40 s | 0.40 s | 97% | 26,836 KB |

The measured run exited with status 0. No swaps or major page faults were reported.

## Baseline Comparison

The prior implementation evidence records 70 passing tests but does not record wall duration, CPU utilization, host CPU count, or memory usage. Therefore, no numeric speedup or CPU regression can be calculated from repository evidence.

The current repeated runs are stable within 0.03 seconds wall time. The task metadata claims 16 vCPU, but the benchmark environment exposes 4 online CPUs; this prevents attributing the result to a 16-vCPU runtime increase. The test workload is offline and short, so it does not establish a meaningful architectural performance difference.

## Implementation Integrity

No production or test implementation was changed. Runtime tenant resolver wiring remains in `collectors/run_collector.py`, and the existing focused validation remains unchanged.

## Token Usage

Token usage for the model response is not exposed to the workspace or test runner. The session token mode is recorded as `NORMAL`; an exact token count is unavailable.

## Blockers

- Host CPU exposure does not match the task metadata: 4 online CPUs observed versus 16 vCPU reported.
- No numeric timing/CPU baseline was recorded by the previous workload.
- Exact model-response token usage is unavailable.
- Tests are offline and do not exercise live Microsoft Graph or PostgreSQL.
