"""Edge abstraction: data or control flow between two nodes."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class LatencyModel(BaseModel):
    """Transmission latency model for an edge.

    Args:
        nominal_ms: Baseline one-way transmission latency in milliseconds.
        jitter_ms: Maximum random jitter added on top of nominal latency.
    """

    nominal_ms: float = Field(default=0.0, ge=0.0)
    jitter_ms: float = Field(default=0.0, ge=0.0)


class ReliabilityModel(BaseModel):
    """Message reliability model for an edge.

    Args:
        drop_probability: Fraction of messages dropped under nominal conditions [0, 1].
    """

    drop_probability: float = Field(default=0.0, ge=0.0, le=1.0)


class Edge(BaseModel):
    """A data or control dependency between two nodes.

    Args:
        source_id: ID of the producing node.
        target_id: ID of the consuming node.
        data_type: Human-readable descriptor of what flows along this edge.
        latency_model: Transmission latency characteristics.
        reliability_model: Message drop characteristics.
        metadata: Arbitrary key-value data.

    Raises:
        ValueError: If source_id equals target_id (self-loops are not allowed).
    """

    source_id: str = Field(..., min_length=1)
    target_id: str = Field(..., min_length=1)
    data_type: str = Field(default="any", description="Type descriptor of transmitted data")
    latency_model: LatencyModel = Field(default_factory=LatencyModel)
    reliability_model: ReliabilityModel = Field(default_factory=ReliabilityModel)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        if self.source_id == self.target_id:
            raise ValueError(
                f"Self-loop detected: edge cannot connect node '{self.source_id}' to itself"
            )

    @property
    def edge_id(self) -> str:
        """Canonical string identifier for this edge."""
        return f"{self.source_id}->{self.target_id}"
