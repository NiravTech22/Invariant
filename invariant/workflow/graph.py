from typing import Any

import networkx as nx

from .node import Node


class WorkflowGraph:
    """NetworkX-based workflow graph with DAG enforcement and invariant exposure."""

    def __init__(self):
        self.graph = nx.DiGraph()
        self.nodes_map: dict[str, Node] = {}

    def add_node(self, node: Node):
        self.nodes_map[node.id] = node
        self.graph.add_node(node.id, node=node)

    def add_edge(self, source_id: str, target_id: str, source_port: str, target_port: str):
        """Adds an edge between two nodes and checks for cycles."""
        if source_id not in self.nodes_map or target_id not in self.nodes_map:
            raise ValueError(f"One or both nodes {source_id}, {target_id} not found")

        self.graph.add_edge(source_id, target_id, source_port=source_port, target_port=target_port)

        if not nx.is_directed_acyclic_graph(self.graph):
            self.graph.remove_edge(source_id, target_id)
            raise ValueError(f"Adding edge {source_id} -> {target_id} would create a cycle")

    def get_node(self, node_id: str) -> Node:
        return self.nodes_map[node_id]

    @property
    def node_ids(self) -> list[str]:
        return list(self.nodes_map.keys())

    def get_topological_order(self) -> list[str]:
        return list(nx.topological_sort(self.graph))

    def get_invariants(self) -> dict[str, Any]:
        """Exposes graph-level invariants for analysis and ML features."""
        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "depth": self._calculate_depth(),
            "fan_in_max": max([d for _, d in self.graph.in_degree()] or [0]),
            "fan_out_max": max([d for _, d in self.graph.out_degree()] or [0]),
            "is_dag": nx.is_directed_acyclic_graph(self.graph),
        }

    def _calculate_depth(self) -> int:
        if not self.graph.nodes:
            return 0
        try:
            return nx.dag_longest_path_length(self.graph)
        except nx.NetworkXError:
            return 0

    def get_critical_path(self) -> list[str]:
        """Returns the longest path in the DAG."""
        return nx.dag_longest_path(self.graph)
