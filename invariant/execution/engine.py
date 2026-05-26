from ..core.config import ExperimentConfig
from ..workflow.graph import WorkflowGraph
from .perturbation import PerturbationModel, SeededPerturbator
from .scheduler import TopologicalScheduler
from .signals import ExecutionSignal, WorkflowExecutionTrace


class DeterministicEngine:
    """Executes a workflow graph deterministically with seeded perturbations."""

    def __init__(self, graph: WorkflowGraph, config: ExperimentConfig):
        self.graph = graph
        self.config = config
        self.scheduler = TopologicalScheduler(graph)
        self.perturbator: SeededPerturbator | None = None
        self.virtual_time = 0.0

    def set_perturbation(self, model: PerturbationModel):
        self.perturbator = SeededPerturbator(model)

    def run(self) -> WorkflowExecutionTrace:
        """Runs the workflow once and captures signals."""
        self.virtual_time = self.config.timestamp  # Start at experiment timestamp

        trace = WorkflowExecutionTrace(run_id=self.config.run_id, timestamp=self.virtual_time)

        plan = self.scheduler.get_execution_plan()

        for node_id in plan:
            node = self.graph.get_node(node_id)

            # Start signal (virtual time)
            start_t = self.virtual_time

            # Apply perturbation latency (in virtual time)
            if self.perturbator:
                injection = self.perturbator.get_latency_injection()
                self.virtual_time += injection

            # Simulate "execution" (passive for v1)
            # Baseline 1ms execution (in virtual time)
            self.virtual_time += 0.001

            end_t = self.virtual_time

            signal = ExecutionSignal(
                node_id=node_id,
                start_time=start_t,
                end_time=end_t,
                metadata={"type": node.node_type},
            )
            trace.add_signal(signal)

        return trace
