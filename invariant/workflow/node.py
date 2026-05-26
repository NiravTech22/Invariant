from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PortType(Enum):
    INPUT = "input"
    OUTPUT = "output"


@dataclass
class Port:
    name: str
    port_type: PortType
    data_type: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeConstraints:
    min_rate_hz: float | None = None
    max_latency_ms: float | None = None
    timeout_ms: float | None = None


@dataclass
class Node:
    """Purely declarative Node representation."""

    id: str
    node_type: str
    ports: list[Port]
    constraints: NodeConstraints = field(default_factory=NodeConstraints)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        # Validate node ID and ports
        if not self.id:
            raise ValueError("Node ID cannot be empty")

    @property
    def input_ports(self) -> list[Port]:
        return [p for p in self.ports if p.port_type == PortType.INPUT]

    @property
    def output_ports(self) -> list[Port]:
        return [p for p in self.ports if p.port_type == PortType.OUTPUT]
