"""Deterministic execution engine for the Scenario Agent.

The engine exposes two top-level entry points:

* :meth:`ScenarioAgent.plan` -- produce a :class:`ScenarioPlan` for a
  caller-supplied :class:`ScenarioRequest`. The plan is deterministic
  and contains no caller-supplied secrets.
* :meth:`ScenarioAgent.execute` -- run a :class:`ScenarioPlan` against
  an injected executor and collect safe, evidence-only step results.

The engine is deliberately small. It does no I/O, performs no
Microsoft Graph calls, never logs secrets, and never mutates the
caller's request. Agentic / LLM reasoning happens *above* this layer;
it is the caller's job to translate a high-level goal into a
:class:`ScenarioRequest` against the registry.
"""
from __future__ import annotations

import time
import uuid
from typing import Dict, List, Optional

from .actions import (
    allowed_parameter_keys,
    declared_permissions_for,
    sanitize_action_parameters,
)
from .executor import DryRunScenarioExecutor, ScenarioActionExecutor
from .models import (
    STATUS_BLOCKED,
    STATUS_FAILED,
    STATUS_PARTIAL_SUCCESS,
    STATUS_PLANNED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    ScenarioActor,
    ScenarioExecutionResult,
    ScenarioPlan,
    ScenarioRequest,
    ScenarioStep,
    ScenarioStepResult,
    correlation_prefix,
    utcnow_iso,
)
from .registry import ScenarioRegistry
from .safety import ScenarioBlockedError, evaluate_safety


def _new_execution_id() -> str:
    return "exec-{0}".format(uuid.uuid4().hex)


def _new_plan_id() -> str:
    return "plan-{0}".format(uuid.uuid4().hex)


def _new_step_id(index: int) -> str:
    return "step-{0:03d}".format(index)


def _calculate_final_status(
    step_results: List[ScenarioStepResult],
) -> str:
    """Reduce per-step statuses into a single final status."""
    if not step_results:
        return STATUS_FAILED
    success = sum(1 for r in step_results if r.status == STATUS_SUCCESS)
    blocked = sum(1 for r in step_results if r.status == STATUS_BLOCKED)
    failed = sum(1 for r in step_results if r.status == STATUS_FAILED)
    if blocked:
        return STATUS_BLOCKED
    if failed == 0 and success == len(step_results):
        return STATUS_SUCCESS
    if success and failed:
        return STATUS_PARTIAL_SUCCESS
    return STATUS_FAILED


