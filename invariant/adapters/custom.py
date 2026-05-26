"""Custom adapter template: starting point for user-defined adapters.

Copy this file and implement the two abstract methods to connect Invariant
to a new robotics stack or simulation environment.
"""

from __future__ import annotations

from invariant.adapters.base import AbstractAdapter
from invariant.core.graph import WorkflowGraph
from invariant.core.workflow import Workflow, WorkflowMetadata


class CustomAdapter(AbstractAdapter):
    """Template for building a custom Invariant adapter.

    Override :meth:`build_workflow` to construct a Workflow that mirrors
    your robotics stack's node/topic topology.

    Args:
        system_name: Human-readable name for the target system.

    Example::

        class MyRobotAdapter(CustomAdapter):
            def build_workflow(self) -> Workflow:
                graph = WorkflowGraph()
                graph.add_node(Node(
                    node_id="my_perception",
                    node_type=NodeType.PERCEPTION,
                    latency_bounds=LatencyBounds(min_ms=1.0, max_ms=30.0),
                ))
                # ... add more nodes and edges ...
                return Workflow(graph=graph, metadata=WorkflowMetadata(name="my_robot"))
    """

    def __init__(self, system_name: str = "custom_system") -> None:
        self._system_name = system_name

    @property
    def name(self) -> str:
        return f"CustomAdapter({self._system_name})"

    def build_workflow(self) -> Workflow:
        """Construct a Workflow for the target system.

        Replace this implementation with your own graph construction logic.

        Returns:
            A Workflow representing the target system topology.
        """
        graph = WorkflowGraph()

        # === Add nodes ===
        # graph.add_node(Node(
        #     node_id="my_node",
        #     node_type=NodeType.PERCEPTION,
        #     latency_bounds=LatencyBounds(min_ms=1.0, max_ms=30.0),
        #     exec_fn=lambda inputs: {"output": 1.0},
        # ))

        # === Add edges ===
        # graph.add_edge(Edge(
        #     source_id="node_a",
        #     target_id="node_b",
        #     data_type="sensor_data",
        # ))

        metadata = WorkflowMetadata(
            name=self._system_name,
            description="Custom adapter workflow",
            target_system=self._system_name,
        )
        return Workflow(graph=graph, metadata=metadata)
