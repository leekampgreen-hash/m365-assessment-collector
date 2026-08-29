#!/usr/bin/env python3
"""Read-only Microsoft Graph API inventory discovery agent v0.2 - Autonomous Batch Discovery.

Hard rules:
- Read-only. GET requests only against Graph discovery endpoints.
- Never add/grant permissions, never modify Entra ID or tenant objects.
- Never print or persist secrets/tokens/Authorization headers/JWTs.
- Python 3 standard library only.
"""

import argparse
import base64
import json
import os
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

AGENT_VERSION = "0.2.0"
WORKSPACE = Path("/workspace")
INVENTORY_PATH = WORKSPACE / "config" / "api_inventory.json"
EVIDENCE_DIR = WORKSPACE / "data" / "discovery"
STATE_FILE = WORKSPACE / "data" / "discovery" / "discovery-state.json"
DOC_PATH = WORKSPACE / "docs" / "api-inventory.md"
ENV_PATH = WORKSPACE / "secrets" / "collector.env"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"
TOKEN_TIMEOUT = 30
GRAPH_TIMEOUT = 30

NONFATAL_CLASSIFICATIONS = ("PASS", "PERMISSION_REQUIRED", "THROTTLED", "API_ERROR")
FATAL_RESULT_CLASSIFICATION = "AUTH_FAILURE"

WORKFLOW_COMPLETE = "COMPLETE"
WORKFLOW_AWAITING_APPROVAL = "AWAITING_APPROVAL"
WORKFLOW_PARTIAL = "PARTIAL"
WORKFLOW_FAIL = "FAIL"


def load_env(path=None):
    path = path if path is not None else ENV_PATH
    values = {}
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("'\"")
    required = ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError("Missing required collector environment variables: " + ", ".join(missing))
    return {key: values[key] for key in required}


def token_roles(token):
    parts = token.split(".")
    if len(parts) != 3:
        return []
    payload = base64.urlsafe_b64decode(parts[1] + "=" * (-len(parts[1]) % 4))
    claims = json.loads(payload.decode("utf-8"))
    roles = claims.get("roles", [])
    return sorted(roles) if isinstance(roles, list) else []


def acquire_token(credentials, opener=urlopen):
    token_url = "https://login.microsoftonline.com/{}/oauth2/v2.0/token".format(credentials["GRAPH_TENANT_ID"])
    body = urlencode({
        "grant_type": "client_credentials",
        "client_id": credentials["GRAPH_CLIENT_ID"],
        "client_secret": credentials["GRAPH_CLIENT_SECRET"],
        "scope": "https://graph.microsoft.com/.default",
    }).encode("ascii")
    request = Request(token_url, data=body, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    with opener(request, timeout=TOKEN_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))
    token = payload.get("access_token")
    if not token:
        raise RuntimeError("Token response did not contain an access token")
    return token


def _error_payload(raw):
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None, None
    error = payload.get("error", {}) if isinstance(payload, dict) else {}
    if isinstance(error, dict):
        return error.get("code"), error.get("message")
    return None, None


def _classification(status, error_code=None):
    if status is not None and 200 <= status < 300:
        return "PASS"
    if status == 401:
        return "AUTH_FAILURE"
    if status == 403:
        return "PERMISSION_REQUIRED"
    if status == 429:
        return "THROTTLED"
    return "API_ERROR"


def _get_documented_permissions(endpoint):
    perms = endpoint.get("documented_permissions")
    if isinstance(perms, list) and perms:
        return sorted(perms)
    single = endpoint.get("permission")
    if single:
        return [single]
    return []


