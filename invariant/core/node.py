"""Node abstraction: a single software module in a robotics workflow pipeline."""

from __future__ import annotations

from collections.abc import Callable
from enum import Enum
from typing import Any, cast

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    """Semantic role of a node in the robotics stack."""

    PERCEPTION = "perception"
    PLANNING = "planning"
    CONTROL = "control"
    COMMS = "comms"
    ORCHESTRATOR = "orchestrator"
    SAFETY = "safety"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    UNKNOWN = "unknown"


class HealthState(str, Enum):
    """Runtime health classification of a node."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class LatencyBounds(BaseModel):
    """Expected execution latency bounds for a node (milliseconds)."""

    min_ms: float = Field(default=0.0, ge=0.0, description="Minimum expected execution time")
    max_ms: float = Field(
        default=10.0, ge=0.0, description="Maximum expected execution time (budget)"
    )

    def model_post_init(self, __context: Any) -> None:
        if self.min_ms > self.max_ms:
            raise ValueError(f"min_ms ({self.min_ms}) must be ≤ max_ms ({self.max_ms})")


class Node(BaseModel):
    """A single software module in a robotics workflow pipeline.

    A node represents one component of the stack (e.g., a perception module,
    a path planner, a controller). It carries an optional execution function
    that the executor calls at runtime; when absent the node is treated as
    a passive pass-through.

    Args:
        node_id: Unique identifier within the workflow.
        node_type: Semantic role label.
        latency_bounds: Expected min/max execution duration in milliseconds.
        exec_fn: Optional callable that takes a dict of inputs and returns outputs.
        metadata: Arbitrary key-value data carried through traces.

    Raises:
        ValueError: If node_id is empty.
    """

    node_id: str = Field(..., min_length=1, description="Unique node identifier")
    node_type: NodeType = Field(default=NodeType.UNKNOWN)
    latency_bounds: LatencyBounds = Field(default_factory=LatencyBounds)
    exec_fn: Callable[..., Any] | None = Field(
        default=None, exclude=True, description="Execution function; excluded from serialization"
    )
    metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = {"arbitrary_types_allowed": True}

    def execute(self, inputs: dict[str, Any]) -> dict[str, Any]:
        """Invoke the node's execution function.

        Args:
            inputs: Key-value map of input data from upstream edges.

        Returns:
            Key-value map of outputs for downstream edges. Returns inputs
            unchanged when no exec_fn is registered (pass-through behaviour).
        """
        if self.exec_fn is None:
            return dict(inputs)
        return cast(dict[str, Any], self.exec_fn(inputs))
