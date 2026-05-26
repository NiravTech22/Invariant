"""CascadePerturbation: apply multiple perturbations simultaneously or in sequence."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING, Any

from invariant.perturbation.base import BasePerturbation

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class CascadeMode(str, Enum):
    """How constituent perturbations are applied."""

    PARALLEL = "parallel"
    SEQUENTIAL = "sequential"


class CascadePerturbation(BasePerturbation):
    """Compose multiple perturbations into one compound fault scenario.

    In **PARALLEL** mode all constituent perturbations whose ``applies_to``
    returns True are applied in list order within the same timestep.

    In **SEQUENTIAL** mode perturbations are applied round-robin across
    timesteps: perturbation 0 on step 0 (modulo n), perturbation 1 on step 1,
    etc. This models faults that trigger each other in a chain over time.

    Args:
        perturbations: Ordered list of BasePerturbation instances.
        mode: PARALLEL or SEQUENTIAL application strategy.

    Example::

        cascade = CascadePerturbation(
            perturbations=[
                LatencyPerturbation(node_ids={"perception"}, mode=LatencyMode.FIXED, delay_ms=30),
                DropoutPerturbation(node_ids={"planner"}, mode=DropoutMode.SUSTAINED, duration=3),
            ],
            mode=CascadeMode.PARALLEL,
        )
    """

    def __init__(
        self,
        perturbations: list[BasePerturbation],
        mode: CascadeMode = CascadeMode.PARALLEL,
    ) -> None:
        if not perturbations:
            raise ValueError("CascadePerturbation requires at least one constituent perturbation")
        self._perturbations = perturbations
        self.mode = mode

    def applies_to(self, node_id: str, timestep: int) -> bool:
        return any(p.applies_to(node_id, timestep) for p in self._perturbations)

    def apply(self, context: "ExecutionContext", node_id: str) -> "ExecutionContext":
        if self.mode == CascadeMode.PARALLEL:
            for pert in self._perturbations:
                if pert.applies_to(node_id, context.timestep):
                    context = pert.apply(context, node_id)
        else:
            # Sequential: apply one perturbation per timestep, round-robin
            idx = context.timestep % len(self._perturbations)
            pert = self._perturbations[idx]
            if pert.applies_to(node_id, context.timestep):
                context = pert.apply(context, node_id)

        context.log_event(
            "cascade_applied",
            {
                "node_id": node_id,
                "mode": self.mode.value,
                "count": len(self._perturbations),
            },
        )
        return context

    @property
    def perturbations(self) -> list[BasePerturbation]:
        return list(self._perturbations)

    @property
    def description(self) -> str:
        parts = ", ".join(p.description for p in self._perturbations)
        return f"CascadePerturbation({self.mode.value}: [{parts}])"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "CascadePerturbation",
            "mode": self.mode.value,
            "perturbations": [p.to_dict() for p in self._perturbations],
        }