def _request_page(url, token, opener=urlopen):
    request = Request(url, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
    try:
        with opener(request, timeout=GRAPH_TIMEOUT) as response:
            return response.status, dict(response.headers), json.loads(response.read().decode("utf-8")), None, None
    except HTTPError as error:
        raw = error.read()
        code, message = _error_payload(raw)
        return error.code, dict(error.headers), None, code, message
    except (URLError, TimeoutError, OSError) as error:
        return None, {}, None, type(error).__name__, str(error)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        return 200, {}, None, type(error).__name__, "Invalid JSON response"


def _endpoint_url(path, select, top):
    if path.startswith("https://"):
        url = path
    else:
        normalized_path = "/" + path.lstrip("/")
        if normalized_path.startswith("/v1.0/"):
            normalized_path = normalized_path[len("/v1.0"):]
        url = GRAPH_BASE.rstrip("/") + normalized_path
    query = {}
    if select:
        query["$select"] = ",".join(select)
    if top is not None:
        query["$top"] = str(top)
    if query:
        return url + ("&" if "?" in url else "?") + urlencode(query)
    return url


def discover_endpoint(endpoint, token, opener=urlopen, clock=time.monotonic, token_roles=None):
    started = clock()
    status = error_code = error_message = retry_after = None
    pages = total_rows = 0
    pagination_detected = False
    url = _endpoint_url(endpoint["path"], endpoint.get("select", []), endpoint.get("top", 10))
    while url:
        status, headers, payload, error_code, error_message = _request_page(url, token, opener)
        retry_after = headers.get("Retry-After") if status == 429 else None
        if not (status is not None and 200 <= status < 300):
            break
        if not isinstance(payload, dict):
            status, error_code, error_message = 200, "InvalidResponse", "Graph response was not an object"
            break
        pages += 1
        values = payload.get("value", [])
        total_rows += len(values) if isinstance(values, list) else 0
        next_link = payload.get("@odata.nextLink")
        if next_link:
            pagination_detected = True
            url = next_link
        else:
            url = None
    return {
        "execution_timestamp": datetime.now(timezone.utc).isoformat(),
        "agent_version": AGENT_VERSION,
        "inventory_id": endpoint["id"],
        "workload": endpoint["workload"],
        "endpoint_name": endpoint["name"],
        "method": endpoint["method"],
        "endpoint_path": endpoint["path"],
        "auth_type": endpoint["auth"],
        "documented_permissions": _get_documented_permissions(endpoint),
        "http_status": status,
        "classification": _classification(status, error_code),
        "pages": pages,
        "total_rows": total_rows,
        "pagination_detected": pagination_detected,
        "duration_seconds": round(clock() - started, 3),
        "graph_error_code": error_code,
        "graph_error_message": error_message,
        "retry_after": retry_after,
        "token_roles": token_roles or [],
    }


def load_inventory(path=None):
    path = path if path is not None else INVENTORY_PATH
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _endpoint_id_from_result(result):
    return result["inventory_id"]


def _compute_workflow_state(endpoint_results):
    if not endpoint_results:
        return WORKFLOW_FAIL
    classifications = {r["classification"] for r in endpoint_results}
    if FATAL_RESULT_CLASSIFICATION in classifications:
        return WORKFLOW_FAIL
    if classifications == {"PASS"}:
        return WORKFLOW_COMPLETE
    if "PERMISSION_REQUIRED" in classifications:
        return WORKFLOW_AWAITING_APPROVAL
    if "THROTTLED" in classifications or "API_ERROR" in classifications:
        return WORKFLOW_PARTIAL
    return WORKFLOW_FAIL


def _build_permission_groups(endpoint_results, token_roles=None):
    token_roles = token_roles or []
    groups = {}
    for result in endpoint_results:
        if result["classification"] != "PERMISSION_REQUIRED":
            continue
        for perm in result["documented_permissions"]:
            if perm not in groups:
                groups[perm] = {
                    "permission": perm,
                    "affected_endpoint_ids": [],
                    "affected_endpoint_names": [],
                    "current_role_present": perm in token_roles,
                    "approval_status": "REQUIRED",
                }
            if result["inventory_id"] not in groups[perm]["affected_endpoint_ids"]:
                groups[perm]["affected_endpoint_ids"].append(result["inventory_id"])
                groups[perm]["affected_endpoint_names"].append(result["endpoint_name"])
    for group in groups.values():
        if group["current_role_present"]:
            group["approval_status"] = "ROLE_PRESENT_BUT_STILL_DENIED"
    result = list(groups.values())
    result.sort(key=lambda group: group["permission"])
    return result


def _build_endpoint_state(result):
    return {
        "id": result["inventory_id"],
        "key": result["endpoint_name"].lower().replace(" ", ""),
        "endpoint_name": result["endpoint_name"],
        "classification": result["classification"],
        "http_status": result["http_status"],
        "last_tested": result["execution_timestamp"],
        "documented_permissions": result["documented_permissions"],
        "pages": result["pages"],
        "total_rows": result["total_rows"],
        "retry_after": result.get("retry_after"),
    }


def _current_timestamp():
    return datetime.now(timezone.utc).isoformat()


def _build_state(workflow_state, roles, endpoint_states, permission_groups, last_batch=None):
    return {
        "agent_version": AGENT_VERSION,
        "updated_at": _current_timestamp(),
        "workflow_state": workflow_state,
        "token_roles": roles,
        "last_batch_execution": last_batch or _current_timestamp(),
        "endpoints": endpoint_states,
        "permission_groups": permission_groups,
    }


def write_state_file(state, path=None):
    path = path if path is not None else STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / ("discovery-state.tmp." + str(os.getpid()))
    try:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2)
            handle.write("\n")
        shutil.move(str(tmp), str(path))
    except BaseException:
        if tmp.exists():
            tmp.unlink()
        raise


