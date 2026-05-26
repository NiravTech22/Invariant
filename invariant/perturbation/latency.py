"""LatencyPerturbation: delay a node's execution by a configurable amount."""

from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING, Any

from invariant.perturbation.base import BasePerturbation

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class LatencyMode(str, Enum):
    """Distribution used to sample the injected delay."""

    FIXED = "fixed"
    UNIFORM = "uniform"
    GAUSSIAN = "gaussian"


class LatencyPerturbation(BasePerturbation):
    """Inject a time delay into a node's virtual execution.

    The delay is applied to the SimulatedClock — never wall time — so
    determinism is guaranteed for equal seeds.

    Args:
        node_ids: Set of node IDs to target. ``None`` targets all nodes.
        mode: Sampling distribution for the delay magnitude.
        delay_ms: Fixed delay (used when mode is FIXED).
        min_ms: Lower bound for UNIFORM sampling.
        max_ms: Upper bound for UNIFORM / mean for GAUSSIAN sampling.
        std_ms: Standard deviation for GAUSSIAN mode.
        start_step: First simulation step at which the perturbation is active.
        end_step: Last simulation step (inclusive). ``None`` means indefinite.
        seed: RNG seed for reproducibility.

    Example::

        pert = LatencyPerturbation(
            node_ids={"planner"},
            mode=LatencyMode.UNIFORM,
            min_ms=10.0,
            max_ms=50.0,
            seed=42,
        )
    """

    def __init__(
        self,
        node_ids: set[str] | None = None,
        mode: LatencyMode | str = LatencyMode.FIXED,
        delay_ms: float = 0.0,
        min_ms: float = 0.0,
        max_ms: float = 0.0,
        std_ms: float = 0.0,
        start_step: int = 0,
        end_step: int | None = None,
        seed: int | None = None,
    ) -> None:
        self.node_ids = node_ids
        self.mode = LatencyMode(mode) if isinstance(mode, str) else mode
        self.delay_ms = delay_ms
        self.min_ms = min_ms
        self.max_ms = max_ms
        self.std_ms = std_ms
        self.start_step = start_step
        self.end_step = end_step
        self._rng = random.Random(seed)
        self._seed = seed

    def applies_to(self, node_id: str, timestep: int) -> bool:
        if self.node_ids is not None and node_id not in self.node_ids:
            return False
        if timestep < self.start_step:
            return False
        if self.end_step is not None and timestep > self.end_step:
            return False
        return True

    def apply(self, context: ExecutionContext, node_id: str) -> ExecutionContext:
        delay = self._sample_delay()
        if delay > 0:
            context.clock.advance(delay)
            context.log_event(
                "latency_injected",
                {"node_id": node_id, "delay_ms": delay, "mode": self.mode.value},
            )
        return context

    def _sample_delay(self) -> float:
        if self.mode == LatencyMode.FIXED:
            return max(0.0, self.delay_ms)
        if self.mode == LatencyMode.UNIFORM:
            return max(0.0, self._rng.uniform(self.min_ms, self.max_ms))
        # GAUSSIAN
        sample = self._rng.gauss(self.max_ms, self.std_ms)
        return max(0.0, sample)

    @property
    def description(self) -> str:
        if self.mode == LatencyMode.FIXED:
            return f"LatencyPerturbation(fixed={self.delay_ms:.1f}ms)"
        if self.mode == LatencyMode.UNIFORM:
            return f"LatencyPerturbation(uniform=[{self.min_ms:.1f}, {self.max_ms:.1f}]ms)"
        return f"LatencyPerturbation(gaussian(μ={self.max_ms:.1f}, σ={self.std_ms:.1f})ms)"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "LatencyPerturbation",
            "node_ids": list(self.node_ids) if self.node_ids is not None else None,
            "mode": self.mode.value,
            "delay_ms": self.delay_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "std_ms": self.std_ms,
            "start_step": self.start_step,
            "end_step": self.end_step,
            "seed": self._seed,
        }
