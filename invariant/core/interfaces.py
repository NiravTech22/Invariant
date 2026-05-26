from abc import ABC, abstractmethod

from .outcome import Violation
from .types import ProposedAction, SystemState


class SafetyValidator(ABC):
    """
    Interface for any safety check module (Constraint or Policy).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the validator for logging."""
        pass

    @abstractmethod
    def check(self, state: SystemState, action: ProposedAction) -> Violation | None:
        """
        Returns None if safe, or a Violation object if unsafe.
        Does NOT modify the action.
        """
        pass

class ComponentInterface(ABC):
    """
    Base for larger subsystems found in robotic stacks if needed.
    """
    pass
