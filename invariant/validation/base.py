from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph


@dataclass
class ValidationResult:
    pass_status: bool
    validator_id: str
    message: str
    metrics: dict[str, Any] = None

class BaseValidator(ABC):
    @abstractmethod
    def validate(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace]) -> ValidationResult:
        pass
