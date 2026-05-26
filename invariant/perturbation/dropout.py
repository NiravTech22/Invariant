"""DropoutPerturbation: cause a node to receive no input for one or more timesteps."""

from __future__ import annotations

import random
from enum import Enum
from typing import TYPE_CHECKING, Any

from invariant.perturbation.base import BasePerturbation

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext

_DROP_SENTINEL = "__dropped__"


class DropoutMode(str, Enum):
    """Strategy for determining when dropouts occur."""

    SINGLE = "single"
    SUSTAINED = "sustained"
    PROBABILISTIC = "probabilistic"


class DropoutPerturbation(BasePerturbation):
    """Cause a node to receive no input, simulating message loss.

    The executor checks for the ``__dropped__`` sentinel in node outputs
    to determine that inputs were dropped for a given node.

    Three modes are supported:

    - **SINGLE**: Drop inputs exactly once at ``drop_step``.
    - **SUSTAINED**: Drop inputs for ``duration`` consecutive steps starting
      at ``start_step``.
    - **PROBABILISTIC**: Drop inputs with probability ``drop_probability``
      on each step.

    Args:
        node_ids: Set of node IDs to target. ``None`` targets all nodes.
        mode: Dropout strategy.
        drop_step: Step at which to drop (SINGLE mode).
        start_step: First step of sustained dropout.
        duration: Number of consecutive steps to drop (SUSTAINED mode).
        drop_probability: Probability of dropping on any given step.
        seed: RNG seed for PROBABILISTIC mode.

    Raises:
        ValueError: If drop_probability is outside [0, 1].
    """

    def __init__(
        self,
        node_ids: set[str] | None = None,
        mode: DropoutMode | str = DropoutMode.SINGLE,
        drop_step: int = 0,
        start_step: int = 0,
        duration: int = 1,
        drop_probability: float = 0.5,
        seed: int | None = None,
    ) -> None:
        if not 0.0 <= drop_probability <= 1.0:
            raise ValueError(f"drop_probability must be in [0, 1], got {drop_probability}")
        self.node_ids = node_ids
        self.mode = DropoutMode(mode) if isinstance(mode, str) else mode
        self.drop_step = drop_step
        self.start_step = start_step
        self.duration = duration
        self.drop_probability = drop_probability
        self._rng = random.Random(seed)
        self._seed = seed

    def applies_to(self, node_id: str, timestep: int) -> bool:
        if self.node_ids is not None and node_id not in self.node_ids:
            return False
        return True

    def apply(self, context: "ExecutionContext", node_id: str) -> "ExecutionContext":
        timestep = context.timestep
        should_drop = False

        if self.mode == DropoutMode.SINGLE:
            should_drop = timestep == self.drop_step
        elif self.mode == DropoutMode.SUSTAINED:
            should_drop = self.start_step <= timestep < self.start_step + self.duration
        elif self.mode == DropoutMode.PROBABILISTIC:
            should_drop = self._rng.random() < self.drop_probability

        if should_drop:
            # Signal to executor that this node's inputs are dropped
            context.set_output(node_id + _DROP_SENTINEL, {"dropped": True})
            context.log_event(
                "input_dropped",
                {"node_id": node_id, "mode": self.mode.value, "timestep": timestep},
            )

        return context

    @property
    def description(self) -> str:
        if self.mode == DropoutMode.SINGLE:
            return f"DropoutPerturbation(single at step={self.drop_step})"
        if self.mode == DropoutMode.SUSTAINED:
            return f"DropoutPerturbation(sustained start={self.start_step} for {self.duration} steps)"
        return f"DropoutPerturbation(probabilistic p={self.drop_probability:.2f})"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "DropoutPerturbation",
            "node_ids": list(self.node_ids) if self.node_ids is not None else None,
            "mode": self.mode.value,
            "drop_step": self.drop_step,
            "start_step": self.start_step,
            "duration": self.duration,
            "drop_probability": self.drop_probability,
            "seed": self._seed,
        }