class ScenarioAgent:
    """Top-level orchestrator for planning and executing scenarios."""

    def __init__(
        self,
        registry: ScenarioRegistry,
        executor: Optional[ScenarioActionExecutor] = None,
        *,
        allow_destructive: bool = False,
        clock=None,
    ) -> None:
        self._registry = registry
        self._executor: ScenarioActionExecutor = executor or DryRunScenarioExecutor()
        self._allow_destructive = allow_destructive
        self._clock = clock or time.monotonic

    # ----- Properties -----------------------------------------------------

    @property
    def registry(self) -> ScenarioRegistry:
        return self._registry

    @property
    def executor(self) -> ScenarioActionExecutor:
        return self._executor

    @property
    def allow_destructive(self) -> bool:
        return self._allow_destructive

    # ----- Planning -------------------------------------------------------

    def plan(self, request: ScenarioRequest) -> ScenarioPlan:
        """Produce a :class:`ScenarioPlan` for ``request``.

        Raises :class:`ScenarioBlockedError` if the safety gate refuses
        the request. The plan is deterministic: given the same request
        and registry, two plans have identical content modulo their
        randomly generated ``plan_id`` / ``execution_id`` /
        ``correlation_id`` markers.
        """
        evaluate_safety(
            request,
            registry=self._registry,
            allow_destructive=self._allow_destructive,
        )

        scenario = self._registry.get(request.scenario_id)
        # safety gate guarantees ``scenario`` is not None
        assert scenario is not None

        execution_id = _new_execution_id()
        plan_id = _new_plan_id()
        correlation_id = correlation_prefix(execution_id)

        safe_params = sanitize_action_parameters(
            scenario.action_type,
            request.metadata.get("parameters"),
        )

        step = ScenarioStep(
            step_id=_new_step_id(1),
            action_type=scenario.action_type,
            declared_permissions=list(declared_permissions_for(scenario.action_type)),
            safe_parameters=safe_params,
            expected_evidence=list(scenario.expected_observable_evidence),
        )

        return ScenarioPlan(
            plan_id=plan_id,
            execution_id=execution_id,
            scenario_id=scenario.scenario_id,
            actor_id=request.actor.actor_id if request.actor is not None else None,
            correlation_id=correlation_id,
            declared_permissions=list(scenario.required_delegated_permissions),
            steps=[step],
            expected_evidence=list(scenario.expected_observable_evidence),
            cleanup_required=scenario.cleanup_required,
            cleanup_scenario_id=scenario.cleanup_scenario_id,
            risk_level=scenario.risk_level,
            status=STATUS_PLANNED,
        )

    # ----- Execution ------------------------------------------------------

    def execute(
        self,
        plan: ScenarioPlan,
        actor: Optional[ScenarioActor] = None,
    ) -> ScenarioExecutionResult:
        """Execute ``plan`` against the injected executor.

        ``actor`` is supplied by the caller for the duration of
        execution; it is *never* persisted in the result. The result
        contains safe, evidence-only data. The execution is
        deterministic: there are no hidden retries; a failed step
        aborts subsequent steps.
        """
        scenario = self._registry.get(plan.scenario_id)
        if scenario is None:
            raise ScenarioBlockedError(
                "SCENARIO_UNKNOWN",
                "Plan refers to unknown scenario: {0!r}".format(plan.scenario_id),
            )

        # If the plan was built for an actor, the caller must supply
        # the same actor (or a compatible one) at execute time. This
        # is a defensive check, not a re-authorization.
        if plan.actor_id is not None and actor is None:
            raise ScenarioBlockedError(
                "ACTOR_MISSING",
                "Plan requires an actor; none supplied at execute time.",
            )
        if actor is not None and plan.actor_id is not None:
            if actor.actor_id != plan.actor_id:
                raise ScenarioBlockedError(
                    "ACTOR_UNAUTHORIZED",
                    "Supplied actor does not match the planned actor.",
                )

        started_at = utcnow_iso()
        start_clock = self._clock()

        step_results: List[ScenarioStepResult] = []
        for step in plan.steps:
            result = self._executor.execute(step, actor, plan)
            step_results.append(result)
            if result.status in (STATUS_FAILED, STATUS_BLOCKED):
                break

        completed_at = utcnow_iso()
        duration = self._clock() - start_clock
        final_status = _calculate_final_status(step_results)

        final_evidence: List[str] = [plan.correlation_id]
        for result in step_results:
            final_evidence.extend(result.evidence_labels)

        return ScenarioExecutionResult(
            execution_id=plan.execution_id,
            correlation_id=plan.correlation_id,
            scenario_id=plan.scenario_id,
            actor_id=plan.actor_id,
            status=final_status,
            started_at=started_at,
            completed_at=completed_at,
            duration=duration,
            step_results=step_results,
            final_evidence=final_evidence,
            declared_permissions=list(plan.declared_permissions),
            cleanup_required=plan.cleanup_required,
            cleanup_scenario_id=plan.cleanup_scenario_id,
            risk_level=plan.risk_level,
        )

    # ----- Convenience ----------------------------------------------------

    def plan_and_execute(
        self,
        request: ScenarioRequest,
    ) -> ScenarioExecutionResult:
        """Plan ``request`` and immediately execute the resulting plan.

        The actor on ``request`` (if any) is forwarded to the executor
        so dry-run evidence can record the actor's logical id.
        """
        plan = self.plan(request)
        return self.execute(plan, actor=request.actor)


__all__ = ["ScenarioAgent"]