#!/usr/bin/env python3
"""CLI entry point for the Collector framework.

Usage examples (offline-safe):

    python -m collectors.run_collector --endpoint G01-001 --dry-run
    python -m collectors.run_collector --all --dry-run
    python -m collectors.run_collector --all --inventory path/to/inventory.json

What this CLI guarantees:

- ``--dry-run`` MUST NOT request a token and MUST NOT call Microsoft
  Graph. It only loads the inventory, validates selection, and prints a
  concise summary.
- The CLI never prints credentials, tokens, ``Authorization`` headers,
  or the raw env file contents.
- Errors are deterministic and never include a secret value.

What this CLI does NOT do:

- Persist tokens.
- Write to a database.
- Modify Entra permissions.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen
from typing import Optional, Sequence

from collectors.core import (
    PASS,
    CollectorRuntime,
    RuntimeError_,
    RuntimeOptions,
    RuntimeSummary,
)
from collectors.core.tenant import (
    TrustedTenantResolutionError,
    resolve_trusted_tenant,
)
from collectors.core.config import (
    AuthConfigError,
    dict_source,
    env_file_source,
    env_source,
)
from collectors.core.results import safe_dumps
from collectors.persistence import CollectionWriter, dispatch_persistence, open_database_connection
from collectors.core.models import CollectionResult, EndpointSpec


DEFAULT_INVENTORY = Path("config/api_inventory.json")
DEFAULT_ENV_FILE = Path("secrets/collector.env")
DEFAULT_PERSISTENCE_ENV_FILE = Path("secrets/graph-agent-postgres-runtime.env")
DEFAULT_PERSISTENCE_PASSWORD_FILE = Path("/run/secrets/graph_agent_runtime_password")
def _trusted_tenant_resolver(config, connection=None):
    """Resolve the internal surrogate from the authenticated Entra identity."""
    try:
        return resolve_trusted_tenant(config, connection)
    except TrustedTenantResolutionError as exc:
        raise RuntimeError_(str(exc)) from exc


def _database_tenant_resolver(connection):
    return lambda config: _trusted_tenant_resolver(config, connection)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="collectors.run_collector",
        description="Run a Collector framework workload (offline-safe in --dry-run mode).",
    )
    parser.add_argument("--endpoint", help="Single endpoint id (e.g. G01-001).")
    parser.add_argument("--security-rule", help="Registered deterministic Security rule id.")
    parser.add_argument("--onedrive-audit", action="store_true", help="Collect the bounded OneDrive Audit.SharePoint feed.")
    parser.add_argument(
        "--sharepoint-settings", action="store_true", help="Collect SharePoint tenant settings (G01-020)."
    )
    parser.add_argument(
        "--sharepoint-audit", action="store_true", help="Collect the bounded SharePoint Audit.SharePoint feed."
    )
    parser.add_argument(
        "--sharepoint-sites", action="store_true", help="Collect SharePoint site URLs."
    )
    parser.add_argument(
        "--intune-compliance", action="store_true", help="Collect Intune managed-device compliance."
    )
    parser.add_argument(
        "--granted-graph-permissions", nargs="*", default=(),
        help="Explicit app permissions granted to this collector identity.",
    )
    parser.add_argument(
        "--endpoints",
        nargs="+",
        default=None,
        help="Whitespace-separated list of endpoint ids.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Execute every enabled endpoint in the inventory.",
    )
    parser.add_argument(
        "--inventory",
        default=str(DEFAULT_INVENTORY),
        help="Path to inventory JSON (default: config/api_inventory.json).",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_FILE),
        help=(
            "Path to the auth env file used when GRAPH_* env vars are "
            "not already set (default: secrets/collector.env)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Load and validate configuration/inventory only; no token, no Graph calls.",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=3,
        help="Per-endpoint retry budget (default: 3).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit the runtime summary as JSON to stdout.",
    )
    return parser


def _select_auth_source(args, env_override=None):
    """Return a config source that prefers process env, then env file.

    The returned source NEVER logs or prints its contents. The source
    is used for both dry-run validation (where the file is read but no
    token is requested) and for normal execution.

    For ``--dry-run`` we DO read the env file to validate that the
    required variables are present; this is OFFLINE because no token
    endpoint is contacted.
    """
    proc_env = env_override if env_override is not None else os.environ
    if all(proc_env.get(k) for k in ("GRAPH_TENANT_ID", "GRAPH_CLIENT_ID", "GRAPH_CLIENT_SECRET")):
        return env_source(proc_env)
    env_path = Path(args.env_file)
    if env_path.exists():
        return env_file_source(env_path)
    # Fall back to a process-env-only source; ``load_auth_config`` will
    # then report the missing variable names.
    return env_source(proc_env)


def _build_persistence():
    connection = open_database_connection(
        env_file=DEFAULT_PERSISTENCE_ENV_FILE,
        password_file=DEFAULT_PERSISTENCE_PASSWORD_FILE,
    )
    return connection, CollectionWriter(connection, dispatch_persistence)


def collect_and_persist_sharepoint_settings(*, tenant_id, transport, connection, spec):
    """Collect the singleton G01-020 response and persist it through the registry."""
    from collectors.security import SharePointTenantSettingsCollector
    from collectors.workloads.registry import normalize_records

    writer = CollectionWriter(connection, dispatch_persistence)
    collection_run_id = writer.begin_collection_run(
        tenant_id=tenant_id,
        endpoint_ids=[spec.endpoint_id],
    )
    endpoint_run_id = writer.begin_endpoint_run(
        collection_run_id=collection_run_id,
        tenant_id=tenant_id,
        spec=spec,
    )
    result = CollectionResult(endpoint_id=spec.endpoint_id, status="ERROR")
    try:
        collected = SharePointTenantSettingsCollector(transport).collect()
        if collected.error_classification is not None:
            result.error_classification = collected.error_classification
            result.error_message = collected.error_classification
            result.http_status = collected.http_status
            return result
        record = {
            "sharingCapability": collected.raw_sharing_capability,
            "defaultSharingLinkType": collected.default_sharing_link_type,
            "externalUserExpirationRequired": collected.external_user_expiration_required,
            "externalUserExpirationInDays": collected.external_user_expiration_in_days,
            "fileAnonymousLinkType": collected.file_anonymous_link_type,
            "folderAnonymousLinkType": collected.folder_anonymous_link_type,
            "requireAnonymousLinksExpireInDays": collected.require_anonymous_links_expire_in_days,
            "allowGuestUserSharing": collected.allow_guest_user_sharing,
        }
        records = normalize_records(
            spec.endpoint_id,
            [record],
            {
                "tenant_id": tenant_id,
                "collection_run_id": collection_run_id,
                "endpoint_run_id": endpoint_run_id,
                "observed_at": collected.observation.observed_at,
            },
        )
        from collectors.core.runtime import NormalizedCollection
        writer.write(NormalizedCollection(
            endpoint_id=spec.endpoint_id,
            workload=spec.workload,
            data_domain=spec.data_domain,
            collection_timestamp=collected.observation.observed_at,
            tenant_id=tenant_id,
            source_metadata={},
            records=records,
        ))
        result = CollectionResult(
            endpoint_id=spec.endpoint_id,
            status=PASS,
            http_status=collected.http_status,
            rows=1,
            persisted_rows=1,
        )
        return result
    finally:
        writer.complete_endpoint_run(endpoint_run_id=endpoint_run_id, result=result)
        writer.complete_collection_run(collection_run_id=collection_run_id, results=[result])


def _dry_run_summary(
    runtime: CollectorRuntime,
    *,
    endpoint: Optional[str],
    endpoints: Optional[Sequence[str]],
    all_enabled: bool,
) -> dict:
    """Resolve the selection for dry-run WITHOUT requesting a token.

    Returns a dict with safe, credential-free information.
    """
    specs = runtime.resolve_selection(
        endpoint_id=endpoint,
        endpoint_ids=endpoints,
        all_enabled=all_enabled,
    )
    return {
        "mode": "dry-run",
        "inventory_path": str(runtime.inventory_path),
        "selected_endpoint_ids": [s.endpoint_id for s in specs],
        "selected_count": len(specs),
        "no_token_requested": True,
        "no_graph_requested": True,
    }


def _format_summary(summary: RuntimeSummary) -> dict:
    return {
        "runs": [r.to_dict() for r in summary.runs],
        "auth_error_classification": (
            summary.auth_error.classification if summary.auth_error is not None else None
        ),
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit:
        return 2

    selected_count = int(bool(args.endpoint)) + int(bool(args.endpoints)) + int(bool(args.all)) + int(bool(args.security_rule)) + int(args.onedrive_audit) + int(args.sharepoint_settings) + int(args.sharepoint_audit) + int(args.sharepoint_sites) + int(args.intune_compliance)
    if selected_count == 0 and not args.dry_run:
        parser.error("one of --endpoint, --endpoints, --all, --security-rule, --onedrive-audit, --sharepoint-settings, --sharepoint-audit, or --sharepoint-sites is required")
    if selected_count > 1:
        parser.error("only one of --endpoint, --endpoints, --all, --security-rule, --onedrive-audit, --sharepoint-settings, --sharepoint-audit, or --sharepoint-sites may be provided")
    if args.sharepoint_settings:
        args.endpoint = "G01-020"
    if args.sharepoint_audit:
        args.endpoint = "SP-A01"

    inventory_path = Path(args.inventory)
    if not inventory_path.exists():
        print(
            "ERROR: inventory not found at {}\n".format(inventory_path),
            file=sys.stderr,
        )
        return 2

    auth_source = _select_auth_source(args)

    options = RuntimeOptions(max_retries=args.max_retries, tenant_resolver=_trusted_tenant_resolver)
    if args.intune_compliance and args.dry_run:
        print(safe_dumps({"mode": "dry-run", "collector": "intune_compliance", "no_token_requested": True, "no_graph_requested": True}) if args.json else "dry-run: collector=intune_compliance no_token_requested=True no_graph_requested=True")
        return 0
    if args.intune_compliance and not args.dry_run:
        try:
            from collectors.core.config import load_auth_config
            from collectors.core.auth import CollectorTokenProvider
            from collectors.core.transport import GraphTransport
            from collectors.intune_compliance import collect_and_persist_intune_compliance, REQUIRED_PERMISSION
            if REQUIRED_PERMISSION not in args.granted_graph_permissions:
                print("ERROR: missing required permission: {}".format(REQUIRED_PERMISSION), file=sys.stderr)
                return 3
            database_connection, _ = _build_persistence()
            auth_config = load_auth_config(auth_source)
            tenant_id = _trusted_tenant_resolver(auth_config, database_connection)
            transport = GraphTransport(CollectorTokenProvider(auth_config, http_open=urlopen).get_token, url_open=urlopen)
            result = collect_and_persist_intune_compliance(tenant_id=tenant_id, transport=transport, connection=database_connection)
            database_connection.close()
            print(safe_dumps({"intune_compliance": result}) if args.json else "intune compliance run complete")
            return 0
        except Exception as exc:
            print("ERROR: {}".format(type(exc).__name__), file=sys.stderr)
            return 3
    if args.onedrive_audit and args.dry_run:
        print(safe_dumps({"mode": "dry-run", "collector": "onedrive_audit", "no_token_requested": True, "no_graph_requested": True}) if args.json else "dry-run: collector=onedrive_audit no_token_requested=True no_graph_requested=True")
        return 0
    if args.onedrive_audit and not args.dry_run:
        try:
            from collectors.core.config import load_auth_config
            from collectors.onedrive_audit import collect_and_persist_onedrive_audit
            database_connection, _ = _build_persistence()
            auth_config = load_auth_config(auth_source)
            tenant_id = _trusted_tenant_resolver(auth_config, database_connection)
            spec = EndpointSpec(
                endpoint_id="OD-AUDIT", name="OneDrive Audit.SharePoint",
                path="", workload="OneDrive", permission="ActivityFeed.Read",
            )
            writer = CollectionWriter(database_connection, dispatch_persistence)
            collection_run_id = writer.begin_collection_run(tenant_id=tenant_id, endpoint_ids=[spec.endpoint_id])
            endpoint_run_id = writer.begin_endpoint_run(
                collection_run_id=collection_run_id, tenant_id=tenant_id, spec=spec,
            )
            end = datetime.now(timezone.utc)
            try:
                metrics = collect_and_persist_onedrive_audit(
                    tenant_id=tenant_id,
                    auth_config=auth_config,
                    connection=database_connection,
                    url_open=urlopen,
                    start=end - timedelta(hours=4),
                    end=end,
                    collected_at=end.isoformat(),
                    collection_run_id=collection_run_id,
                    endpoint_run_id=endpoint_run_id,
                )
                result = CollectionResult(endpoint_id=spec.endpoint_id, status="PASS", rows=metrics["normalized"], persisted_rows=metrics["persisted"])
            except Exception:
                result = CollectionResult(endpoint_id=spec.endpoint_id, status="ERROR", error_classification="SOURCE_FAILURE", error_message="COLLECTION_FAILED")
                raise
            finally:
                writer.complete_endpoint_run(endpoint_run_id=endpoint_run_id, result=result)
                writer.complete_collection_run(collection_run_id=collection_run_id, results=[result])
            print(safe_dumps({"onedrive_audit": metrics}) if args.json else "onedrive audit run complete")
            return 0
        except Exception as exc:
            print("ERROR: {}".format(type(exc).__name__), file=sys.stderr)
            return 3
    if args.sharepoint_audit and args.dry_run:
        print(safe_dumps({"mode": "dry-run", "collector": "sharepoint_audit", "no_token_requested": True, "no_graph_requested": True}) if args.json else "dry-run: collector=sharepoint_audit no_token_requested=True no_graph_requested=True")
        return 0
    if args.sharepoint_audit and not args.dry_run:
        try:
            from collectors.core.config import load_auth_config
            from collectors.sharepoint_audit import collect_and_persist_sharepoint_audit
            database_connection, _ = _build_persistence()
            auth_config = load_auth_config(auth_source)
            tenant_id = _trusted_tenant_resolver(auth_config, database_connection)
            spec = EndpointSpec(
                endpoint_id="SP-A01", name="SharePoint Audit.SharePoint",
                path="", workload="SharePoint", permission="ActivityFeed.Read",
            )
            writer = CollectionWriter(database_connection, dispatch_persistence)
            collection_run_id = writer.begin_collection_run(tenant_id=tenant_id, endpoint_ids=[spec.endpoint_id])
            endpoint_run_id = writer.begin_endpoint_run(
                collection_run_id=collection_run_id, tenant_id=tenant_id, spec=spec,
            )
            end = datetime.now(timezone.utc)
            try:
                metrics = collect_and_persist_sharepoint_audit(
                    tenant_id=tenant_id,
                    auth_config=auth_config,
                    connection=database_connection,
                    url_open=urlopen,
                    start=end - timedelta(hours=4),
                    end=end,
                    collected_at=end.isoformat(),
                    collection_run_id=collection_run_id,
                    endpoint_run_id=endpoint_run_id,
                )
                result = CollectionResult(endpoint_id=spec.endpoint_id, status="PASS", rows=metrics["normalized"], persisted_rows=metrics["persisted"])
            except Exception:
                result = CollectionResult(endpoint_id=spec.endpoint_id, status="ERROR", error_classification="SOURCE_FAILURE", error_message="COLLECTION_FAILED")
                raise
            finally:
                writer.complete_endpoint_run(endpoint_run_id=endpoint_run_id, result=result)
                writer.complete_collection_run(collection_run_id=collection_run_id, results=[result])
            print(safe_dumps({"sharepoint_audit": metrics}) if args.json else "sharepoint audit run complete")
            return 0
        except Exception as exc:
            print("ERROR: {}".format(type(exc).__name__), file=sys.stderr)
            return 3
    if args.sharepoint_sites:
        if args.dry_run:
            print(safe_dumps({"mode": "dry-run", "collector": "sharepoint_sites", "no_token_requested": True, "no_graph_requested": True}) if args.json else "dry-run: collector=sharepoint_sites no_token_requested=True no_graph_requested=True")
            return 0
        try:
            from collectors.core.config import load_auth_config
            from collectors.core.auth import CollectorTokenProvider
            from collectors.core.transport import GraphTransport
            from collectors.sharepoint_sites import collect_sharepoint_site_urls
            database_connection, _ = _build_persistence()
            auth_config = load_auth_config(auth_source)
            tenant_id = _trusted_tenant_resolver(auth_config, database_connection)
            token_provider = CollectorTokenProvider(auth_config, http_open=urlopen)
            transport = GraphTransport(token_provider.get_token, url_open=urlopen)
            result = collect_sharepoint_site_urls(tenant_id=tenant_id, auth_config=auth_config, transport=transport)
            database_connection.close()
            print(safe_dumps({"sharepoint_sites": result}) if args.json else "sharepoint sites run complete")
            return 0
        except Exception as exc:
            print("ERROR: {}".format(type(exc).__name__), file=sys.stderr)
            return 3

    if args.sharepoint_settings and not args.dry_run:
        try:
            from collectors.core.config import load_auth_config
            from collectors.core.transport import GraphTransport

            database_connection, _ = _build_persistence()
            auth_config = load_auth_config(auth_source)
            tenant_id = _trusted_tenant_resolver(auth_config, database_connection)
            runtime = CollectorRuntime(
                inventory_path=inventory_path,
                auth_source=auth_source,
                options=options,
            )
            spec = runtime.resolve_selection(endpoint_id="G01-020", endpoint_ids=None, all_enabled=False)[0]
            transport = runtime.build_transport(runtime.build_token_provider(auth_config).get_token)
            result = collect_and_persist_sharepoint_settings(
                tenant_id=tenant_id,
                transport=transport,
                connection=database_connection,
                spec=spec,
            )
            payload = {"sharepoint_settings": result.to_dict()}
            if args.json:
                print(safe_dumps(payload))
            else:
                print("sharepoint settings run complete")
            return 0 if result.status == PASS else 1
        except Exception as exc:
            print("ERROR: {}".format(type(exc).__name__), file=sys.stderr)
            return 3
    # Dry-run path: resolve selection, do NOT request a token, do NOT call Graph
    # or open a database connection.
    if args.dry_run:
        try:
            runtime = CollectorRuntime(
                inventory_path=inventory_path,
                auth_source=auth_source,
                options=options,
            )
        except Exception as exc:
            print("ERROR: failed to load inventory: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
            return 2
        # Validate selection and inventory before any output is printed.
        try:
            payload = _dry_run_summary(
                runtime,
                endpoint=args.endpoint,
                endpoints=args.endpoints,
                all_enabled=args.all,
            )
        except RuntimeError_ as exc:
            print("ERROR: {}".format(exc), file=sys.stderr)
            return 3
        # Validate the auth config in dry-run too -- the source has
        # NOT contacted any token endpoint, but we still want to know
        # whether the env vars would be present for a real run.
        try:
            runtime.build_auth_config()
            payload["auth_config_present"] = True
        except AuthConfigError as exc:
            payload["auth_config_present"] = False
            payload["auth_config_error"] = str(exc)
        # Also count enabled specs for sanity output.
        payload["enabled_endpoint_count"] = len(runtime.enabled_specs())
        if args.json:
            print(safe_dumps(payload))
        else:
            print(
                "dry-run: inventory={} selected={} enabled_total={} "
                "auth_config_present={} no_token_requested=True no_graph_requested=True".format(
                    payload["inventory_path"],
                    payload["selected_endpoint_ids"],
                    payload["enabled_endpoint_count"],
                    payload["auth_config_present"],
                )
            )
        return 0

    try:
        database_connection, collection_writer = _build_persistence()
        options.tenant_resolver = _database_tenant_resolver(database_connection)
        from capabilities import plan_collection
        from capabilities.persistence import CapabilityQueryService
        def capability_gate(spec):
            tenant_id = _trusted_tenant_resolver(runtime.build_auth_config(), database_connection)
            capabilities = CapabilityQueryService.from_connection(database_connection, tenant_id).capabilities()
            entitlements = {item["capability"]: item["entitlement"] for item in capabilities}
            return plan_collection(spec.required_capabilities, spec.documented_permissions, entitlements, args.granted_graph_permissions)
        runtime = CollectorRuntime(
            inventory_path=inventory_path,
            auth_source=auth_source,
            options=options,
            database_connection=database_connection,
            collection_writer=collection_writer,
        )
        options.capability_gate = capability_gate
        if args.security_rule:
            from collectors.security import SecurityOrchestrator
            outcome = SecurityOrchestrator(
                runtime, database_connection, granted_graph_permissions=tuple(args.granted_graph_permissions),
            ).run(args.security_rule)
            payload = {"security": {key: (value.to_dict() if hasattr(value, "to_dict") else str(value)) for key, value in outcome.items()}}
            if args.json:
                print(safe_dumps(payload))
            else:
                print("security run complete: {}".format(args.security_rule))
            return 0 if outcome["collection"].status in (PASS, "SKIPPED") else 1
        summary = runtime.run(endpoint_id=args.endpoint, endpoint_ids=args.endpoints, all_enabled=args.all)
    except (RuntimeError_, RuntimeError) as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 3
    payload = _format_summary(summary)
    if args.json:
        print(safe_dumps(payload))
    else:
        print("collector run complete: {} endpoint(s)".format(len(summary.runs)))
    return 0 if all(run.status == PASS for run in summary.runs) else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print("ERROR: unexpected failure: {}: {}".format(type(exc).__name__, exc), file=sys.stderr)
        raise SystemExit(1)
