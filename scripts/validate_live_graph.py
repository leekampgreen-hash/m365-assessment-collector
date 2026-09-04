"""Live Microsoft Graph validation suite for TD-003.

Validates representative Graph endpoints against the live controlled tenant:
- G01-001: Users (Directory.Read.All)
- G01-004: Subscribed SKUs (Organization.Read.All / Directory.Read.All)
- G01-006: Sign-in Logs (AuditLog.Read.All)
- G01-011: Conditional Access Policies (Policy.Read.All)

Confirms HTTP 200, response envelope, field presence, and pagination handling
without retaining or leaking tokens or raw sensitive payloads.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from collectors.core.auth import CollectorAuthConfig, CollectorTokenProvider
from collectors.core.config import env_file_source, load_auth_config
from collectors.core.http import build_collector_http_open
from collectors.core.inventory import load_inventory
from collectors.core.transport import GraphTransport


def run_live_graph_validation() -> dict:
    auth_file = Path("/workspace/secrets/collector.env")
    if not auth_file.exists():
        auth_file = Path("secrets/collector.env")
    if not auth_file.exists():
        raise RuntimeError(f"Auth file not found at {auth_file}")

    inventory_file = Path("/workspace/config/api_inventory.json")
    if not inventory_file.exists():
        inventory_file = Path("config/api_inventory.json")

    specs = load_inventory(inventory_file)
    config = load_auth_config(env_file_source(str(auth_file)))

    http_opener = build_collector_http_open(specs, config.tenant_id)
    token_provider = CollectorTokenProvider(config, http_open=http_opener)
    transport = GraphTransport(token_provider=token_provider.get_token, url_open=http_opener)

    endpoints_to_test = [
        {
            "endpoint_id": "G01-001",
            "name": "Users",
            "path": "/v1.0/users?$select=id,displayName,userPrincipalName,userType,accountEnabled&$top=5",
            "expected_fields": ["id", "userPrincipalName"],
        },
        {
            "endpoint_id": "G01-004",
            "name": "Subscribed SKUs",
            "path": "/v1.0/subscribedSkus",
            "expected_fields": ["id", "skuId", "skuPartNumber"],
        },
        {
            "endpoint_id": "G01-006",
            "name": "Sign-in Logs",
            "path": "/v1.0/auditLogs/signIns?$top=5",
            "expected_fields": ["id", "createdDateTime"],
        },
        {
            "endpoint_id": "G01-011",
            "name": "Conditional Access Policies",
            "path": "/v1.0/identity/conditionalAccess/policies",
            "expected_fields": ["id", "displayName", "state"],
        },
    ]

    results = []
    overall_pass = True

    for item in endpoints_to_test:
        eid = item["endpoint_id"]
        start_time = time.monotonic()
        try:
            resp = transport.get(item["path"])
            duration = round(time.monotonic() - start_time, 3)
            data = resp.payload
            items = data.get("value", []) if isinstance(data, dict) else []
            has_next = bool(isinstance(data, dict) and data.get("@odata.nextLink"))

            missing_fields = []
            if items:
                first_item = items[0]
                for f in item["expected_fields"]:
                    if f not in first_item:
                        missing_fields.append(f)

            passed = resp.status == 200 and len(missing_fields) == 0
            if not passed:
                overall_pass = False

            results.append({
                "endpoint_id": eid,
                "name": item["name"],
                "http_status": resp.status,
                "rows_sampled": len(items),
                "pagination_detected": has_next,
                "duration_seconds": duration,
                "expected_fields_verified": len(missing_fields) == 0,
                "missing_fields": missing_fields,
                "status": "PASS" if passed else "FAIL",
            })
        except Exception as exc:
            overall_pass = False
            results.append({
                "endpoint_id": eid,
                "name": item["name"],
                "error": type(exc).__name__,
                "status": "FAIL",
            })

    summary = {
        "tenant_id": config.tenant_id,
        "client_id": config.client_id,
        "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "total_endpoints_tested": len(endpoints_to_test),
        "passed_count": sum(1 for r in results if r["status"] == "PASS"),
        "results": results,
    }
    return summary


if __name__ == "__main__":
    try:
        report = run_live_graph_validation()
        print(json.dumps(report, indent=2))
        sys.exit(0 if report["overall_status"] == "PASS" else 1)
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(2)
