"""FaultPropagationAnalyzer: trace how a perturbation at one node affects downstream nodes."""

from __future__ import annotations

from typing import Any

from invariant.analysis.divergence import DivergenceAnalyzer
from invariant.core.graph import WorkflowGraph
from invariant.instrumentation.tracer import ExecutionTrace


class FaultImpact:
    """Impact record for a single node in the fault propagation graph.

    Attributes:
        node_id: The impacted node.
        mean_divergence: Mean divergence from baseline across perturbed runs.
        peak_divergence: Maximum divergence observed.
        onset_index: First run index where divergence exceeded threshold.
        distance_from_source: Graph hop distance from the perturbed node.
    """

    def __init__(
        self,
        node_id: str,
        mean_divergence: float,
        peak_divergence: float,
        onset_index: int | None,
        distance_from_source: int,
    ) -> None:
        self.node_id = node_id
        self.mean_divergence = mean_divergence
        self.peak_divergence = peak_divergence
        self.onset_index = onset_index
        self.distance_from_source = distance_from_source

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mean_divergence": self.mean_divergence,
            "peak_divergence": self.peak_divergence,
            "onset_index": self.onset_index,
            "distance_from_source": self.distance_from_source,
        }


class FaultPropagationResult:
    """Result of a fault propagation analysis.

    Attributes:
        source_node_id: The node where the perturbation was injected.
        impacted_nodes: Dict mapping node_id → FaultImpact for all nodes
            affected above the divergence threshold.
        propagation_graph: Adjacency representation of affected nodes.
        total_affected: Number of nodes impacted above threshold.
    """

    def __init__(
        self,
        source_node_id: str,
        impacted_nodes: dict[str, FaultImpact],
        propagation_graph: dict[str, list[str]],
    ) -> None:
        self.source_node_id = source_node_id
        self.impacted_nodes = impacted_nodes
        self.propagation_graph = propagation_graph
        self.total_affected = len(impacted_nodes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_node_id": self.source_node_id,
            "total_affected": self.total_affected,
            "impacted_nodes": {k: v.to_dict() for k, v in self.impacted_nodes.items()},
            "propagation_graph": self.propagation_graph,
        }


class FaultPropagationAnalyzer:
    """Trace fault propagation from a perturbed source node through the workflow graph.

    Given a perturbation applied to ``source_node_id``, computes which
    downstream nodes show elevated divergence from baseline, how large the
    impact is, and when it appears.

    Args:
        graph: The workflow graph (used to trace downstream paths).
        baseline: Reference trace without perturbations.
        perturbed_traces: Ordered list of perturbed traces.
        source_node_id: The node where the fault originates.
        divergence_threshold: Minimum divergence to count as impacted.

    Example::

        analyzer = FaultPropagationAnalyzer(graph, baseline, runs, "perception")
        result = analyzer.analyze()
        print(f"Affected nodes: {result.total_affected}")
    """

    def __init__(
        self,
        graph: WorkflowGraph,
        baseline: ExecutionTrace,
        perturbed_traces: list[ExecutionTrace],
        source_node_id: str,
        divergence_threshold: float = 0.05,
    ) -> None:
        self._graph = graph
        self._baseline = baseline
        self._perturbed = perturbed_traces
        self.source_node_id = source_node_id
        self.divergence_threshold = divergence_threshold

    def analyze(self) -> FaultPropagationResult:
        """Run fault propagation analysis.

        Returns:
            FaultPropagationResult with impacted node details and graph.
        """
        div_analyzer = DivergenceAnalyzer(
            self._baseline,
            self._perturbed,
            threshold=self.divergence_threshold,
        )
        divergence_results = div_analyzer.analyze()

        # BFS to compute distance from source
        distances: dict[str, int] = {self.source_node_id: 0}
        queue = [self.source_node_id]
        while queue:
            current = queue.pop(0)
            for succ in self._graph.successors(current):
                if succ not in distances:
                    distances[succ] = distances[current] + 1
                    queue.append(succ)

        impacted: dict[str, FaultImpact] = {}
        for node_id, div_result in divergence_results.items():
            if div_result.peak_divergence > self.divergence_threshold:
                impacted[node_id] = FaultImpact(
                    node_id=node_id,
                    mean_divergence=div_result.mean_divergence,
                    peak_divergence=div_result.peak_divergence,
                    onset_index=div_result.onset_index,
                    distance_from_source=distances.get(node_id, -1),
                )

        # Build propagation sub-graph of impacted nodes
        prop_graph: dict[str, list[str]] = {}
        for node_id in impacted:
            succs = [s for s in self._graph.successors(node_id) if s in impacted]
            prop_graph[node_id] = succs

        return FaultPropagationResult(
            source_node_id=self.source_node_id,
            impacted_nodes=impacted,
            propagation_graph=prop_graph,
        )
