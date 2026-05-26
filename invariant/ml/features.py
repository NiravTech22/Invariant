
import numpy as np

from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph


class AggregatedFeatureExtractor:
    """Extracts aggregated features for ML supervision."""

    def extract(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace]) -> np.ndarray:
        # 1. Graph Features
        invariants = graph.get_invariants()
        graph_feats = [
            invariants["num_nodes"],
            invariants["num_edges"],
            invariants["depth"],
            invariants["fan_in_max"],
            invariants["fan_out_max"]
        ]

        # 2. Temporal Features (from traces)
        if not traces:
             return np.array(graph_feats + [0, 0, 0, 0])

        all_latencies = []
        for trace in traces:
            for signal in trace.signals:
                all_latencies.append(signal.duration_ms)

        temporal_feats = [
            np.mean(all_latencies),
            np.std(all_latencies),
            np.max(all_latencies),
            len(traces) # Sample size
        ]

        return np.array(graph_feats + temporal_feats, dtype=np.float32)
