
from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph
from .base import BaseValidator, ValidationResult


class StructuralValidator(BaseValidator):
    """Validates graph topology and basic invariants."""

    def validate(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace]) -> ValidationResult:
        invariants = graph.get_invariants()

        errors = []
        if not invariants["is_dag"]:
            errors.append("Graph is not a DAG")

        if invariants["num_nodes"] == 0:
            errors.append("Graph has no nodes")

        pass_status = len(errors) == 0
        message = "Structural validation passed" if pass_status else f"Structural errors: {', '.join(errors)}"

        return ValidationResult(
            pass_status=pass_status,
            validator_id="structural",
            message=message,
            metrics=invariants
        )
