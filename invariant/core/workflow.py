"""Workflow: container that holds a WorkflowGraph with metadata and serialization."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from invariant.core.edge import Edge, LatencyModel, ReliabilityModel
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node, NodeType


class WorkflowMetadata(BaseModel):
    """Descriptive metadata attached to a workflow definition."""

    name: str = Field(..., min_length=1, description="Workflow name")
    version: str = Field(default="0.1.0")
    description: str = Field(default="")
    author: str = Field(default="")
    target_system: str = Field(default="", description="Robot or stack this workflow models")


class Workflow:
    """Container for a WorkflowGraph plus metadata.

    The Workflow class is the primary user-facing object. It wraps a
    WorkflowGraph, holds versioned metadata, and provides YAML/JSON
    serialization so experiments are fully reproducible from config files.

    Typical usage::

        workflow = Workflow.from_yaml("examples/simple_pipeline.yaml")
        workflow.validate()
        print(workflow.summary())

    Raises:
        ValueError: On structural validation failures (cycles, empty graph,
            unknown edge endpoints).
    """

    def __init__(self, graph: WorkflowGraph, metadata: WorkflowMetadata) -> None:
        self.graph = graph
        self.metadata = metadata

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(self) -> None:
        """Assert structural correctness of the workflow.

        Raises:
            ValueError: If the graph is empty or contains unexpected structural
                problems. (Cycle detection happens eagerly in WorkflowGraph.add_edge.)
        """
        if len(self.graph) == 0:
            raise ValueError(f"Workflow '{self.metadata.name}' has no nodes")
        summary = self.graph.summary()
        if not summary["is_dag"]:
            raise ValueError(f"Workflow '{self.metadata.name}' contains a cycle — invalid DAG")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def summary(self) -> str:
        """Return a human-readable text summary."""
        s = self.graph.summary()
        lines = [
            f"Workflow: {self.metadata.name} v{self.metadata.version}",
            f"  Description : {self.metadata.description or '(none)'}",
            f"  Target      : {self.metadata.target_system or '(unspecified)'}",
            f"  Nodes       : {s['num_nodes']}",
            f"  Edges       : {s['num_edges']}",
            f"  Depth       : {s['depth']}",
            f"  Critical path: {' -> '.join(s['critical_path']) or '(empty)'}",
        ]
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (suitable for JSON/YAML)."""
        nodes_data: list[dict[str, Any]] = []
        for node in self.graph.nodes:
            nodes_data.append(
                {
                    "id": node.node_id,
                    "type": node.node_type.value,
                    "latency_bounds": {
                        "min_ms": node.latency_bounds.min_ms,
                        "max_ms": node.latency_bounds.max_ms,
                    },
                    "metadata": node.metadata,
                }
            )

        edges_data: list[dict[str, Any]] = []
        for edge in self.graph.edges:
            edges_data.append(
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "data_type": edge.data_type,
                    "latency": {
                        "nominal_ms": edge.latency_model.nominal_ms,
                        "jitter_ms": edge.latency_model.jitter_ms,
                    },
                    "reliability": {
                        "drop_probability": edge.reliability_model.drop_probability,
                    },
                    "metadata": edge.metadata,
                }
            )

        return {
            "metadata": self.metadata.model_dump(),
            "nodes": nodes_data,
            "edges": edges_data,
        }

    def to_yaml(self, path: str | Path) -> None:
        """Write workflow to a YAML file.

        Args:
            path: Destination file path.
        """
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(self.to_dict(), fh, default_flow_style=False, sort_keys=False)

    def to_json(self, path: str | Path) -> None:
        """Write workflow to a JSON file.

        Args:
            path: Destination file path.
        """
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, indent=2)

    # ------------------------------------------------------------------
    # Deserialization
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Workflow:
        """Construct a Workflow from a plain dict.

        Args:
            data: Dict with keys ``metadata``, ``nodes``, ``edges``.

        Raises:
            ValueError: If required fields are missing or structurally invalid.
        """
        meta_data = data.get("metadata", {})
        if "name" not in meta_data:
            meta_data["name"] = data.get("name", "unnamed")
        metadata = WorkflowMetadata(**meta_data)

        graph = WorkflowGraph()

        for nd in data.get("nodes", []):
            lb_raw = nd.get("latency_bounds", {})
            lb = LatencyBounds(
                min_ms=lb_raw.get("min_ms", nd.get("min_latency_ms", 0.0)),
                max_ms=lb_raw.get(
                    "max_ms",
                    nd.get("max_latency_ms", nd.get("constraints", {}).get("max_latency_ms", 10.0)),
                ),
            )
            node = Node(
                node_id=nd["id"],
                node_type=NodeType(nd.get("type", "unknown")),
                latency_bounds=lb,
                metadata=nd.get("metadata", {}),
            )
            graph.add_node(node)

        for ed in data.get("edges", []):
            lat_raw = ed.get("latency", {})
            rel_raw = ed.get("reliability", {})
            edge = Edge(
                source_id=ed["source"],
                target_id=ed["target"],
                data_type=ed.get("data_type", ed.get("type", "any")),
                latency_model=LatencyModel(
                    nominal_ms=lat_raw.get("nominal_ms", 0.0),
                    jitter_ms=lat_raw.get("jitter_ms", 0.0),
                ),
                reliability_model=ReliabilityModel(
                    drop_probability=rel_raw.get("drop_probability", 0.0),
                ),
                metadata=ed.get("metadata", {}),
            )
            graph.add_edge(edge)

        return cls(graph=graph, metadata=metadata)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Workflow:
        """Load a Workflow from a YAML file.

        Args:
            path: Path to the YAML workflow definition.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the YAML is malformed or structurally invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Workflow file must be a YAML mapping, got {type(data).__name__}")
        return cls.from_dict(data)

    @classmethod
    def from_json(cls, path: str | Path) -> Workflow:
        """Load a Workflow from a JSON file.

        Args:
            path: Path to the JSON workflow definition.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow file not found: {path}")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return cls.from_dict(data)

    def __repr__(self) -> str:
        return (
            f"Workflow(name={self.metadata.name!r}, "
            f"nodes={len(self.graph.nodes)}, "
            f"edges={len(self.graph.edges)})"
        )
