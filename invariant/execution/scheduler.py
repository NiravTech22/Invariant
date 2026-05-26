"""TopologicalScheduler: determines node execution order from a WorkflowGraph."""

from __future__ import annotations

from invariant.core.graph import WorkflowGraph


class TopologicalScheduler:
    """Produces a deterministic node execution plan respecting data dependencies.

    The execution plan is a list of node IDs in topological order — every
    node appears after all of its predecessors. The plan is computed once at
    construction and cached.

    Args:
        graph: The WorkflowGraph to schedule.

    Raises:
        RuntimeError: If the graph contains a cycle (should not be possible
            if WorkflowGraph.add_edge was used correctly).
    """

    def __init__(self, graph: WorkflowGraph) -> None:
        self._plan: list[str] = graph.get_topological_order()

    def get_execution_plan(self) -> list[str]:
        """Return the ordered list of node IDs for one execution pass.

        Returns:
            List of node IDs in a valid topological order.
        """
        return list(self._plan)
