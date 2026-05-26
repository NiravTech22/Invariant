"""Integration test: verify cyclic workflows are rejected."""

import pytest

from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import Node
from invariant.core.workflow import Workflow, WorkflowMetadata


class TestCyclicWorkflowRejected:
    def test_cycle_via_add_edge_raises(self):
        graph = WorkflowGraph()
        for nid in ["a", "b", "c"]:
            graph.add_node(Node(node_id=nid))
        graph.add_edge(Edge(source_id="a", target_id="b"))
        graph.add_edge(Edge(source_id="b", target_id="c"))
        with pytest.raises(ValueError, match="cycle"):
            graph.add_edge(Edge(source_id="c", target_id="a"))

    def test_cycle_via_yaml_raises(self, tmp_path):
        yaml_content = """
metadata:
  name: cyclic
nodes:
  - id: x
    type: perception
  - id: y
    type: planning
edges:
  - source: x
    target: y
  - source: y
    target: x
"""
        p = tmp_path / "cyclic.yaml"
        p.write_text(yaml_content)
        with pytest.raises(ValueError, match="cycle"):
            Workflow.from_yaml(p)

    def test_self_loop_raises(self):
        with pytest.raises(Exception):
            Edge(source_id="a", target_id="a")

    def test_valid_dag_passes(self):
        graph = WorkflowGraph()
        for nid in ["a", "b", "c"]:
            graph.add_node(Node(node_id=nid))
        graph.add_edge(Edge(source_id="a", target_id="b"))
        graph.add_edge(Edge(source_id="a", target_id="c"))
        graph.add_edge(Edge(source_id="b", target_id="c"))
        assert graph.summary()["is_dag"] is True
