"""SensitivityAnalyzer: perturbation magnitude sweep to find stability thresholds."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from invariant.analysis.stability import StabilityAnalyzer, StabilityClass
from invariant.instrumentation.tracer import ExecutionTrace


class SensitivityPoint:
    """Result for a single perturbation magnitude in a sensitivity sweep.

    Attributes:
        magnitude: The perturbation magnitude at this point.
        stability_class: Stability classification for this magnitude.
        peak_divergence: Global peak divergence across all nodes.
        recovery_steps: Steps to recovery (None if no recovery observed).
    """

    def __init__(
        self,
        magnitude: float,
        stability_class: StabilityClass,
        peak_divergence: float,
        recovery_steps: int | None,
    ) -> None:
        self.magnitude = magnitude
        self.stability_class = stability_class
        self.peak_divergence = peak_divergence
        self.recovery_steps = recovery_steps

    def to_dict(self) -> dict[str, Any]:
        return {
            "magnitude": self.magnitude,
            "stability_class": self.stability_class.value,
            "peak_divergence": self.peak_divergence,
            "recovery_steps": self.recovery_steps,
        }


class SensitivityResult:
    """Result of a sensitivity sweep over perturbation magnitudes.

    Attributes:
        points: Ordered list of SensitivityPoint (one per magnitude).
        critical_threshold: The smallest magnitude at which the system
            transitions from STABLE to a less stable class. ``None`` if
            no transition was observed within the sweep range.
    """

    def __init__(self, points: list[SensitivityPoint]) -> None:
        self.points = points
        self.critical_threshold: float | None = self._find_threshold()

    def _find_threshold(self) -> float | None:
        for i in range(len(self.points) - 1):
            if (
                self.points[i].stability_class == StabilityClass.STABLE
                and self.points[i + 1].stability_class != StabilityClass.STABLE
            ):
                return self.points[i + 1].magnitude
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "critical_threshold": self.critical_threshold,
            "points": [p.to_dict() for p in self.points],
        }


class SensitivityAnalyzer:
    """Sweep perturbation magnitude to find where stability breaks down.

    Calls a user-supplied ``run_fn`` for each magnitude value to generate
    perturbed traces, then classifies stability at each point. The result
    identifies the critical threshold where the system transitions from
    STABLE to MARGINALLY_STABLE or UNSTABLE.

    Args:
        baseline: Reference trace without perturbations.
        magnitudes: Ordered list of perturbation magnitude values to sweep.
        run_fn: Callable that accepts a magnitude value and returns a list
            of perturbed ExecutionTrace objects.
        divergence_threshold: Threshold passed to StabilityAnalyzer.

    Example::

        def run_at(mag):
            pert = LatencyPerturbation(delay_ms=mag, ...)
            executor = DeterministicExecutor(workflow, perturbations=[pert])
            return [executor.run() for _ in range(5)]

        analyzer = SensitivityAnalyzer(baseline, [10, 20, 50, 100], run_at)
        result = analyzer.sweep()
        print(f"Critical threshold: {result.critical_threshold}")
    """

    def __init__(
        self,
        baseline: ExecutionTrace,
        magnitudes: list[float],
        run_fn: Callable[[float], list[ExecutionTrace]],
        divergence_threshold: float = 0.1,
    ) -> None:
        self._baseline = baseline
        self._magnitudes = sorted(magnitudes)
        self._run_fn = run_fn
        self.divergence_threshold = divergence_threshold

    def sweep(self) -> SensitivityResult:
        """Execute the full sensitivity sweep.

        Returns:
            SensitivityResult with all measurement points and critical threshold.
        """
        points: list[SensitivityPoint] = []

        for mag in self._magnitudes:
            perturbed = self._run_fn(mag)
            stability_analyzer = StabilityAnalyzer(
                baseline=self._baseline,
                perturbed_traces=perturbed,
                divergence_threshold=self.divergence_threshold,
            )
            result = stability_analyzer.analyze()
            points.append(
                SensitivityPoint(
                    magnitude=mag,
                    stability_class=result.classification,
                    peak_divergence=result.peak_divergence,
                    recovery_steps=result.recovery_steps,
                )
            )

        return SensitivityResult(points=points)
