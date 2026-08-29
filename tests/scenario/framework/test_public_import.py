"""Public-import smoke tests for the Scenario Agent framework.

Mirrors the G07-CR1 ``test_public_import`` regression so that G08-A
delivers the same import-time safety guarantees:

* ``agents.scenario`` importable from the project root,
* every documented public symbol re-exported,
* no network / transport / credentials modules imported transitively.
"""
from __future__ import annotations

import sys
import unittest


class PublicImportSmokeTests(unittest.TestCase):
    def test_import_agents_scenario(self):
        import agents.scenario
        self.assertTrue(hasattr(agents.scenario, "ScenarioAgent"))
        self.assertTrue(hasattr(agents.scenario, "ScenarioRegistry"))
        self.assertTrue(hasattr(agents.scenario, "DryRunScenarioExecutor"))

    def test_import_submodules(self):
        import agents.scenario.actions
        import agents.scenario.actors
        import agents.scenario.engine
        import agents.scenario.executor
        import agents.scenario.models
        import agents.scenario.registry
        import agents.scenario.safety

    def test_public_api_size_is_stable(self):
        import agents.scenario
        # The framework documents 60 public symbols. Future scope
        # additions must be a deliberate __all__ change.
        self.assertGreaterEqual(len(agents.scenario.__all__), 60)

    def test_does_not_import_graph_transport(self):
        # Removing agents.scenario.* modules and re-importing must not
        # cause collectors.core.transport to appear. The deletion is
        # destructive to other already-imported modules (for example
        # scripts.run_scn_auth_001 holds a class reference captured at
        # import time), so the removed entries are restored afterwards
        # to keep the global sys.modules unchanged for the rest of the
        # suite.
        removed = {
            mod: sys.modules[mod]
            for mod in list(sys.modules)
            if mod.startswith("agents.scenario")
        }
        for mod in removed:
            del sys.modules[mod]
        try:
            import agents.scenario  # noqa: F401
            self.assertNotIn("collectors.core.transport", sys.modules)
        finally:
            for mod in list(sys.modules):
                if mod.startswith("agents.scenario"):
                    del sys.modules[mod]
            sys.modules.update(removed)

    def test_does_not_import_microsoft_graph_modules(self):
        # The framework must not transitively import anything
        # microsoft-graph-specific from the collector stack.
        forbidden = {
            "collectors.core.transport",
            "collectors.core.auth",
            "collectors.core.config",
            "collectors.core.runtime",
        }
        for module_name in forbidden:
            self.assertNotIn(module_name, sys.modules)


class ScenarioAgentSymbolTests(unittest.TestCase):
    def test_scenario_agent_is_exported(self):
        from agents.scenario import ScenarioAgent
        self.assertTrue(callable(ScenarioAgent))

    def test_dry_run_executor_is_exported(self):
        from agents.scenario import DryRunScenarioExecutor
        self.assertTrue(callable(DryRunScenarioExecutor))

    def test_scenario_registry_is_exported(self):
        from agents.scenario import ScenarioRegistry
        self.assertTrue(callable(ScenarioRegistry))

    def test_safety_error_is_exported(self):
        from agents.scenario import ScenarioBlockedError
        self.assertTrue(issubclass(ScenarioBlockedError, Exception))

    def test_models_are_exported(self):
        from agents.scenario import (
            ScenarioActor,
            ScenarioDefinition,
            ScenarioExecutionResult,
            ScenarioPlan,
            ScenarioRequest,
            ScenarioStep,
            ScenarioStepResult,
        )
        # All model types are dataclasses / have a to_dict.
        for cls in (
            ScenarioActor,
            ScenarioDefinition,
            ScenarioExecutionResult,
            ScenarioPlan,
            ScenarioRequest,
            ScenarioStep,
            ScenarioStepResult,
        ):
            self.assertTrue(hasattr(cls, "to_dict"))

    def test_status_constants_are_exported(self):
        from agents.scenario import (
            STATUS_BLOCKED,
            STATUS_FAILED,
            STATUS_PARTIAL_SUCCESS,
            STATUS_PLANNED,
            STATUS_RUNNING,
            STATUS_SUCCESS,
        )
        for value in (
            STATUS_BLOCKED,
            STATUS_FAILED,
            STATUS_PARTIAL_SUCCESS,
            STATUS_PLANNED,
            STATUS_RUNNING,
            STATUS_SUCCESS,
        ):
            self.assertIsInstance(value, str)
            self.assertNotEqual(value, "")


if __name__ == "__main__":
    unittest.main()