"""WorkflowGraph: directed acyclic graph of nodes and edges."""

from __future__ import annotations

from typing import Any, cast

import networkx as nx

from invariant.core.edge import Edge
from invariant.core.node import Node


class WorkflowGraph:
    """A directed acyclic graph (DAG) representing a robotics software workflow.

    Maintains a networkx DiGraph for structural queries while storing rich
    Node and Edge objects separately. Every add_edge call verifies that the
    graph remains acyclic; callers receive an explicit ValueError if a cycle
    would be introduced.

    Raises:
        ValueError: On duplicate node IDs, unknown edge endpoints, or cycle introduction.
    """

    def __init__(self) -> None:
        self._graph: nx.DiGraph = nx.DiGraph()
        self._nodes: dict[str, Node] = {}
        self._edges: dict[str, Edge] = {}

    # ------------------------------------------------------------------
    # Mutation
    # ------------------------------------------------------------------

    def add_node(self, node: Node) -> None:
        """Add a node to the graph.

        Args:
            node: Node instance to add.

        Raises:
            ValueError: If a node with the same ID already exists.
        """
        if node.node_id in self._nodes:
            raise ValueError(f"Node '{node.node_id}' already exists in the graph")
        self._nodes[node.node_id] = node
        self._graph.add_node(node.node_id)

    def add_edge(self, edge: Edge) -> None:
        """Add an edge to the graph, enforcing DAG invariant.

        Args:
            edge: Edge instance to add.

        Raises:
            ValueError: If endpoints are unknown, edge already exists, or a
                cycle would be created.
        """
        if edge.source_id not in self._nodes:
            raise ValueError(f"Source node '{edge.source_id}' not found in graph")
        if edge.target_id not in self._nodes:
            raise ValueError(f"Target node '{edge.target_id}' not found in graph")
        if self._graph.has_edge(edge.source_id, edge.target_id):
            raise ValueError(f"Edge '{edge.source_id}' -> '{edge.target_id}' already exists")

        self._graph.add_edge(edge.source_id, edge.target_id)

        if not nx.is_directed_acyclic_graph(self._graph):
            self._graph.remove_edge(edge.source_id, edge.target_id)
            raise ValueError(
                f"Adding edge '{edge.source_id}' -> '{edge.target_id}' introduces a cycle"
            )

        self._edges[edge.edge_id] = edge

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_node(self, node_id: str) -> Node:
        """Retrieve a node by ID.

        Args:
            node_id: The node's unique identifier.

        Raises:
            KeyError: If the node does not exist.
        """
        try:
            return self._nodes[node_id]
        except KeyError:
            raise KeyError(
                f"Node '{node_id}' not found. Available: {list(self._nodes.keys())}"
            ) from None

    def get_edge(self, source_id: str, target_id: str) -> Edge:
        """Retrieve an edge by its endpoints.

        Raises:
            KeyError: If the edge does not exist.
        """
        key = f"{source_id}->{target_id}"
        try:
            return self._edges[key]
        except KeyError:
            raise KeyError(f"Edge '{source_id}' -> '{target_id}' not found") from None

    @property
    def node_ids(self) -> list[str]:
        """All node IDs in insertion order."""
        return list(self._nodes.keys())

    @property
    def nodes(self) -> list[Node]:
        """All Node objects."""
        return list(self._nodes.values())

    @property
    def edges(self) -> list[Edge]:
        """All Edge objects."""
        return list(self._edges.values())

    def get_topological_order(self) -> list[str]:
        """Return node IDs in a valid topological order.

        Returns:
            List of node IDs where each node appears before all its successors.

        Raises:
            RuntimeError: If the graph contains a cycle (should not happen if
                add_edge is always used).
        """
        try:
            return list(nx.topological_sort(self._graph))
        except nx.NetworkXUnfeasible as exc:
            raise RuntimeError("Graph contains a cycle — cannot compute topological order") from exc

    def successors(self, node_id: str) -> list[str]:
        """Return direct successors of a node."""
        return list(self._graph.successors(node_id))

    def predecessors(self, node_id: str) -> list[str]:
        """Return direct predecessors of a node."""
        return list(self._graph.predecessors(node_id))

    def edges_from(self, node_id: str) -> list[Edge]:
        """Return all edges whose source is node_id."""
        return [
            self._edges[f"{node_id}->{succ}"]
            for succ in self._graph.successors(node_id)
            if f"{node_id}->{succ}" in self._edges
        ]

    def edges_to(self, node_id: str) -> list[Edge]:
        """Return all edges whose target is node_id."""
        return [
            self._edges[f"{pred}->{node_id}"]
            for pred in self._graph.predecessors(node_id)
            if f"{pred}->{node_id}" in self._edges
        ]

    def get_critical_path(self) -> list[str]:
        """Return the node sequence forming the longest path in the DAG."""
        return list(nx.dag_longest_path(self._graph))

    def depth(self) -> int:
        """Return the length of the longest path (number of edges)."""
        if not self._graph.nodes:
            return 0
        try:
            return cast(int, nx.dag_longest_path_length(self._graph))
        except nx.NetworkXError:
            return 0

    def summary(self) -> dict[str, Any]:
        """Return a human-readable summary dict of graph properties."""
        in_degrees = [d for _, d in self._graph.in_degree()]
        out_degrees = [d for _, d in self._graph.out_degree()]
        return {
            "num_nodes": self._graph.number_of_nodes(),
            "num_edges": self._graph.number_of_edges(),
            "depth": self.depth(),
            "max_fan_in": max(in_degrees) if in_degrees else 0,
            "max_fan_out": max(out_degrees) if out_degrees else 0,
            "is_dag": nx.is_directed_acyclic_graph(self._graph),
            "critical_path": self.get_critical_path(),
        }

    def __len__(self) -> int:
        return len(self._nodes)

    def __repr__(self) -> str:
        s = self.summary()
        return f"WorkflowGraph(nodes={s['num_nodes']}, edges={s['num_edges']}, depth={s['depth']})"
