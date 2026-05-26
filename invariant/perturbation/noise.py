"""NoisePerturbation: inject noise into numeric node outputs."""

from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING, Any

from invariant.perturbation.base import BasePerturbation

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class NoiseDistribution(str, Enum):
    """Distribution used to sample noise magnitude."""

    GAUSSIAN = "gaussian"
    UNIFORM = "uniform"


class NoisePerturbation(BasePerturbation):
    """Add numerical noise to a node's output values.

    Noise is applied after a node executes, before its outputs reach
    downstream nodes. Only numeric (int/float) values in the output dict
    are perturbed; non-numeric values pass through unchanged.

    Args:
        node_ids: Set of node IDs to target. ``None`` targets all nodes.
        distribution: Noise sampling distribution.
        magnitude: For GAUSSIAN: standard deviation; for UNIFORM: half-width.
        start_step: First step at which noise is injected.
        end_step: Last step (inclusive). ``None`` means indefinite.
        seed: RNG seed.

    Example::

        noise = NoisePerturbation(
            node_ids={"perception"},
            distribution=NoiseDistribution.GAUSSIAN,
            magnitude=0.05,
            seed=99,
        )
    """

    def __init__(
        self,
        node_ids: set[str] | None = None,
        distribution: NoiseDistribution | str = NoiseDistribution.GAUSSIAN,
        magnitude: float = 0.01,
        start_step: int = 0,
        end_step: int | None = None,
        seed: int | None = None,
    ) -> None:
        self.node_ids = node_ids
        self.distribution = (
            NoiseDistribution(distribution) if isinstance(distribution, str) else distribution
        )
        self.magnitude = magnitude
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
        outputs = context.get_output(node_id)
        if not outputs:
            return context

        noisy_outputs: dict[str, Any] = {}
        for key, value in outputs.items():
            if isinstance(value, (int, float)):
                noisy_outputs[key] = value + self._sample_noise()
            else:
                noisy_outputs[key] = value

        context.set_output(node_id, noisy_outputs)
        context.log_event(
            "noise_injected",
            {
                "node_id": node_id,
                "distribution": self.distribution.value,
                "magnitude": self.magnitude,
            },
        )
        return context

    def _sample_noise(self) -> float:
        if self.distribution == NoiseDistribution.GAUSSIAN:
            return self._rng.gauss(0.0, self.magnitude)
        return self._rng.uniform(-self.magnitude, self.magnitude)

    @property
    def description(self) -> str:
        return f"NoisePerturbation({self.distribution.value}, magnitude={self.magnitude:.4f})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "NoisePerturbation",
            "node_ids": list(self.node_ids) if self.node_ids is not None else None,
            "distribution": self.distribution.value,
            "magnitude": self.magnitude,
            "start_step": self.start_step,
            "end_step": self.end_step,
            "seed": self._seed,
        }
