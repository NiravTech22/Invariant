"""Unit tests for invariant.execution: clock, context, scheduler, executor."""

import pytest

from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node, NodeType
from invariant.core.workflow import Workflow, WorkflowMetadata
from invariant.execution.clock import SimulatedClock
from invariant.execution.context import EdgeRecord, ExecutionContext, NodeRecord
from invariant.execution.executor import DeterministicExecutor
from invariant.execution.scheduler import TopologicalScheduler
from invariant.core.node import HealthState


# ------------------------------------------------------------------
# SimulatedClock
# ------------------------------------------------------------------


class TestSimulatedClock:
    def test_initial_time(self):
        clock = SimulatedClock(100.0)
        assert clock.now() == 100.0

    def test_advance(self):
        clock = SimulatedClock(0.0)
        clock.advance(5.0)
        assert clock.now() == 5.0

    def test_multiple_advances(self):
        clock = SimulatedClock(0.0)
        clock.advance(3.0)
        clock.advance(7.0)
        assert clock.now() == 10.0

    def test_negative_advance_raises(self):
        clock = SimulatedClock(0.0)
        with pytest.raises(ValueError, match="negative"):
            clock.advance(-1.0)

    def test_zero_advance_ok(self):
        clock = SimulatedClock(5.0)
        clock.advance(0.0)
        assert clock.now() == 5.0

    def test_record_event(self):
        clock = SimulatedClock(10.0)
        clock.record_event("test_event", {"detail": "ok"})
        events = clock.events
        assert len(events) == 1
        assert events[0]["label"] == "test_event"
        assert events[0]["time_ms"] == 10.0

    def test_reset(self):
        clock = SimulatedClock(100.0)
        clock.advance(50.0)
        clock.record_event("e")
        clock.reset(0.0)
        assert clock.now() == 0.0
        assert len(clock.events) == 0

    def test_no_wall_time(self):
        import time

        clock = SimulatedClock(0.0)
        t_before = time.time()
        clock.advance(1_000_000.0)
        t_after = time.time()
        elapsed_real = t_after - t_before
        assert elapsed_real < 0.1  # virtual advance has no wall-clock cost


# ------------------------------------------------------------------
# ExecutionContext
# ------------------------------------------------------------------


class TestExecutionContext:
    def _make_ctx(self):
        clock = SimulatedClock(0.0)
        return ExecutionContext(run_id="test", timestep=0, clock=clock)

    def test_set_get_output(self):
        ctx = self._make_ctx()
        ctx.set_output("node_a", {"x": 1})
        assert ctx.get_output("node_a") == {"x": 1}

    def test_get_missing_output_returns_empty(self):
        ctx = self._make_ctx()
        assert ctx.get_output("missing") == {}

    def test_gather_inputs(self):
        ctx = self._make_ctx()
        ctx.set_output("a", {"v": 1})
        ctx.set_output("b", {"v": 2})
        inputs = ctx.gather_inputs("c", ["a", "b"])
        assert inputs["a"] == {"v": 1}
        assert inputs["b"] == {"v": 2}

    def test_record_node(self):
        ctx = self._make_ctx()
        record = NodeRecord(
            node_id="n", timestep=0, start_ms=0.0, end_ms=5.0,
            inputs={}, outputs={}, health=HealthState.HEALTHY,
        )
        ctx.record_node(record)
        assert len(ctx.node_records) == 1
        assert ctx.node_records[0].node_id == "n"

    def test_log_event(self):
        ctx = self._make_ctx()
        ctx.log_event("test", {"key": "val"})
        events = ctx.events
        assert len(events) == 1
        assert events[0]["label"] == "test"


# ------------------------------------------------------------------
# TopologicalScheduler
# ------------------------------------------------------------------


class TestTopologicalScheduler:
    def test_linear_order(self):
        graph = WorkflowGraph()
        for nid in ["a", "b", "c"]:
            graph.add_node(Node(node_id=nid))
        graph.add_edge(Edge(source_id="a", target_id="b"))
        graph.add_edge(Edge(source_id="b", target_id="c"))
        scheduler = TopologicalScheduler(graph)
        plan = scheduler.get_execution_plan()
        assert plan.index("a") < plan.index("b")
        assert plan.index("b") < plan.index("c")


# ------------------------------------------------------------------
# DeterministicExecutor
# ------------------------------------------------------------------


def _simple_workflow():
    graph = WorkflowGraph()
    graph.add_node(Node(
        node_id="a",
        node_type=NodeType.PERCEPTION,
        latency_bounds=LatencyBounds(min_ms=1.0, max_ms=5.0),
        exec_fn=lambda inputs: {"val": 1.0},
    ))
    graph.add_node(Node(
        node_id="b",
        node_type=NodeType.PLANNING,
        latency_bounds=LatencyBounds(min_ms=2.0, max_ms=10.0),
        exec_fn=lambda inputs: {"val": 2.0},
    ))
    graph.add_edge(Edge(source_id="a", target_id="b"))
    return Workflow(graph=graph, metadata=WorkflowMetadata(name="test"))


class TestDeterministicExecutor:
    def test_run_produces_trace(self):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        trace = executor.run()
        assert len(trace.node_records) == 2

    def test_determinism_same_seed(self):
        workflow = _simple_workflow()
        from invariant.perturbation.latency import LatencyPerturbation, LatencyMode

        # Create two separate instances with the same seed — determinism requires
        # fresh RNGs producing identical sequences, not shared mutable state.
        p1 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=20.0, seed=42)
        p2 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=20.0, seed=42)
        e1 = DeterministicExecutor(workflow, perturbations=[p1])
        e2 = DeterministicExecutor(workflow, perturbations=[p2])
        t1 = e1.run(run_id="test", timestep=0)
        t2 = e2.run(run_id="test", timestep=0)
        lat1 = t1.get_node_latencies()
        lat2 = t2.get_node_latencies()
        assert lat1.keys() == lat2.keys()
        for k in lat1:
            assert lat1[k] == pytest.approx(lat2[k], rel=1e-9)

    def test_no_perturbation_baseline(self):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        trace = executor.run()
        assert trace.is_nominal()
        assert len(trace.get_dropped_nodes()) == 0

    def test_node_outputs_passed_downstream(self):
        graph = WorkflowGraph()
        graph.add_node(Node(
            node_id="source",
            exec_fn=lambda inputs: {"value": 42},
        ))
        graph.add_node(Node(
            node_id="sink",
            exec_fn=lambda inputs: {"received": inputs.get("source", {}).get("value", 0)},
        ))
        graph.add_edge(Edge(source_id="source", target_id="sink"))
        workflow = Workflow(graph=graph, metadata=WorkflowMetadata(name="t"))
        executor = DeterministicExecutor(workflow)
        trace = executor.run()
        sink_record = next(r for r in trace.node_records if r["node_id"] == "sink")
        assert sink_record["outputs"]["received"] == 42

    def test_total_duration_positive(self):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        trace = executor.run()
        assert trace.get_total_duration_ms() > 0
