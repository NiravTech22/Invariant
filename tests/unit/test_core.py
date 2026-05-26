"""Unit tests for invariant.core: node, edge, graph, workflow."""

import pytest

from invariant.core.edge import Edge, LatencyModel, ReliabilityModel
from invariant.core.graph import WorkflowGraph
from invariant.core.node import HealthState, LatencyBounds, Node, NodeType
from invariant.core.workflow import Workflow, WorkflowMetadata


# ------------------------------------------------------------------
# Node tests
# ------------------------------------------------------------------


class TestNode:
    def test_basic_construction(self):
        node = Node(node_id="perception", node_type=NodeType.PERCEPTION)
        assert node.node_id == "perception"
        assert node.node_type == NodeType.PERCEPTION

    def test_empty_id_raises(self):
        with pytest.raises(Exception):
            Node(node_id="")

    def test_latency_bounds_validation(self):
        with pytest.raises(Exception):
            LatencyBounds(min_ms=50.0, max_ms=10.0)

    def test_execute_passthrough_without_fn(self):
        node = Node(node_id="n1")
        inputs = {"x": 1, "y": 2}
        outputs = node.execute(inputs)
        assert outputs == inputs

    def test_execute_with_fn(self):
        node = Node(node_id="n1", exec_fn=lambda inputs: {"result": 42})
        outputs = node.execute({})
        assert outputs == {"result": 42}

    def test_health_state_enum(self):
        assert HealthState.HEALTHY.value == "healthy"
        assert HealthState.DEGRADED.value == "degraded"
        assert HealthState.FAILED.value == "failed"


# ------------------------------------------------------------------
# Edge tests
# ------------------------------------------------------------------


class TestEdge:
    def test_basic_construction(self):
        edge = Edge(source_id="a", target_id="b")
        assert edge.source_id == "a"
        assert edge.target_id == "b"
        assert edge.edge_id == "a->b"

    def test_self_loop_raises(self):
        with pytest.raises(Exception):
            Edge(source_id="a", target_id="a")

    def test_latency_model_defaults(self):
        edge = Edge(source_id="a", target_id="b")
        assert edge.latency_model.nominal_ms == 0.0
        assert edge.latency_model.jitter_ms == 0.0

    def test_reliability_model(self):
        edge = Edge(
            source_id="a",
            target_id="b",
            reliability_model=ReliabilityModel(drop_probability=0.1),
        )
        assert edge.reliability_model.drop_probability == 0.1


# ------------------------------------------------------------------
# WorkflowGraph tests
# ------------------------------------------------------------------


def _make_simple_graph():
    graph = WorkflowGraph()
    for nid in ["a", "b", "c"]:
        graph.add_node(Node(node_id=nid))
    graph.add_edge(Edge(source_id="a", target_id="b"))
    graph.add_edge(Edge(source_id="b", target_id="c"))
    return graph


class TestWorkflowGraph:
    def test_add_node(self):
        graph = WorkflowGraph()
        graph.add_node(Node(node_id="x"))
        assert "x" in graph.node_ids

    def test_duplicate_node_raises(self):
        graph = WorkflowGraph()
        graph.add_node(Node(node_id="x"))
        with pytest.raises(ValueError, match="already exists"):
            graph.add_node(Node(node_id="x"))

    def test_add_edge(self):
        graph = _make_simple_graph()
        assert len(graph.edges) == 2

    def test_unknown_source_raises(self):
        graph = WorkflowGraph()
        graph.add_node(Node(node_id="b"))
        with pytest.raises(ValueError, match="Source node"):
            graph.add_edge(Edge(source_id="unknown", target_id="b"))

    def test_unknown_target_raises(self):
        graph = WorkflowGraph()
        graph.add_node(Node(node_id="a"))
        with pytest.raises(ValueError, match="Target node"):
            graph.add_edge(Edge(source_id="a", target_id="unknown"))

    def test_cycle_detection(self):
        graph = WorkflowGraph()
        for nid in ["a", "b", "c"]:
            graph.add_node(Node(node_id=nid))
        graph.add_edge(Edge(source_id="a", target_id="b"))
        graph.add_edge(Edge(source_id="b", target_id="c"))
        with pytest.raises(ValueError, match="cycle"):
            graph.add_edge(Edge(source_id="c", target_id="a"))

    def test_topological_order(self):
        graph = _make_simple_graph()
        order = graph.get_topological_order()
        assert order.index("a") < order.index("b")
        assert order.index("b") < order.index("c")

    def test_get_node_not_found_raises_keyerror(self):
        graph = WorkflowGraph()
        with pytest.raises(KeyError):
            graph.get_node("nonexistent")

    def test_summary(self):
        graph = _make_simple_graph()
        s = graph.summary()
        assert s["num_nodes"] == 3
        assert s["num_edges"] == 2
        assert s["is_dag"] is True

    def test_depth(self):
        graph = _make_simple_graph()
        assert graph.depth() == 2

    def test_len(self):
        graph = _make_simple_graph()
        assert len(graph) == 3


# ------------------------------------------------------------------
# Workflow tests
# ------------------------------------------------------------------


class TestWorkflow:
    def test_from_yaml(self, tmp_path):
        yaml_content = """
metadata:
  name: test_workflow
nodes:
  - id: a
    type: perception
    latency_bounds:
      min_ms: 1.0
      max_ms: 10.0
  - id: b
    type: planning
    latency_bounds:
      min_ms: 1.0
      max_ms: 10.0
edges:
  - source: a
    target: b
    data_type: sensor_data
"""
        p = tmp_path / "wf.yaml"
        p.write_text(yaml_content)
        workflow = Workflow.from_yaml(p)
        assert workflow.metadata.name == "test_workflow"
        assert len(workflow.graph.nodes) == 2
        assert len(workflow.graph.edges) == 1

    def test_validate_empty_raises(self):
        graph = WorkflowGraph()
        workflow = Workflow(graph=graph, metadata=WorkflowMetadata(name="empty"))
        with pytest.raises(ValueError, match="no nodes"):
            workflow.validate()

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            Workflow.from_yaml("/nonexistent/path.yaml")

    def test_roundtrip_json(self, tmp_path):
        graph = WorkflowGraph()
        graph.add_node(Node(node_id="a", node_type=NodeType.PERCEPTION))
        graph.add_node(Node(node_id="b", node_type=NodeType.PLANNING))
        graph.add_edge(Edge(source_id="a", target_id="b"))
        workflow = Workflow(graph=graph, metadata=WorkflowMetadata(name="roundtrip"))
        json_path = tmp_path / "wf.json"
        workflow.to_json(json_path)
        loaded = Workflow.from_json(json_path)
        assert loaded.metadata.name == "roundtrip"
        assert len(loaded.graph.nodes) == 2
        assert len(loaded.graph.edges) == 1

    def test_cycle_in_yaml_raises(self, tmp_path):
        yaml_content = """
metadata:
  name: cyclic
nodes:
  - id: a
    type: perception
  - id: b
    type: planning
edges:
  - source: a
    target: b
  - source: b
    target: a
"""
        p = tmp_path / "cyclic.yaml"
        p.write_text(yaml_content)
        with pytest.raises(ValueError, match="cycle"):
            Workflow.from_yaml(p)
