"""BasePerturbation: abstract interface that all perturbations must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invariant.execution.context import ExecutionContext


class BasePerturbation(ABC):
    """Abstract base class for all perturbation types.

    Every perturbation must implement three things:

    1. :meth:`applies_to` — gates whether this perturbation is active for a
       given node at a given timestep.
    2. :meth:`apply` — modifies the :class:`~invariant.execution.context.ExecutionContext`
       to inject the perturbation effect.
    3. :attr:`description` — a human-readable string used in reports.

    Perturbations must be fully serializable (``to_dict`` / ``from_dict``) so
    that experiment configurations can be archived and reproduced exactly.
    """

    @abstractmethod
    def applies_to(self, node_id: str, timestep: int) -> bool:
        """Return True if this perturbation is active for node_id at timestep.

        Args:
            node_id: The node about to be executed.
            timestep: The current simulation step.

        Returns:
            True if this perturbation should be applied, False to skip.
        """

    @abstractmethod
    def apply(self, context: ExecutionContext, node_id: str) -> ExecutionContext:
        """Inject the perturbation effect into the execution context.

        Implementations may:
        - Advance ``context.clock`` to inject latency.
        - Set a ``__dropped__`` sentinel on context outputs to signal dropout.
        - Modify node outputs already stored in the context (noise).

        The context is mutated in-place; returning it makes the call chainable.

        Args:
            context: The live execution context for this run.
            node_id: The node currently being processed.

        Returns:
            The (mutated) context.
        """

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable one-line description used in reports and logs."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialize perturbation parameters to a plain dict.

        The dict must contain a ``type`` key matching the perturbation's
        class name so it can be reconstructed by a registry.
        """

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.description})"
