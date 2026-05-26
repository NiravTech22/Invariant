"""ROS2 adapter: introspect a running ROS 2 graph and wrap it as an Invariant Workflow.

The ROS 2 adapter does NOT control the robot. It observes and instruments
a running ROS 2 system. The robot stack continues to run normally; Invariant
sits alongside it, recording the graph topology and (optionally) intercepting
topic messages to measure timing.

This module gracefully degrades when rclpy is unavailable: all classes
can be imported but will raise ``RuntimeError`` when methods requiring
a live ROS 2 context are called.
"""

from __future__ import annotations

from typing import Any

try:
    import rclpy
    from rclpy.node import Node as RosNode

    _HAS_RCLPY = True
except ImportError:
    rclpy = None  # type: ignore[assignment]
    RosNode = object  # type: ignore[assignment,misc]
    _HAS_RCLPY = False

from invariant.adapters.base import AbstractAdapter
from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node, NodeType
from invariant.core.workflow import Workflow, WorkflowMetadata


def _require_rclpy() -> None:
    if not _HAS_RCLPY:
        raise RuntimeError(
            "rclpy is not installed. Install it with your ROS 2 distribution "
            "and ensure your Python environment can find it."
        )


class ROS2Adapter(AbstractAdapter):
    """Introspect a running ROS 2 graph and generate an Invariant Workflow.

    The adapter creates an rclpy node named ``invariant_introspector`` and
    uses the graph introspection API to discover all nodes, their
    publishers, and their subscribers. Edges are inferred by matching
    topic names: if node A publishes topic T and node B subscribes to T,
    an edge A→B is created.

    Args:
        node_name: Name for the introspection rclpy node.

    Raises:
        RuntimeError: If rclpy is not available.

    Example::

        adapter = ROS2Adapter()
        workflow = adapter.build_workflow()
        workflow.validate()
        print(workflow.summary())
    """

    def __init__(self, node_name: str = "invariant_introspector") -> None:
        _require_rclpy()
        if not rclpy.ok():
            rclpy.init()
        self._node = rclpy.create_node(node_name)
        self._active = True

    @property
    def name(self) -> str:
        return "ROS2Adapter"

    def build_workflow(self) -> Workflow:
        """Introspect the running ROS 2 graph and return a Workflow.

        Returns:
            Workflow representing the live ROS 2 node/topic topology.

        Raises:
            RuntimeError: If the ROS 2 node is not active.
        """
        if not self._active:
            raise RuntimeError("ROS2Adapter has been shut down")

        graph = WorkflowGraph()

        node_names_namespaces: list[tuple[str, str]] = (
            self._node.get_node_names_and_namespaces()
        )

        for name, namespace in node_names_namespaces:
            full_name = f"{namespace}/{name}".replace("//", "/")

            pubs = self._node.get_publisher_names_and_types_by_node(name, namespace)
            subs = self._node.get_subscriber_names_and_types_by_node(name, namespace)

            node = Node(
                node_id=full_name,
                node_type=NodeType.UNKNOWN,
                latency_bounds=LatencyBounds(min_ms=0.0, max_ms=100.0),
                metadata={
                    "ros_name": name,
                    "ros_namespace": namespace,
                    "publishers": [t for t, _ in pubs],
                    "subscribers": [t for t, _ in subs],
                },
            )
            try:
                graph.add_node(node)
            except ValueError:
                pass  # Skip duplicate nodes

        # Infer edges from topic matching
        for source_node in graph.nodes:
            pub_topics: list[str] = source_node.metadata.get("publishers", [])
            for topic in pub_topics:
                for target_node in graph.nodes:
                    if target_node.node_id == source_node.node_id:
                        continue
                    sub_topics: list[str] = target_node.metadata.get("subscribers", [])
                    if topic in sub_topics:
                        try:
                            graph.add_edge(
                                Edge(
                                    source_id=source_node.node_id,
                                    target_id=target_node.node_id,
                                    data_type=topic,
                                )
                            )
                        except ValueError:
                            pass  # Ignore cycles or duplicates from ROS graph

        metadata = WorkflowMetadata(
            name="ros2_introspected",
            description="Introspected from live ROS 2 system",
            target_system="ros2",
        )
        return Workflow(graph=graph, metadata=metadata)

    def spin_once(self, timeout_sec: float = 0.1) -> None:
        """Spin the introspection node once to process pending callbacks.

        Args:
            timeout_sec: Maximum time to spin in seconds.
        """
        if self._active and _HAS_RCLPY:
            rclpy.spin_once(self._node, timeout_sec=timeout_sec)

    def shutdown(self) -> None:
        """Cleanly destroy the ROS 2 node and shut down rclpy."""
        if self._active and _HAS_RCLPY:
            self._node.destroy_node()
            rclpy.shutdown()
            self._active = False
