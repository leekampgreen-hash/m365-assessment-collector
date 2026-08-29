import unittest

from capabilities import (
    Capability,
    CapabilityResolver,
    CollectionDecision,
    EntitlementState,
    FeatureStatus,
    RuntimeState,
    plan_collection,
    plan_security_evaluation,
)
from collectors.core import CollectorRuntime, RuntimeOptions, dict_source
from pathlib import Path


def sku(*plans):
    return {"service_plans": [
        {"servicePlanName": plan, "provisioningStatus": "Success"} for plan in plans
    ]}


class CapabilityResolverTests(unittest.TestCase):
    def test_basic_tenant_has_no_premium_capabilities(self):
        resolver = CapabilityResolver([sku("EXCHANGE_S_STANDARD")])
        self.assertEqual(resolver.resolve(Capability.ENTRA_P1).entitlement, EntitlementState.NOT_ENTITLED)
        self.assertEqual(resolver.resolve(Capability.ENTRA_P2).entitlement, EntitlementState.NOT_ENTITLED)

    def test_p1_enables_p1_but_not_p2(self):
        resolver = CapabilityResolver([sku("AAD_PREMIUM")])
        self.assertEqual(resolver.resolve(Capability.ENTRA_P1).entitlement, EntitlementState.ENTITLED)
        self.assertEqual(resolver.resolve(Capability.ENTRA_P2).entitlement, EntitlementState.NOT_ENTITLED)

    def test_p2_satisfies_p1_and_p2(self):
        resolver = CapabilityResolver([sku("AAD_PREMIUM_P2")])
        self.assertEqual(resolver.resolve(Capability.ENTRA_P1).entitlement, EntitlementState.ENTITLED)
        self.assertEqual(resolver.resolve(Capability.ENTRA_P2).entitlement, EntitlementState.ENTITLED)

    def test_unknown_plan_never_becomes_not_licensed(self):
        resolver = CapabilityResolver([sku("CUSTOM_PLAN")])
        self.assertEqual(resolver.resolve(Capability.ENTRA_P1).entitlement, EntitlementState.UNKNOWN)
        self.assertEqual(resolver.resolve(Capability.CONDITIONAL_ACCESS).entitlement, EntitlementState.UNKNOWN)
        self.assertEqual(resolver.resolve(Capability.CONDITIONAL_ACCESS).feature_status, FeatureStatus.UNKNOWN)

    def test_missing_persisted_service_plan_data_is_unknown(self):
        resolver = CapabilityResolver([])
        self.assertEqual(resolver.resolve(Capability.EXCHANGE).entitlement, EntitlementState.UNKNOWN)

    def test_workload_mapping_and_derived_capabilities_are_conservative(self):
        resolver = CapabilityResolver([sku("EXCHANGE_S_ENTERPRISE", "SHAREPOINTENTERPRISE", "ONEDRIVESTANDARD")])
        self.assertEqual(resolver.resolve(Capability.EXCHANGE).entitlement, EntitlementState.ENTITLED)
        self.assertEqual(resolver.resolve(Capability.SHAREPOINT).entitlement, EntitlementState.ENTITLED)
        self.assertEqual(resolver.resolve(Capability.ONEDRIVE).entitlement, EntitlementState.ENTITLED)
        self.assertEqual(resolver.resolve(Capability.M365_USAGE_REPORTS).entitlement, EntitlementState.UNKNOWN)


