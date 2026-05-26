from typing import Any

import yaml

from .graph import WorkflowGraph
from .node import Node, NodeConstraints, Port, PortType


class WorkflowLoader:
    """Loads workflow definitions from YAML or JSON."""

    @staticmethod
    def from_yaml(path: str) -> WorkflowGraph:
        with open(path) as f:
            data = yaml.safe_load(f)
        return WorkflowLoader.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WorkflowGraph:
        graph = WorkflowGraph()

        # Add nodes
        for node_data in data.get("nodes", []):
            ports = []
            for p in node_data.get("ports", []):
                ports.append(
                    Port(
                        name=p["name"],
                        port_type=PortType(p["port_type"]),
                        data_type=p["data_type"],
                        metadata=p.get("metadata", {}),
                    )
                )

            constraints = NodeConstraints(**node_data.get("constraints", {}))

            node = Node(
                id=node_data["id"],
                node_type=node_data["type"],
                ports=ports,
                constraints=constraints,
                metadata=node_data.get("metadata", {}),
            )
            graph.add_node(node)

        # Add edges
        for edge_data in data.get("edges", []):
            graph.add_edge(
                source_id=edge_data["source"],
                target_id=edge_data["target"],
                source_port=edge_data["source_port"],
                target_port=edge_data["target_port"],
            )

        return graph
