"""MockAdapter: pre-built mock nodes for testing Invariant without a real robot."""

from __future__ import annotations

import random
from collections.abc import Callable
from typing import Any

from invariant.adapters.base import AbstractAdapter
from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node, NodeType
from invariant.core.workflow import Workflow, WorkflowMetadata


def _make_mock_fn(
    node_id: str,
    output_keys: list[str],
    value_range: tuple[float, float] = (0.0, 1.0),
    seed: int | None = None,
) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """Create a simple deterministic mock execution function.

    Args:
        node_id: Node identifier (used as RNG seed component).
        output_keys: Keys to include in the output dict.
        value_range: Range for generated float values.
        seed: Optional seed. If None, uses hash of node_id.
    """
    rng_seed = seed if seed is not None else hash(node_id) % (2**31)
    rng = random.Random(rng_seed)

    def fn(inputs: dict[str, Any]) -> dict[str, Any]:
        return {k: rng.uniform(*value_range) for k in output_keys}

    return fn


class MockPerceptionNode(Node):
    """Pre-built mock perception node.

    Produces a stream of simulated sensor readings (x, y, z coordinates)
    on each execution.

    Args:
        node_id: Unique identifier. Defaults to ``"perception"``.
        latency_bounds: Expected execution time bounds.
        seed: RNG seed for output generation.
    """

    def __init__(
        self,
        node_id: str = "perception",
        latency_bounds: LatencyBounds | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            node_type=NodeType.PERCEPTION,
            latency_bounds=latency_bounds or LatencyBounds(min_ms=1.0, max_ms=33.0),
            exec_fn=_make_mock_fn(node_id, ["x", "y", "z"], seed=seed),
        )


class MockPlannerNode(Node):
    """Pre-built mock planning node.

    Consumes perception output and produces a trajectory waypoints list.

    Args:
        node_id: Unique identifier. Defaults to ``"planner"``.
        latency_bounds: Expected execution time bounds.
        seed: RNG seed for output generation.
    """

    def __init__(
        self,
        node_id: str = "planner",
        latency_bounds: LatencyBounds | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            node_type=NodeType.PLANNING,
            latency_bounds=latency_bounds or LatencyBounds(min_ms=5.0, max_ms=100.0),
            exec_fn=_make_mock_fn(node_id, ["waypoint_x", "waypoint_y", "speed"], seed=seed),
        )


class MockControllerNode(Node):
    """Pre-built mock controller node.

    Consumes planner output and produces velocity commands.

    Args:
        node_id: Unique identifier. Defaults to ``"controller"``.
        latency_bounds: Expected execution time bounds.
        seed: RNG seed for output generation.
    """

    def __init__(
        self,
        node_id: str = "controller",
        latency_bounds: LatencyBounds | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            node_type=NodeType.CONTROL,
            latency_bounds=latency_bounds or LatencyBounds(min_ms=0.5, max_ms=10.0),
            exec_fn=_make_mock_fn(node_id, ["v", "w"], value_range=(-1.0, 1.0), seed=seed),
        )


class MockOrchestratorNode(Node):
    """Pre-built mock orchestrator node.

    Coordinates decisions from multiple inputs.

    Args:
        node_id: Unique identifier. Defaults to ``"orchestrator"``.
        latency_bounds: Expected execution time bounds.
        seed: RNG seed for output generation.
    """

    def __init__(
        self,
        node_id: str = "orchestrator",
        latency_bounds: LatencyBounds | None = None,
        seed: int | None = None,
    ) -> None:
        super().__init__(
            node_id=node_id,
            node_type=NodeType.ORCHESTRATOR,
            latency_bounds=latency_bounds or LatencyBounds(min_ms=1.0, max_ms=20.0),
            exec_fn=_make_mock_fn(node_id, ["decision", "priority"], seed=seed),
        )


class MockAdapter(AbstractAdapter):
    """Adapter that builds a Workflow from mock nodes.

    Supports building complete mock robotics stacks from a simple topology
    specification. Useful for testing Invariant itself and for prototyping
    experiments without a real robot.

    Args:
        workflow_name: Name for the constructed workflow.

    Example::

        adapter = MockAdapter("linear_pipeline")
        perception = MockPerceptionNode()
        planner = MockPlannerNode()
        controller = MockControllerNode()
        workflow = adapter.build_linear_pipeline(perception, planner, controller)
    """

    def __init__(self, workflow_name: str = "mock_workflow") -> None:
        self._workflow_name = workflow_name

    @property
    def name(self) -> str:
        return f"MockAdapter({self._workflow_name})"

    def build_workflow(self) -> Workflow:
        """Build a default linear three-node mock pipeline.

        Returns:
            Workflow with perception → planner → controller topology.
        """
        return self.build_linear_pipeline(
            MockPerceptionNode(),
            MockPlannerNode(),
            MockControllerNode(),
        )

    def build_linear_pipeline(self, *nodes: Node) -> Workflow:
        """Build a linear chain of nodes.

        Args:
            *nodes: Nodes in execution order (first → last).

        Returns:
            Workflow with edges connecting each consecutive pair.

        Raises:
            ValueError: If fewer than 2 nodes are provided.
        """
        if len(nodes) < 2:
            raise ValueError("build_linear_pipeline requires at least 2 nodes")

        graph = WorkflowGraph()
        for node in nodes:
            graph.add_node(node)

        for i in range(len(nodes) - 1):
            graph.add_edge(
                Edge(
                    source_id=nodes[i].node_id,
                    target_id=nodes[i + 1].node_id,
                    data_type="mock_data",
                )
            )

        metadata = WorkflowMetadata(
            name=self._workflow_name,
            description="Mock linear pipeline",
            target_system="mock",
        )
        return Workflow(graph=graph, metadata=metadata)

    def build_branching_pipeline(
        self,
        source: Node,
        branch_a: Node,
        branch_b: Node,
        arbitrator: Node,
        sink: Node,
    ) -> Workflow:
        """Build a branching pipeline with two parallel branches and an arbitrator.

        Topology: source → (branch_a, branch_b) → arbitrator → sink

        Args:
            source: Input node (e.g. perception).
            branch_a: First parallel branch.
            branch_b: Second parallel branch.
            arbitrator: Merges branch outputs.
            sink: Final sink node (e.g. controller).

        Returns:
            Workflow with the branching topology.
        """
        graph = WorkflowGraph()
        for node in [source, branch_a, branch_b, arbitrator, sink]:
            graph.add_node(node)

        graph.add_edge(Edge(source_id=source.node_id, target_id=branch_a.node_id, data_type="mock"))
        graph.add_edge(Edge(source_id=source.node_id, target_id=branch_b.node_id, data_type="mock"))
        graph.add_edge(
            Edge(source_id=branch_a.node_id, target_id=arbitrator.node_id, data_type="mock")
        )
        graph.add_edge(
            Edge(source_id=branch_b.node_id, target_id=arbitrator.node_id, data_type="mock")
        )
        graph.add_edge(Edge(source_id=arbitrator.node_id, target_id=sink.node_id, data_type="mock"))

        metadata = WorkflowMetadata(
            name=self._workflow_name,
            description="Mock branching pipeline",
            target_system="mock",
        )
        return Workflow(graph=graph, metadata=metadata)