class CapabilityGateTests(unittest.TestCase):
    def test_not_licensed_does_not_invoke_collector(self):
        calls = []
        plan = plan_collection([Capability.ENTRA_P2], ["Policy.Read.All"], {Capability.ENTRA_P2: EntitlementState.NOT_ENTITLED}, ["Policy.Read.All"])
        if plan.decision is CollectionDecision.COLLECT:
            calls.append("graph")
        self.assertEqual(plan.decision, CollectionDecision.SKIP_NOT_LICENSED)
        self.assertEqual(plan.feature_status, FeatureStatus.NOT_LICENSED)
        self.assertEqual(calls, [])

    def test_unknown_capability_skips_safely(self):
        plan = plan_collection([Capability.IDENTITY_PROTECTION], [], {Capability.IDENTITY_PROTECTION: EntitlementState.UNKNOWN}, [])
        self.assertEqual(plan.decision, CollectionDecision.SKIP_CAPABILITY_UNKNOWN)

    def test_permission_is_distinct_from_license(self):
        plan = plan_collection([Capability.ENTRA_P1], ["Policy.Read.All"], {Capability.ENTRA_P1: EntitlementState.ENTITLED}, [])
        self.assertEqual(plan.decision, CollectionDecision.SKIP_PERMISSION_REQUIRED)
        self.assertEqual(plan.feature_status, FeatureStatus.PERMISSION_REQUIRED)

    def test_security_gate_does_not_emit_a_finding_when_unlicensed(self):
        plan = plan_security_evaluation([Capability.ENTRA_P2], {Capability.ENTRA_P2: EntitlementState.NOT_ENTITLED})
        self.assertEqual(plan.feature_status, FeatureStatus.NOT_LICENSED)
        self.assertEqual(plan.collector_status, "NOT_EXECUTED")
        self.assertEqual(plan.security_evaluation, "NOT_EXECUTED")

    def test_source_unavailable_is_distinct_from_license(self):
        plan = plan_security_evaluation([Capability.ENTRA_P1], {Capability.ENTRA_P1: EntitlementState.ENTITLED}, RuntimeState.SOURCE_UNAVAILABLE)
        self.assertEqual(plan.feature_status, FeatureStatus.SOURCE_UNAVAILABLE)

    def test_runtime_skips_before_graph_collector_is_constructed(self):
        reads = []
        runtime = CollectorRuntime(
            Path("config/api_inventory.json"),
            dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
            options=RuntimeOptions(
                tenant_resolver=lambda config: 1,
                http_open=lambda *args, **kwargs: reads.append(args),
                capability_gate=lambda spec: plan_collection(
                    spec.required_capabilities, spec.documented_permissions,
                    {Capability.ENTRA_P1: EntitlementState.NOT_ENTITLED},
                    spec.documented_permissions,
                ),
            ),
        )
        # The runtime validates auth before endpoint planning; use its private
        # execution seam to prove the gate precedes any collector transport.
        plan = runtime.options.capability_gate(runtime.find_spec("G01-011"))
        self.assertEqual(plan.decision, CollectionDecision.SKIP_NOT_LICENSED)
        self.assertEqual(reads, [])

    def test_usage_permission_gate_is_fail_closed_when_permission_missing(self):
        # USAGE-* endpoints declare only documented_permissions and no
        # required_capabilities. The runtime must still consult the gate so
        # they cannot execute (reach the usage transport) without the required
        # granted permission.
        from unittest.mock import Mock

        class TokenResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit=-1): return b'{"access_token":"token","expires_in":3600}'

        class CsvResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit=-1): return b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n"

        hits = []
        def opener(request, timeout=None):
            hits.append(request.full_url)
            if request.full_url.endswith("/token"):
                return TokenResponse()
            return CsvResponse()

        runtime = CollectorRuntime(
            Path("config/api_inventory.json"),
            dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
            options=RuntimeOptions(
                tenant_resolver=lambda config: 1,
                http_open=opener,
                # Reports.Read.All is NOT granted -> gate must deny.
                capability_gate=lambda spec: plan_collection(
                    spec.required_capabilities, spec.documented_permissions,
                    {}, granted_graph_permissions=[],
                ),
                collection_writer=Mock(),
            ),
        )
        summary = runtime.run(endpoint_id="USAGE-002")
        self.assertEqual(summary.runs[0].status, "SKIPPED")
        self.assertEqual(summary.runs[0].capability_decision, "SKIP_PERMISSION_REQUIRED")
        # No usage-report transport call, no token request: fail-closed.
        self.assertEqual(hits, [])

    def test_usage_permission_gate_still_reaches_transport_when_permitted(self):
        from unittest.mock import Mock

        class TokenResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit=-1): return b'{"access_token":"token","expires_in":3600}'

        class CsvResponse:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit=-1): return b"User Principal Name,Report Refresh Date\nuser@example.com,2026-08-20\n"

        hits = []
        def opener(request, timeout=None):
            hits.append(request.full_url)
            if request.full_url.endswith("/token"):
                return TokenResponse()
            return CsvResponse()

        writer = Mock()
        runtime = CollectorRuntime(
            Path("config/api_inventory.json"),
            dict_source({"GRAPH_TENANT_ID": "tenant", "GRAPH_CLIENT_ID": "client", "GRAPH_CLIENT_SECRET": "secret"}),
            options=RuntimeOptions(
                tenant_resolver=lambda config: 1,
                http_open=opener,
                # Reports.Read.All IS granted -> permitted execution must proceed.
                capability_gate=lambda spec: plan_collection(
                    spec.required_capabilities, spec.documented_permissions,
                    {}, granted_graph_permissions=spec.documented_permissions,
                ),
                collection_writer=writer,
            ),
        )
        summary = runtime.run(endpoint_id="USAGE-002")
        self.assertEqual(summary.runs[0].status, "PASS")
        # Token + one usage-report transport call proves it reached the transport.
        self.assertEqual(len(hits), 2)
        self.assertIn("getEmailActivityUserDetail", hits[1])
        writer.write_usage_report.assert_called_once()
