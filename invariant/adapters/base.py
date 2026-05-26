"""AbstractAdapter: interface that all adapters must implement."""

from __future__ import annotations

from abc import ABC, abstractmethod

from invariant.core.workflow import Workflow


class AbstractAdapter(ABC):
    """Base class for all Invariant adapters.

    An adapter bridges a real or simulated robotics stack to Invariant's
    workflow model. It is responsible for:

    1. Building a :class:`~invariant.core.workflow.Workflow` that represents
       the target stack's node/edge topology.
    2. Optionally wrapping node execution so that Invariant can observe
       and perturb real message flows.

    Adapters may have external dependencies (e.g., ROS 2); only adapter
    code should import optional packages. The core execution layer remains
    dependency-free.
    """

    @abstractmethod
    def build_workflow(self) -> Workflow:
        """Construct and return an Invariant Workflow for the target stack.

        Returns:
            A validated Workflow representation of the target system.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short human-readable name for this adapter."""

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name={self.name!r})"