def load_state_file(path=None):
    path = path if path is not None else STATE_FILE
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def write_evidence(results, timestamp=None, directory=None, mode="manual"):
    directory = directory if directory is not None else EVIDENCE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    timestamp = timestamp or datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / ("discovery-{}-{}.json".format(mode, timestamp))
    if path.exists():
        path = directory / ("discovery-{}-{}-{}.json".format(mode, timestamp, time.time_ns() % 1000000))
    with open(path, "w", encoding="utf-8") as handle:
        json.dump({"agent_version": AGENT_VERSION, "results": results}, handle, indent=2)
        handle.write("\n")
    return path


def _print_permission_queue(permission_groups):
    if not permission_groups:
        return
    print("\nPermission Queue:")
    print("Permission | Endpoints | Status")
    for group in permission_groups:
        print("{} | {} | {}".format(
            group["permission"],
            ", ".join(group["affected_endpoint_ids"]),
            group["approval_status"],
        ))


def _print_approval_gate(permission_groups):
    waiting = [g for g in permission_groups
               if g["approval_status"] in ("REQUIRED", "ROLE_PRESENT_BUT_STILL_DENIED")]
    if not waiting:
        return
    print("\nHUMAN APPROVAL REQUIRED")
    for group in waiting:
        print("\n" + group["permission"])
        print("Affected:")
        for eid, name in zip(group["affected_endpoint_ids"], group["affected_endpoint_names"]):
            print("- {} {}".format(eid, name))
        if group["current_role_present"]:
            print("Note: role IS present in token but endpoint still returns HTTP 403.")
    print("\nAction: grant permission manually in Microsoft Entra ID and admin-consent it.")
    print("\nThen run: python /workspace/agents/discovery/discovery_agent.py --resume")


def update_document(results, state=None, path=None):
    path = path if path is not None else DOC_PATH
    rows = {}
    for result in results:
        rows[result["inventory_id"]] = result
    persisted = load_state_file()
    if persisted:
        for ep in persisted.get("endpoints", []) or []:
            epid = ep.get("id")
            if epid and epid not in rows:
                rows[epid] = ep
    workflow_state = persisted.get("workflow_state", "") if persisted else (state or {}).get("workflow_state", "")
    token_roles = persisted.get("token_roles", []) if persisted else []
    if results:
        token_roles = sorted(results[0].get("token_roles") or [])
    lines = [
        "# API Discovery Inventory",
        "",
        "## Latest Results",
        "",
        "| ID | Workload | Endpoint | Method | Auth | Documented Permission | Observed Token Roles | HTTP | Pages | Rows | Pagination | Result | Workflow Status | Last Tested |",
        "|---|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|",
    ]
    inventory = load_inventory()
    for endpoint in inventory:
        result = rows.get(endpoint["id"])
        if result:
            values = [
                endpoint["id"], endpoint["workload"], endpoint["name"],
                endpoint["method"], endpoint["auth"],
                ", ".join(_get_documented_permissions(endpoint)),
                ", ".join(sorted(result.get("token_roles") or token_roles)),
                result.get("http_status") or "-",
                result.get("pages", "-"),
                result.get("total_rows", "-"),
                str(result.get("pagination_detected", "")).lower(),
                result.get("classification", "UNKNOWN"),
                workflow_state,
                result.get("last_tested", result.get("execution_timestamp", "-")),
            ]
        else:
            values = [
                endpoint["id"], endpoint["workload"], endpoint["name"],
                endpoint["method"], endpoint["auth"],
                ", ".join(_get_documented_permissions(endpoint)),
                ", ".join(token_roles) if token_roles else "-",
                "NOT RUN", "-", "-", "-", "NOT RUN", "", "-",
            ]
        lines.append("| " + " | ".join(str(v) for v in values) + " |")
    lines.append("")
    lines.append("## G01-003 Permission Behavior Finding")
    lines.append("")
    lines.append("G01-003 (Organization) returned HTTP 200 with full property access despite the Collector token")
    lines.append("not containing Organization.Read.All. This is a documented permission-behavior observation.")
    lines.append("The token roles at the time of baseline testing were:")
    lines.append("")
    lines.append("- User.Read.All")
    lines.append("- Group.Read.All")
    lines.append("- LicenseAssignment.Read.All")
    lines.append("")
    lines.append("This finding is preserved for G02 review. Do not \"correct\" or erase this observation.")
    lines.append("")
    lines.append("## Autonomous Permission Queue")
    lines.append("")
    lines.append("Permission | Endpoints | Status")
    groups = (persisted or state or {}).get("permission_groups", []) or []
    if groups:
        for group in groups:
            lines.append("{} | {} | {}".format(
                group["permission"],
                ", ".join(group.get("affected_endpoint_ids", []) or []),
                group.get("approval_status", "UNKNOWN"),
            ))
    else:
        lines.append("(none)")
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _merge_into_state(previous_state, new_results, roles):
    previous_endpoints = {e["id"]: e for e in previous_state.get("endpoints", []) or []}
    endpoint_states = []
    all_eids = sorted(set(list(previous_endpoints.keys()) + [r["inventory_id"] for r in new_results]))
    for eid in all_eids:
        matched = next((r for r in new_results if r["inventory_id"] == eid), None)
        if matched:
            endpoint_states.append(_build_endpoint_state(matched))
        else:
            endpoint_states.append(previous_endpoints[eid])
    permission_groups = _recompute_permission_groups_from_states(endpoint_states, roles)
    workflow_state = _compute_workflow_state(endpoint_states)
    return _build_state(workflow_state, roles, endpoint_states, permission_groups, last_batch=previous_state.get("last_batch_execution"))


