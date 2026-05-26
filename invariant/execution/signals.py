from dataclasses import dataclass, field
from typing import Any


@dataclass
class ExecutionSignal:
    """Captured signal from a single node execution."""

    node_id: str
    start_time: float
    end_time: float
    input_data_hashes: dict[str, str] = field(default_factory=dict)
    output_data_hashes: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        return (self.end_time - self.start_time) * 1000


@dataclass
class WorkflowExecutionTrace:
    """Full trace of a workflow execution run."""

    run_id: str
    timestamp: float
    signals: list[ExecutionSignal] = field(default_factory=list)
    perturbations_applied: list[dict[str, Any]] = field(default_factory=list)

    def add_signal(self, signal: ExecutionSignal):
        self.signals.append(signal)

    def get_node_latencies(self) -> dict[str, float]:
        return {s.node_id: s.duration_ms for s in self.signals}
