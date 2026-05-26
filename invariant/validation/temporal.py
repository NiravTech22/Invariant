
from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph
from .base import BaseValidator, ValidationResult


class TemporalValidator(BaseValidator):
    """Validates execution timing against node-level constraints."""

    def validate(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace]) -> ValidationResult:
        if not traces:
            return ValidationResult(False, "temporal", "No execution traces found")

        # Analyze the latest trace
        trace = traces[-1]
        violations = []
        node_stats = {}

        for signal in trace.signals:
            node = graph.get_node(signal.node_id)
            latency = signal.duration_ms
            node_stats[signal.node_id] = latency

            if node.constraints.max_latency_ms is not None:
                if latency > node.constraints.max_latency_ms:
                    violations.append(f"{signal.node_id} latency {latency:.2f}ms exceeds budget {node.constraints.max_latency_ms}ms")

        pass_status = len(violations) == 0
        message = "Temporal constraints satisfied" if pass_status else f"Temporal violations: {len(violations)}"

        return ValidationResult(
            pass_status=pass_status,
            validator_id="temporal",
            message=message,
            metrics={
                "latencies": node_stats,
                "violation_count": len(violations),
                "violations": violations
            }
        )
