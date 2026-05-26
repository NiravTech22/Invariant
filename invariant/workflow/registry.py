from typing import Any

from .node import Node


class NodeRegistry:
    """Registry for node types and templates."""

    def __init__(self):
        self._templates: dict[str, dict[str, Any]] = {}

    def register_template(self, type_name: str, template: dict[str, Any]):
        self._templates[type_name] = template

    def create_node(self, node_id: str, type_name: str, overrides: dict[str, Any] = None) -> Node:
        if type_name not in self._templates:
            raise ValueError(f"Unknown node type: {type_name}")

        data = self._templates[type_name].copy()
        if overrides:
            data.update(overrides)

        # In a real implementation, we would convert dict data to Port and NodeConstraints objects
        # For v1, we assume the factory handles the mapping
        from .node import NodeConstraints, Port, PortType

        ports = [Port(**p) for p in data.get("ports", [])]
        for p in ports:
            if isinstance(p.port_type, str):
                p.port_type = PortType(p.port_type)

        constraints = NodeConstraints(**data.get("constraints", {}))

        return Node(
            id=node_id,
            node_type=type_name,
            ports=ports,
            constraints=constraints,
            metadata=data.get("metadata", {}),
        )
