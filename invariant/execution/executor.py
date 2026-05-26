"""DeterministicExecutor: runs a workflow graph with full trace capture.

Determinism guarantee: given the same workflow, the same set of perturbations,
and the same seed, the executor produces byte-identical traces. This is
enforced by using only the SimulatedClock (no wall time) and seeded RNGs
passed in through perturbations.
"""

from __future__ import annotations

import uuid
from typing import Any

from invariant.core.node import HealthState
from invariant.core.workflow import Workflow
from invariant.execution.clock import SimulatedClock
from invariant.execution.context import EdgeRecord, ExecutionContext, NodeRecord
from invariant.execution.scheduler import TopologicalScheduler
from invariant.instrumentation.tracer import ExecutionTrace


class ExecutionError(RuntimeError):
    """Raised when node execution fails during a run.

    Attributes:
        node_id: The node that failed.
        context: The ExecutionContext at the time of failure.
        cause: The underlying exception.
    """

    def __init__(self, node_id: str, context: ExecutionContext, cause: Exception) -> None:
        self.node_id = node_id
        self.context = context
        self.cause = cause
        super().__init__(
            f"Node '{node_id}' failed at timestep {context.timestep} "
            f"(virtual time {context.clock.now():.3f} ms): {cause}"
        )


class DeterministicExecutor:
    """Runs a Workflow deterministically with optional perturbations.

    The executor iterates nodes in topological order using a SimulatedClock.
    Each node:
      1. Has perturbations applied to the context (may inject latency, drop
         inputs, or modify outputs).
      2. Executes its exec_fn (or pass-through if none).
      3. Has its execution record written to the context.

    Results are collected in an ExecutionTrace that can be analyzed or
    serialized.

    Args:
        workflow: The Workflow to execute.
        perturbations: List of BasePerturbation instances to apply. Applied
            in order for each node.
        initial_time_ms: Virtual clock start time in milliseconds.

    Raises:
        ExecutionError: If a node's exec_fn raises an exception during run.
    """

    def __init__(
        self,
        workflow: Workflow,
        perturbations: list[Any] | None = None,
        initial_time_ms: float = 0.0,
    ) -> None:
        self.workflow = workflow
        self.perturbations: list[Any] = perturbations or []
        self.initial_time_ms = initial_time_ms
        self._scheduler = TopologicalScheduler(workflow.graph)

    def run(self, run_id: str | None = None, timestep: int = 0) -> ExecutionTrace:
        """Execute the workflow once and return a complete trace.

        Args:
            run_id: Identifier for this run. Generated automatically if None.
            timestep: Simulation step counter (used for multi-step experiments).

        Returns:
            ExecutionTrace containing all node records, edge records, and events.

        Raises:
            ExecutionError: If any node raises an exception.
        """
        run_id = run_id or str(uuid.uuid4())
        clock = SimulatedClock(initial_time_ms=self.initial_time_ms)

        active_names = [p.description for p in self.perturbations]
        ctx = ExecutionContext(
            run_id=run_id,
            timestep=timestep,
            clock=clock,
            active_perturbations=active_names,
        )

        plan = self._scheduler.get_execution_plan()

        for node_id in plan:
            node = self.workflow.graph.get_node(node_id)

            # Gather inputs from all predecessors
            pred_ids = self.workflow.graph.predecessors(node_id)
            inputs = ctx.gather_inputs(node_id, pred_ids)

            # Record the node's start time BEFORE any perturbation-induced latency
            # so that duration_ms captures the full observable delay.
            start_ms = clock.now()

            # Apply perturbations (may mutate ctx: advance clock, drop inputs, etc.)
            dropped = False
            applied_perturbation_names: list[str] = []
            for pert in self.perturbations:
                if pert.applies_to(node_id, timestep):
                    ctx = pert.apply(ctx, node_id)
                    applied_perturbation_names.append(pert.description)
                    if ctx.get_output(node_id + "__dropped__"):
                        dropped = True

            # Record edge transmissions from predecessors
            for pred_id in pred_ids:
                pred_edge = None
                try:
                    pred_edge = self.workflow.graph.get_edge(pred_id, node_id)
                except KeyError:
                    pass
                edge_latency = pred_edge.latency_model.nominal_ms if pred_edge else 0.0
                ctx.record_edge(
                    EdgeRecord(
                        source_id=pred_id,
                        target_id=node_id,
                        timestep=timestep,
                        data=ctx.get_output(pred_id) if not dropped else None,
                        latency_ms=edge_latency,
                        dropped=dropped,
                    )
                )

            # Execute node
            outputs: dict[str, Any] = {}
            health = HealthState.HEALTHY

            if dropped:
                health = HealthState.DEGRADED
                ctx.log_event(
                    "node_input_dropped",
                    {"node_id": node_id, "perturbations": applied_perturbation_names},
                )
                outputs = {}
            else:
                try:
                    outputs = node.execute(inputs)
                except Exception as exc:
                    health = HealthState.FAILED
                    ctx.log_event(
                        "node_execution_failed",
                        {"node_id": node_id, "error": str(exc)},
                    )
                    raise ExecutionError(node_id=node_id, context=ctx, cause=exc) from exc

            # Advance clock by nominal execution time (midpoint of bounds)
            nominal_exec_ms = (node.latency_bounds.min_ms + node.latency_bounds.max_ms) / 2.0
            clock.advance(nominal_exec_ms)
            end_ms = clock.now()

            ctx.set_output(node_id, outputs)
            ctx.record_node(
                NodeRecord(
                    node_id=node_id,
                    timestep=timestep,
                    start_ms=start_ms,
                    end_ms=end_ms,
                    inputs=inputs,
                    outputs=outputs,
                    health=health,
                    dropped=dropped,
                    perturbations_applied=applied_perturbation_names,
                )
            )

        return ExecutionTrace.from_context(
            ctx=ctx,
            workflow_name=self.workflow.metadata.name,
            perturbation_descriptions=active_names,
        )