def _merge_groups(current_groups, previous_groups):
    merged = {g["permission"]: dict(g) for g in current_groups}
    for group in previous_groups or []:
        if group["permission"] not in merged:
            merged[group["permission"]] = dict(group)
    return [merged[key] for key in sorted(merged)]


def _recompute_permission_groups_from_states(endpoint_states, token_roles=None):
    """Build permission groups from the CURRENT endpoint state classifications.

    A permission group is included only if at least one endpoint with that
    permission is currently classified as PERMISSION_REQUIRED.
    """
    token_roles = token_roles or []
    groups = {}
    for ep in endpoint_states:
        if ep.get("classification") != "PERMISSION_REQUIRED":
            continue
        perms = ep.get("documented_permissions") or []
        for perm in perms:
            if perm not in groups:
                groups[perm] = {
                    "permission": perm,
                    "affected_endpoint_ids": [],
                    "affected_endpoint_names": [],
                    "current_role_present": perm in token_roles,
                    "approval_status": "REQUIRED",
                }
            eid = ep.get("id")
            ename = ep.get("endpoint_name", ep.get("key", ""))
            if eid and eid not in groups[perm]["affected_endpoint_ids"]:
                groups[perm]["affected_endpoint_ids"].append(eid)
                groups[perm]["affected_endpoint_names"].append(ename)
    for group in groups.values():
        if group["current_role_present"]:
            group["approval_status"] = "ROLE_PRESENT_BUT_STILL_DENIED"
    result = list(groups.values())
    result.sort(key=lambda g: g["permission"])
    return result


def _find_throttled_endpoint_ids(state):
    """Return set of endpoint IDs whose latest classification is THROTTLED."""
    throttled = set()
    for ep in state.get("endpoints", []) or []:
        if ep.get("classification") == "THROTTLED":
            eid = ep.get("id")
            if eid:
                throttled.add(eid)
    return throttled


def run_batch(inventory, env, opener=urlopen):
    started = time.monotonic()
    token = acquire_token(env, opener=opener)
    roles = token_roles(token)
    print("Collector token roles: {}".format(", ".join(roles)))
    enabled = [item for item in inventory if item.get("enabled", True)]
    results = []
    for endpoint in enabled:
        result = discover_endpoint(endpoint, token, opener=opener, token_roles=roles)
        results.append(result)
        print("{id} {name:<12} {classification} HTTP={http} pages={pages} rows={rows}".format(
            id=result["inventory_id"], name=result["endpoint_name"],
            classification=result["classification"], http=result["http_status"] or "-",
            pages=result["pages"], rows=result["total_rows"]))
    workflow_state = _compute_workflow_state(results)
    permission_groups = _build_permission_groups(results, roles)
    endpoint_states = [_build_endpoint_state(r) for r in results]
    state = _build_state(workflow_state, roles, endpoint_states, permission_groups)
    write_state_file(state)
    evidence = write_evidence(results, mode="batch")
    update_document(results, state=state)
    duration = round(time.monotonic() - started, 3)
    print("\nDiscovery run: " + workflow_state)
    print("Evidence: " + str(evidence))
    _print_permission_queue(permission_groups)
    if workflow_state == WORKFLOW_AWAITING_APPROVAL:
        _print_approval_gate(permission_groups)
    return workflow_state, results, state, evidence, duration


