"""DivergenceAnalyzer: measure per-node divergence between baseline and perturbed runs."""

from __future__ import annotations

from typing import Any

import numpy as np

from invariant.instrumentation.tracer import ExecutionTrace


class DivergenceResult:
    """Per-node divergence analysis result.

    Attributes:
        node_id: The analyzed node.
        divergence_values: Sequence of normalized divergence values (one per
            perturbed trace).
        peak_divergence: Maximum observed divergence.
        mean_divergence: Mean divergence across all perturbed traces.
        onset_index: Index of the first perturbed trace where divergence
            exceeds the threshold.
        recovery_index: Index of the first perturbed trace where divergence
            drops back below the threshold after onset. ``None`` if recovery
            was not observed.
        threshold: Divergence threshold used for onset/recovery detection.
    """

    def __init__(
        self,
        node_id: str,
        divergence_values: list[float],
        threshold: float,
    ) -> None:
        self.node_id = node_id
        self.divergence_values = divergence_values
        self.threshold = threshold
        arr = np.array(divergence_values, dtype=float)
        self.peak_divergence: float = float(np.max(arr)) if len(arr) else 0.0
        self.mean_divergence: float = float(np.mean(arr)) if len(arr) else 0.0

        above = [i for i, v in enumerate(divergence_values) if v > threshold]
        self.onset_index: int | None = above[0] if above else None

        if self.onset_index is not None:
            below_after = [
                i
                for i in range(self.onset_index, len(divergence_values))
                if divergence_values[i] <= threshold
            ]
            self.recovery_index: int | None = below_after[0] if below_after else None
        else:
            self.recovery_index = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "divergence_values": self.divergence_values,
            "peak_divergence": self.peak_divergence,
            "mean_divergence": self.mean_divergence,
            "onset_index": self.onset_index,
            "recovery_index": self.recovery_index,
            "threshold": self.threshold,
        }


class DivergenceAnalyzer:
    """Compute per-node divergence between a baseline trace and perturbed traces.

    Divergence at a node is the normalized difference between its execution
    duration in a perturbed trace and its duration in the baseline:

        divergence(node, run_i) = |duration_perturbed - duration_baseline|
                                  / (duration_baseline + epsilon)

    This measure is dimensionless and comparable across nodes with different
    nominal latencies.

    Args:
        baseline: The reference (no-perturbation) trace.
        perturbed_traces: List of perturbed execution traces.
        threshold: Divergence value above which a node is considered divergent.

    Example::

        analyzer = DivergenceAnalyzer(baseline, runs)
        results = analyzer.analyze()
        for nid, result in results.items():
            print(f"{nid}: peak={result.peak_divergence:.3f}")
    """

    def __init__(
        self,
        baseline: ExecutionTrace,
        perturbed_traces: list[ExecutionTrace],
        threshold: float = 0.1,
    ) -> None:
        self._baseline = baseline
        self._perturbed = perturbed_traces
        self.threshold = threshold

    def analyze(self) -> dict[str, DivergenceResult]:
        """Compute divergence results for every node present in the baseline.

        Returns:
            Dict mapping node_id → DivergenceResult.
        """
        baseline_latencies = self._baseline.get_node_latencies()
        results: dict[str, DivergenceResult] = {}

        for node_id, base_dur in baseline_latencies.items():
            divergences: list[float] = []
            for trace in self._perturbed:
                pert_latencies = trace.get_node_latencies()
                pert_dur = pert_latencies.get(node_id, base_dur)
                div = abs(pert_dur - base_dur) / (base_dur + 1e-9)
                divergences.append(div)

            results[node_id] = DivergenceResult(
                node_id=node_id,
                divergence_values=divergences,
                threshold=self.threshold,
            )

        return results

    def summary(self) -> dict[str, Any]:
        """Return a compact summary of divergence across all nodes."""
        results = self.analyze()
        return {
            node_id: {
                "peak": r.peak_divergence,
                "mean": r.mean_divergence,
                "onset_index": r.onset_index,
                "recovery_index": r.recovery_index,
            }
            for node_id, r in results.items()
        }
