"""StabilityAnalyzer: Lyapunov-inspired stability classification of workflow traces."""

from __future__ import annotations

from enum import Enum
from typing import Any

import numpy as np

from invariant.analysis.divergence import DivergenceAnalyzer
from invariant.instrumentation.tracer import ExecutionTrace


class StabilityClass(str, Enum):
    """Stability classification for a workflow under perturbation."""

    STABLE = "stable"
    MARGINALLY_STABLE = "marginally_stable"
    UNSTABLE = "unstable"


class StabilityResult:
    """Result of a stability analysis.

    A workflow is classified as:

    - **STABLE** if divergence at all nodes is monotonically non-increasing
      after perturbation is removed (Lyapunov sense) and recovers within
      the observation window.
    - **MARGINALLY STABLE** if divergence is bounded but does not
      monotonically decrease — the system oscillates or holds a small
      non-zero deviation.
    - **UNSTABLE** if divergence grows without bound or exceeds the threshold
      and never recovers.

    Attributes:
        classification: The stability class.
        evidence: Supporting evidence dict (per-node data).
        peak_divergence: Global maximum divergence across all nodes and runs.
        recovery_steps: Number of perturbed runs before the system returns
            below the divergence threshold. ``None`` if no recovery was observed.
        node_classifications: Per-node stability classifications.
    """

    def __init__(
        self,
        classification: StabilityClass,
        evidence: dict[str, Any],
        peak_divergence: float,
        recovery_steps: int | None,
        node_classifications: dict[str, StabilityClass],
    ) -> None:
        self.classification = classification
        self.evidence = evidence
        self.peak_divergence = peak_divergence
        self.recovery_steps = recovery_steps
        self.node_classifications = node_classifications

    def to_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification.value,
            "peak_divergence": self.peak_divergence,
            "recovery_steps": self.recovery_steps,
            "node_classifications": {k: v.value for k, v in self.node_classifications.items()},
            "evidence": self.evidence,
        }


class StabilityAnalyzer:
    """Classify workflow stability from a set of perturbed execution traces.

    Applies a Lyapunov-inspired convergence check: after perturbation ends
    (or across all runs if perturbation is sustained), does the per-node
    divergence from the baseline decrease monotonically?

    Args:
        baseline: Reference trace without perturbations.
        perturbed_traces: Ordered list of perturbed traces (earliest first).
        divergence_threshold: Normalized divergence value above which a node
            is considered divergent.
        monotone_window: Number of consecutive traces that must show decreasing
            divergence to declare convergence.

    Example::

        analyzer = StabilityAnalyzer(baseline, runs)
        result = analyzer.analyze()
        print(result.classification)
    """

    def __init__(
        self,
        baseline: ExecutionTrace,
        perturbed_traces: list[ExecutionTrace],
        divergence_threshold: float = 0.1,
        monotone_window: int = 3,
    ) -> None:
        self._baseline = baseline
        self._perturbed = perturbed_traces
        self.divergence_threshold = divergence_threshold
        self.monotone_window = monotone_window

    def analyze(self) -> StabilityResult:
        """Run stability analysis and return a classified result.

        Returns:
            StabilityResult with classification, evidence, and per-node data.
        """
        div_analyzer = DivergenceAnalyzer(
            self._baseline, self._perturbed, threshold=self.divergence_threshold
        )
        divergence_results = div_analyzer.analyze()

        node_classifications: dict[str, StabilityClass] = {}
        evidence: dict[str, Any] = {}

        for node_id, div_result in divergence_results.items():
            vals = div_result.divergence_values
            node_cls = self._classify_node(vals, div_result.onset_index, div_result.recovery_index)
            node_classifications[node_id] = node_cls
            evidence[node_id] = div_result.to_dict()

        # Global classification: most severe node classification wins
        if any(v == StabilityClass.UNSTABLE for v in node_classifications.values()):
            global_cls = StabilityClass.UNSTABLE
        elif any(v == StabilityClass.MARGINALLY_STABLE for v in node_classifications.values()):
            global_cls = StabilityClass.MARGINALLY_STABLE
        else:
            global_cls = StabilityClass.STABLE

        all_divergences = [v for dr in divergence_results.values() for v in dr.divergence_values]
        peak_divergence = float(max(all_divergences)) if all_divergences else 0.0

        # Global recovery: maximum recovery_index across nodes, None if any never recovered
        recovery_indices = [dr.recovery_index for dr in divergence_results.values()]
        if all(ri is not None for ri in recovery_indices):
            recovery_steps: int | None = max(recovery_indices)  # type: ignore[type-var]
        else:
            recovery_steps = None

        return StabilityResult(
            classification=global_cls,
            evidence=evidence,
            peak_divergence=peak_divergence,
            recovery_steps=recovery_steps,
            node_classifications=node_classifications,
        )

    def _classify_node(
        self,
        divergences: list[float],
        onset_index: int | None,
        recovery_index: int | None,
    ) -> StabilityClass:
        if not divergences:
            return StabilityClass.STABLE

        arr = np.array(divergences, dtype=float)
        max_div = float(np.max(arr))

        # Never exceeded threshold → stable
        if max_div <= self.divergence_threshold:
            return StabilityClass.STABLE

        # Exceeded threshold but recovered → check if recovery is monotone
        if recovery_index is not None:
            # Look at the post-onset window: is divergence monotonically decreasing?
            if onset_index is not None and recovery_index > onset_index:
                window = divergences[onset_index : recovery_index + 1]
                if self._is_non_increasing(window, tolerance=1e-6):
                    return StabilityClass.STABLE
            return StabilityClass.MARGINALLY_STABLE

        # Never recovered and divergence is growing → unstable
        if len(arr) >= 2 and float(arr[-1]) > float(arr[0]) + self.divergence_threshold:
            return StabilityClass.UNSTABLE

        return StabilityClass.MARGINALLY_STABLE

    @staticmethod
    def _is_non_increasing(values: list[float], tolerance: float = 1e-6) -> bool:
        for i in range(len(values) - 1):
            if values[i + 1] > values[i] + tolerance:
                return False
        return True