def _waiting_endpoint_ids(state):
    waiting = set()
    for group in state.get("permission_groups", []) or []:
        if group.get("approval_status") in ("REQUIRED", "ROLE_PRESENT_BUT_STILL_DENIED"):
            for eid in group.get("affected_endpoint_ids", []) or []:
                waiting.add(eid)
    return waiting


def _find_granted_waiting_endpoints(state, fresh_roles):
    granted = set()
    for group in state.get("permission_groups", []) or []:
        perm = group.get("permission")
        if perm and perm in fresh_roles:
            for eid in group.get("affected_endpoint_ids", []) or []:
                granted.add(eid)
    return granted


def run_resume(inventory, env, opener=urlopen):
    started = time.monotonic()
    previous = load_state_file()
    if previous is None:
        print("Resume result: FAIL")
        print("No discovery-state.json found. Run --batch first.")
        return WORKFLOW_FAIL, None, None, None, 1
    token = acquire_token(env, opener=opener)
    roles = token_roles(token)
    print("Previous token roles: {}".format(", ".join(previous.get("token_roles") or [])))
    print("Current token roles:  {}".format(", ".join(roles)))
    waiting = _waiting_endpoint_ids(previous)
    granted = _find_granted_waiting_endpoints(previous, roles)
    throttled = _find_throttled_endpoint_ids(previous)
    rerun_reasons = []
    if granted:
        rerun_reasons.append("permission grant")
    if throttled:
        rerun_reasons.append("throttled retry")
    if not granted and not throttled:
        print("\nResume result: NO_CHANGE")
        print("Workflow state: " + str(previous.get("workflow_state", WORKFLOW_UNKNOWN)))
        return previous.get("workflow_state", WORKFLOW_AWAITING_APPROVAL), None, None, None, 0
    print("Resume reasons: {}".format(", ".join(rerun_reasons)))
    inventory_map = {e["id"]: e for e in inventory}
    rerun = set()
    if granted:
        for eid in sorted(granted):
            if eid in inventory_map:
                rerun.add(eid)
    if throttled:
        # Respect Retry-After from previous state before retrying throttled endpoints
        for ep in previous.get("endpoints", []) or []:
            if ep.get("id") in throttled:
                retry_after = ep.get("retry_after")
                if retry_after is not None:
                    try:
                        wait = int(retry_after)
                        print("Throttled endpoint {}: waiting {}s (Retry-After)".format(ep["id"], wait))
                        time.sleep(wait)
                    except (ValueError, TypeError):
                        pass
        for eid in sorted(throttled):
            if eid in inventory_map:
                rerun.add(eid)
    rerun = sorted(rerun)
    results = []
    for eid in rerun:
        result = discover_endpoint(inventory_map[eid], token, opener=opener, token_roles=roles)
        results.append(result)
        print("{id} {name:<12} {classification} HTTP={http} pages={pages} rows={rows}".format(
            id=result["inventory_id"], name=result["endpoint_name"],
            classification=result["classification"], http=result["http_status"] or "-",
            pages=result["pages"], rows=result["total_rows"]))
    # Merge new results with previous endpoint states, recompute permission
    # groups + workflow from the CURRENT merged state
    state = _merge_into_state(previous, results, roles)
    write_state_file(state)
    evidence = write_evidence(results, mode="resume")
    update_document(results, state=state)
    duration = round(time.monotonic() - started, 3)
    print("\nDiscovery run: " + state["workflow_state"])
    print("Evidence: " + str(evidence))
    _print_permission_queue(state.get("permission_groups", []))
    if state["workflow_state"] == WORKFLOW_AWAITING_APPROVAL:
        _print_approval_gate(state.get("permission_groups", []))
    return state["workflow_state"], results, state, evidence, duration


def results_or_None():
    return None


