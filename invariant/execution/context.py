"""ExecutionContext: shared state passed between nodes during a single workflow run."""

from __future__ import annotations

from typing import Any

from invariant.core.node import HealthState
from invariant.execution.clock import SimulatedClock


class NodeRecord:
    """Captured record for a single node execution within a timestep.

    Attributes:
        node_id: ID of the node that was executed.
        timestep: The simulation step at which this record was captured.
        start_ms: Virtual clock time when execution began (ms).
        end_ms: Virtual clock time when execution completed (ms).
        inputs: A copy of the inputs the node received.
        outputs: A copy of the outputs the node produced.
        health: Health state of the node at execution time.
        dropped: True if the node's inputs were dropped by a perturbation.
        perturbations_applied: Names of perturbations active during this execution.
    """

    __slots__ = (
        "node_id",
        "timestep",
        "start_ms",
        "end_ms",
        "inputs",
        "outputs",
        "health",
        "dropped",
        "perturbations_applied",
    )

    def __init__(
        self,
        node_id: str,
        timestep: int,
        start_ms: float,
        end_ms: float,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
        health: HealthState,
        dropped: bool = False,
        perturbations_applied: list[str] | None = None,
    ) -> None:
        self.node_id = node_id
        self.timestep = timestep
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.inputs = inputs
        self.outputs = outputs
        self.health = health
        self.dropped = dropped
        self.perturbations_applied = perturbations_applied or []

    @property
    def duration_ms(self) -> float:
        """Wall (virtual) execution duration in milliseconds."""
        return self.end_ms - self.start_ms

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "node_id": self.node_id,
            "timestep": self.timestep,
            "start_ms": self.start_ms,
            "end_ms": self.end_ms,
            "duration_ms": self.duration_ms,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "health": self.health.value,
            "dropped": self.dropped,
            "perturbations_applied": self.perturbations_applied,
        }


class EdgeRecord:
    """Captured record for a single edge transmission within a timestep.

    Attributes:
        source_id: Producing node.
        target_id: Consuming node.
        timestep: Simulation step.
        data: The data transmitted (or None if dropped).
        latency_ms: Transmission latency applied (virtual ms).
        dropped: True if the message was dropped.
    """

    __slots__ = ("source_id", "target_id", "timestep", "data", "latency_ms", "dropped")

    def __init__(
        self,
        source_id: str,
        target_id: str,
        timestep: int,
        data: dict[str, Any] | None,
        latency_ms: float,
        dropped: bool = False,
    ) -> None:
        self.source_id = source_id
        self.target_id = target_id
        self.timestep = timestep
        self.data = data
        self.latency_ms = latency_ms
        self.dropped = dropped

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "timestep": self.timestep,
            "data": self.data,
            "latency_ms": self.latency_ms,
            "dropped": self.dropped,
        }


class ExecutionContext:
    """Shared mutable state for one complete workflow execution run.

    The context is threaded through every node execution and accumulates a
    complete record: per-node records, per-edge records, health states, and
    a log of all events. The simulated clock is owned by this context.

    Args:
        run_id: Unique identifier for this execution run.
        timestep: Which simulation step this context represents.
        clock: The SimulatedClock instance driving virtual time.
        active_perturbations: Names of perturbations active at the start.
    """

    def __init__(
        self,
        run_id: str,
        timestep: int,
        clock: SimulatedClock,
        active_perturbations: list[str] | None = None,
    ) -> None:
        self.run_id = run_id
        self.timestep = timestep
        self.clock = clock
        self.active_perturbations: list[str] = active_perturbations or []

        self._node_outputs: dict[str, dict[str, Any]] = {}
        self._node_records: list[NodeRecord] = []
        self._edge_records: list[EdgeRecord] = []
        self._health_states: dict[str, HealthState] = {}
        self._events: list[dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Node output management
    # ------------------------------------------------------------------

    def set_output(self, node_id: str, outputs: dict[str, Any]) -> None:
        """Store outputs produced by a node."""
        self._node_outputs[node_id] = outputs

    def get_output(self, node_id: str) -> dict[str, Any]:
        """Retrieve outputs previously stored for a node.

        Returns an empty dict if the node has not yet executed or was dropped.
        """
        return dict(self._node_outputs.get(node_id, {}))

    def gather_inputs(self, node_id: str, predecessor_ids: list[str]) -> dict[str, Any]:
        """Merge outputs from all predecessor nodes into a single inputs dict.

        Args:
            node_id: The consuming node (for logging only).
            predecessor_ids: IDs of all upstream nodes.

        Returns:
            Merged dict of all predecessor outputs keyed by source node ID.
        """
        merged: dict[str, Any] = {}
        for pred_id in predecessor_ids:
            pred_out = self.get_output(pred_id)
            merged[pred_id] = pred_out
        return merged

    # ------------------------------------------------------------------
    # Record management
    # ------------------------------------------------------------------

    def record_node(self, record: NodeRecord) -> None:
        """Append a node execution record."""
        self._node_records.append(record)
        self._health_states[record.node_id] = record.health

    def record_edge(self, record: EdgeRecord) -> None:
        """Append an edge transmission record."""
        self._edge_records.append(record)

    def log_event(self, label: str, extra: dict[str, Any] | None = None) -> None:
        """Log a timestamped event.

        Args:
            label: Short human-readable event description.
            extra: Optional additional context dict.
        """
        self._events.append(
            {
                "time_ms": self.clock.now(),
                "timestep": self.timestep,
                "label": label,
                **(extra or {}),
            }
        )

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    @property
    def node_records(self) -> list[NodeRecord]:
        return list(self._node_records)

    @property
    def edge_records(self) -> list[EdgeRecord]:
        return list(self._edge_records)

    @property
    def events(self) -> list[dict[str, Any]]:
        return list(self._events)

    @property
    def health_states(self) -> dict[str, HealthState]:
        return dict(self._health_states)

    def get_node_latencies(self) -> dict[str, float]:
        """Return per-node execution duration in ms for this context."""
        return {r.node_id: r.duration_ms for r in self._node_records}
