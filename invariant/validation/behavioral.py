
import numpy as np

from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph
from .base import BaseValidator, ValidationResult


class BehavioralValidator(BaseValidator):
    # this class was defined to analyze the divergence across multiple execution runs.

    def validate(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace]) -> ValidationResult:
        if len(traces) < 2:
            return ValidationResult(True, "behavioral", "Insufficient traces for behavioral analysis (need at least 2)")

        # Aggregate latencies per node across all traces
        node_latencies: dict[str, list[float]] = {}
        for trace in traces:
            for signal in trace.signals:
                if signal.node_id not in node_latencies:
                    node_latencies[signal.node_id] = []
                node_latencies[signal.node_id].append(signal.duration_ms)

        # calculate the variance and entropy (simplified) per node
        stats = {}
        high_variance_nodes = []

        for node_id, latencies in node_latencies.items():
            variance = float(np.var(latencies))
            mean = float(np.mean(latencies))
            cv = variance / (mean**2) if mean > 0 else 0 # coefficient of variation squared

            stats[node_id] = {
                "mean": mean,
                "variance": variance,
                "cv": cv
            }

            # arbitrary threshold for v1 "instability"
            if cv > 0.5:
                high_variance_nodes.append(node_id)

        pass_status = len(high_variance_nodes) == 0
        message = "Behavioral stability confirmed" if pass_status else f"High divergence in nodes: {', '.join(high_variance_nodes)}"

        return ValidationResult(
            pass_status=pass_status,
            validator_id="behavioral",
            message=message,
            metrics=stats
        )