def show_status():
    state = load_state_file()
    if state is None:
        print("No discovery state found. Run --batch first.")
        return
    print("Agent version: {}".format(state.get("agent_version", "unknown")))
    print("Workflow state: {}".format(state.get("workflow_state", "unknown")))
    print("Last batch: {}".format(state.get("last_batch_execution", "never")))
    counts = {}
    for ep in state.get("endpoints", []) or []:
        cls = ep.get("classification", "UNKNOWN")
        counts[cls] = counts.get(cls, 0) + 1
    print("PASS count: {}".format(counts.get("PASS", 0)))
    print("PERMISSION_REQUIRED count: {}".format(counts.get("PERMISSION_REQUIRED", 0)))
    print("THROTTLED count: {}".format(counts.get("THROTTLED", 0)))
    print("API_ERROR count: {}".format(counts.get("API_ERROR", 0)))
    pending = [g for g in state.get("permission_groups", []) or []
               if g.get("approval_status") in ("REQUIRED", "ROLE_PRESENT_BUT_STILL_DENIED")]
    if pending:
        print("Pending permission groups:")
        for group in pending:
            print("  {} [{}]".format(group["permission"], group["approval_status"]))
    else:
        print("Pending permission groups: none")


WORKFLOW_UNKNOWN = "UNKNOWN"


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run read-only Microsoft Graph discovery v0.2")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="Test all enabled endpoints (v0.1 legacy)")
    group.add_argument("--batch", action="store_true", help="Autonomous batch discovery")
    group.add_argument("--resume", action="store_true", help="Resume discovery after a permission grant")
    group.add_argument("--status", action="store_true", help="Show persisted discovery state (offline)")
    inventory = load_inventory()
    aliases = {"directoryAuditLogs": "directoryAudits"}
    endpoint_names = tuple(sorted(
        {item["name"].lower() for item in inventory}
        | {item["path"].rstrip("/").rsplit("/", 1)[-1] for item in inventory}
        | set(aliases)
    ))
    group.add_argument("--endpoint", choices=endpoint_names)
    args = parser.parse_args(argv)

    if args.status:
        show_status()
        return 0

    try:
        if args.batch:
            workflow_state, _, _, _, _ = run_batch(inventory, load_env())
            return 0 if workflow_state in (WORKFLOW_COMPLETE, WORKFLOW_AWAITING_APPROVAL) else 1
        if args.resume:
            workflow_state, _, _, _, _ = run_resume(inventory, load_env())
            return 0 if workflow_state in (WORKFLOW_COMPLETE, WORKFLOW_AWAITING_APPROVAL) else 1
    except Exception as error:
        print("Discovery run: FAIL")
        print("Error: {}".format(error))
        return 1

    endpoint_key = aliases.get(args.endpoint, args.endpoint)
    enabled = [item for item in inventory if item.get("enabled", True)]
    selected = enabled if args.all else [
        item for item in enabled
        if item["name"].lower() == endpoint_key
        or item["path"].rstrip("/").rsplit("/", 1)[-1] == endpoint_key
    ]
    results = []
    try:
        token = acquire_token(load_env())
        roles = token_roles(token)
        for endpoint in selected:
            result = discover_endpoint(endpoint, token, token_roles=roles)
            results.append(result)
            print("{id} {name:<12} {classification} HTTP={http} pages={pages} rows={rows}".format(
                id=result["inventory_id"], name=result["endpoint_name"],
                classification=result["classification"], http=result["http_status"] or "-",
                pages=result["pages"], rows=result["total_rows"]))
    except Exception as error:
        print("Discovery run: FAIL")
        print("Evidence: unavailable")
        print("Inventory: /workspace/docs/api-inventory.md")
        return 1
    evidence = write_evidence(results, mode="manual")
    previous = load_state_file()
    if previous is not None:
        merged = _merge_into_state(previous, results, roles)
        write_state_file(merged)
        state_for_doc = merged
    else:
        endpoint_states = [_build_endpoint_state(r) for r in results]
        permission_groups = _recompute_permission_groups_from_states(endpoint_states, roles)
        workflow_state = _compute_workflow_state(endpoint_states)
        state_for_doc = _build_state(workflow_state, roles, endpoint_states, permission_groups)
        write_state_file(state_for_doc)
    update_document(results, state=state_for_doc)
    classifications = {result["classification"] for result in results}
    overall = "PASS" if classifications == {"PASS"} else "PARTIAL" if "PASS" in classifications else "FAIL"
    print("Discovery run: " + overall)
    print("Evidence: " + str(evidence))
    print("Inventory: /workspace/docs/api-inventory.md")
    return 0 if overall != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())