"""Focused import-path regression for the G07-C public package surface.

This module pins the ``import collectors.workloads`` import contract:

* the bare package import must succeed (no TypeError, no circular
  import, no Dataclass field-ordering error);
* the two central public symbols the integration layer exposes
  (:class:`WorkloadEntry` and the canonical ``REGISTRY`` mapping) must
  be reachable through the package root;
* the registry must contain canonical ``G01-001..G01-020`` plus ``SP-A01``;
* the registry must be import-time validated (no duplicate ids, no
  unknown ids).

These assertions exist so a future change that reorders
``WorkloadEntry`` fields (or otherwise breaks the dataclass
construction) and silently regresses the public import path is caught
by the test suite, not by the first downstream consumer.
"""
from __future__ import annotations

import importlib
import sys
import unittest

import collectors.workloads as workloads_pkg
from collectors.workloads import REGISTRY, WorkloadEntry
from collectors.workloads.models import PersistenceMode
from collectors.workloads.registry import (
    EXPECTED_ENDPOINT_IDS,
    LineageContext,
    get_entry,
    iter_entries,
)


EXPECTED_IDS = tuple("G01-{:03d}".format(index) for index in range(1, 21)) + ("SP-A01",)


class PublicImportRegressionTests(unittest.TestCase):
    """Pins the public import contract of ``collectors.workloads``."""

    def test_bare_package_import_succeeds(self):
        # Fresh-import the package to exercise the full module graph.
        sys.modules.pop("collectors.workloads", None)
        module = importlib.import_module("collectors.workloads")
        self.assertIsNotNone(module)
        self.assertTrue(hasattr(module, "WorkloadEntry"))
        self.assertTrue(hasattr(module, "REGISTRY"))

    def test_workload_entry_is_exported_from_package_root(self):
        self.assertIs(WorkloadEntry, workloads_pkg.WorkloadEntry)

    def test_workload_entry_is_importable_from_models_submodule(self):
        from collectors.workloads.models import WorkloadEntry as WE
        self.assertIs(WE, WorkloadEntry)

    def test_registry_is_exported_from_package_root(self):
        self.assertIs(REGISTRY, workloads_pkg.REGISTRY)

    def test_registry_has_expected_entries(self):
        self.assertEqual(len(REGISTRY), len(EXPECTED_IDS))

    def test_registry_ids_match_expected_canonical_set(self):
        self.assertEqual(set(REGISTRY.keys()), set(EXPECTED_IDS))

    def test_registry_has_no_duplicates(self):
        self.assertEqual(len(list(REGISTRY.keys())), len(set(REGISTRY.keys())))

    def test_registry_has_no_unknown_endpoint_ids(self):
        unknown = set(REGISTRY) - set(EXPECTED_IDS)
        self.assertFalse(unknown, "unknown endpoints registered: " + repr(unknown))

    def test_every_entry_is_a_workload_entry_instance(self):
        for endpoint_id, entry in REGISTRY.items():
            self.assertIsInstance(entry, WorkloadEntry)
            self.assertEqual(entry.endpoint_id, endpoint_id)

    def test_every_entry_has_a_persistence_mode_member(self):
        for entry in REGISTRY.values():
            self.assertIsInstance(entry.persistence_mode, PersistenceMode)

    def test_get_entry_round_trips_for_every_endpoint(self):
        for endpoint_id in EXPECTED_IDS:
            self.assertIs(get_entry(endpoint_id), REGISTRY[endpoint_id])

    def test_iter_entries_returns_canonical_ids_in_order(self):
        ids = [entry.endpoint_id for entry in iter_entries()]
        self.assertEqual(ids, list(EXPECTED_IDS))


class PublicImportSmokeTests(unittest.TestCase):
    """Minimal smoke-import tests that mirror the runtime import path."""

    def test_import_collectors_workloads(self):
        # Mirrors: python -c "import collectors.workloads"
        importlib.import_module("collectors.workloads")

    def test_import_workload_entry_from_models(self):
        # Mirrors: python -c "from collectors.workloads.models import WorkloadEntry"
        from collectors.workloads.models import WorkloadEntry as WE
        self.assertTrue(callable(WE))

    def test_import_registry_and_assert_expected_entries(self):
        from collectors.workloads.registry import REGISTRY as R
        self.assertEqual(len(R), len(EXPECTED_IDS))

    def test_import_registry_helpers(self):
        # The dispatch helpers exposed by the registry must be importable.
        from collectors.workloads.registry import (
            LineageContext as LC,
            normalize_record,
            normalize_records,
            validate_registry,
        )
        self.assertTrue(callable(LC))
        self.assertTrue(callable(normalize_record))
        self.assertTrue(callable(normalize_records))
        self.assertTrue(callable(validate_registry))


if __name__ == "__main__":
    unittest.main()
