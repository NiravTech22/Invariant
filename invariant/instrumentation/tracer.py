"""ExecutionTrace: structured, serializable record of a single workflow execution."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class ExecutionTrace:
    """Complete record of one workflow execution run.

    Contains:
    - Experiment metadata (workflow name, run ID, timestamp, perturbations).
    - Per-node records: timing, inputs, outputs, health, dropped flag.
    - Per-edge records: transmission latency, dropped flag, data.
    - Events: anomalies, perturbation activations, health state changes.

    Traces serialize to JSON. They are the primary artifact produced by
    :class:`~invariant.execution.executor.DeterministicExecutor`.

    Args:
        run_id: Unique identifier for this run.
        workflow_name: Name of the workflow that was executed.
        timestep: Simulation step this trace represents.
        clock_end_ms: Virtual clock time at the end of execution.
        node_records: List of serialized node record dicts.
        edge_records: List of serialized edge record dicts.
        events: List of event dicts.
        perturbation_descriptions: Human-readable list of active perturbations.
        created_at: ISO-8601 wall-clock timestamp of when the trace was created.
    """

    def __init__(
        self,
        run_id: str,
        workflow_name: str,
        timestep: int,
        clock_end_ms: float,
        node_records: list[dict[str, Any]],
        edge_records: list[dict[str, Any]],
        events: list[dict[str, Any]],
        perturbation_descriptions: list[str],
        created_at: str,
    ) -> None:
        self.run_id = run_id
        self.workflow_name = workflow_name
        self.timestep = timestep
        self.clock_end_ms = clock_end_ms
        self.node_records = node_records
        self.edge_records = edge_records
        self.events = events
        self.perturbation_descriptions = perturbation_descriptions
        self.created_at = created_at

    @classmethod
    def from_context(
        cls,
        ctx: ExecutionContext,
        workflow_name: str,
        perturbation_descriptions: list[str] | None = None,
    ) -> "ExecutionTrace":
        """Construct an ExecutionTrace from a completed ExecutionContext.

        Args:
            ctx: The execution context after a full run.
            workflow_name: Name of the workflow that was executed.
            perturbation_descriptions: Human-readable perturbation names.

        Returns:
            A new ExecutionTrace instance.
        """
        return cls(
            run_id=ctx.run_id,
            workflow_name=workflow_name,
            timestep=ctx.timestep,
            clock_end_ms=ctx.clock.now(),
            node_records=[r.to_dict() for r in ctx.node_records],
            edge_records=[r.to_dict() for r in ctx.edge_records],
            events=ctx.events,
            perturbation_descriptions=perturbation_descriptions or [],
            created_at=datetime.now(tz=timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Derived metrics
    # ------------------------------------------------------------------

    def get_node_latencies(self) -> dict[str, float]:
        """Return a map of node_id → execution duration (ms)."""
        return {r["node_id"]: r["duration_ms"] for r in self.node_records}

    def get_total_duration_ms(self) -> float:
        """Return the total virtual execution duration for the workflow."""
        return self.clock_end_ms

    def is_nominal(self) -> bool:
        """Return True if no nodes were dropped or failed."""
        return all(not r["dropped"] for r in self.node_records)

    def get_dropped_nodes(self) -> list[str]:
        """Return IDs of nodes whose inputs were dropped."""
        return [r["node_id"] for r in self.node_records if r["dropped"]]

    def get_failed_nodes(self) -> list[str]:
        """Return IDs of nodes whose health state is 'failed'."""
        return [r["node_id"] for r in self.node_records if r["health"] == "failed"]

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "run_id": self.run_id,
            "workflow_name": self.workflow_name,
            "timestep": self.timestep,
            "clock_end_ms": self.clock_end_ms,
            "created_at": self.created_at,
            "perturbation_descriptions": self.perturbation_descriptions,
            "node_records": self.node_records,
            "edge_records": self.edge_records,
            "events": self.events,
        }

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionTrace":
        """Reconstruct an ExecutionTrace from a plain dict.

        Args:
            data: Dict as produced by :meth:`to_dict`.
        """
        return cls(
            run_id=data["run_id"],
            workflow_name=data["workflow_name"],
            timestep=data.get("timestep", 0),
            clock_end_ms=data["clock_end_ms"],
            node_records=data["node_records"],
            edge_records=data["edge_records"],
            events=data["events"],
            perturbation_descriptions=data.get("perturbation_descriptions", []),
            created_at=data.get("created_at", ""),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ExecutionTrace":
        """Reconstruct from a JSON string."""
        return cls.from_dict(json.loads(json_str))

    def __repr__(self) -> str:
        return (
            f"ExecutionTrace(run_id={self.run_id[:8]}…, "
            f"nodes={len(self.node_records)}, "
            f"duration={self.clock_end_ms:.2f}ms)"
        )
