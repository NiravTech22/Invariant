"""OverloadPerturbation: simulate a node exceeding its execution time budget."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from invariant.perturbation.base import BasePerturbation

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class OverloadPerturbation(BasePerturbation):
    """Simulate a node taking longer than its expected execution window.

    This perturbation advances the simulated clock by an extra delay on top
    of the node's nominal execution time, causing all downstream nodes to
    start later. This is useful for testing scheduler resilience when one
    component becomes a bottleneck.

    The overload delay is sampled from a uniform distribution between
    ``min_overload_ms`` and ``max_overload_ms``.

    Args:
        node_ids: Set of node IDs to overload. ``None`` targets all nodes.
        min_overload_ms: Minimum extra delay added to the simulated clock.
        max_overload_ms: Maximum extra delay.
        start_step: First simulation step at which overload is active.
        end_step: Last simulation step (inclusive). ``None`` means indefinite.
        seed: RNG seed for reproducible delay sampling.

    Example::

        overload = OverloadPerturbation(
            node_ids={"planner"},
            min_overload_ms=50.0,
            max_overload_ms=200.0,
            seed=7,
        )
    """

    def __init__(
        self,
        node_ids: set[str] | None = None,
        min_overload_ms: float = 0.0,
        max_overload_ms: float = 100.0,
        start_step: int = 0,
        end_step: int | None = None,
        seed: int | None = None,
    ) -> None:
        self.node_ids = node_ids
        self.min_overload_ms = min_overload_ms
        self.max_overload_ms = max_overload_ms
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
        extra_ms = self._rng.uniform(self.min_overload_ms, self.max_overload_ms)
        context.clock.advance(extra_ms)
        context.log_event(
            "overload_injected",
            {"node_id": node_id, "extra_ms": extra_ms},
        )
        return context

    @property
    def description(self) -> str:
        return (
            f"OverloadPerturbation(overload=[{self.min_overload_ms:.1f}, "
            f"{self.max_overload_ms:.1f}]ms)"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "OverloadPerturbation",
            "node_ids": list(self.node_ids) if self.node_ids is not None else None,
            "min_overload_ms": self.min_overload_ms,
            "max_overload_ms": self.max_overload_ms,
            "start_step": self.start_step,
            "end_step": self.end_step,
            "seed": self._seed,
        }
