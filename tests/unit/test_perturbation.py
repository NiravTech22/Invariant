"""Unit tests for invariant.perturbation: all perturbation types."""

import pytest

from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node
from invariant.core.workflow import Workflow, WorkflowMetadata
from invariant.execution.clock import SimulatedClock
from invariant.execution.context import ExecutionContext
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.cascade import CascadeMode, CascadePerturbation
from invariant.perturbation.dropout import DropoutMode, DropoutPerturbation
from invariant.perturbation.latency import LatencyMode, LatencyPerturbation
from invariant.perturbation.noise import NoiseDistribution, NoisePerturbation
from invariant.perturbation.overload import OverloadPerturbation


def _make_ctx(timestep: int = 0) -> ExecutionContext:
    clock = SimulatedClock(0.0)
    return ExecutionContext(run_id="test", timestep=timestep, clock=clock)


def _simple_workflow() -> Workflow:
    graph = WorkflowGraph()
    for nid in ["perception", "planner", "controller"]:
        graph.add_node(
            Node(
                node_id=nid,
                latency_bounds=LatencyBounds(min_ms=1.0, max_ms=5.0),
                exec_fn=lambda inputs: {"val": 1.0},
            )
        )
    graph.add_edge(Edge(source_id="perception", target_id="planner"))
    graph.add_edge(Edge(source_id="planner", target_id="controller"))
    return Workflow(graph=graph, metadata=WorkflowMetadata(name="test"))


# ------------------------------------------------------------------
# LatencyPerturbation
# ------------------------------------------------------------------


class TestLatencyPerturbation:
    def test_fixed_delay(self):
        pert = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=50.0)
        ctx = _make_ctx()
        assert ctx.clock.now() == 0.0
        pert.apply(ctx, "planner")
        assert ctx.clock.now() == 50.0

    def test_zero_fixed_delay(self):
        pert = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=0.0)
        ctx = _make_ctx()
        pert.apply(ctx, "node")
        assert ctx.clock.now() == 0.0

    def test_uniform_delay_bounded(self):
        pert = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=10.0, max_ms=20.0, seed=99)
        for _ in range(50):
            ctx = _make_ctx()
            pert.apply(ctx, "node")
            assert 10.0 <= ctx.clock.now() <= 20.0

    def test_gaussian_delay_non_negative(self):
        pert = LatencyPerturbation(mode=LatencyMode.GAUSSIAN, max_ms=10.0, std_ms=2.0, seed=42)
        for _ in range(50):
            ctx = _make_ctx()
            pert.apply(ctx, "node")
            assert ctx.clock.now() >= 0.0

    def test_applies_to_all_nodes_when_none(self):
        pert = LatencyPerturbation()
        assert pert.applies_to("any_node", 0) is True

    def test_applies_to_specific_node(self):
        pert = LatencyPerturbation(node_ids={"planner"})
        assert pert.applies_to("planner", 0) is True
        assert pert.applies_to("controller", 0) is False

    def test_start_end_step_gating(self):
        pert = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=10.0, start_step=2, end_step=4)
        assert pert.applies_to("n", 1) is False
        assert pert.applies_to("n", 2) is True
        assert pert.applies_to("n", 4) is True
        assert pert.applies_to("n", 5) is False

    def test_serialization_roundtrip(self):
        pert = LatencyPerturbation(
            node_ids={"a"}, mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=50.0, seed=7
        )
        d = pert.to_dict()
        assert d["type"] == "LatencyPerturbation"
        assert d["mode"] == "uniform"

    def test_determinism_with_same_seed(self):
        p1 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=0.0, max_ms=100.0, seed=42)
        p2 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=0.0, max_ms=100.0, seed=42)
        delays1 = [p1._sample_delay() for _ in range(10)]
        delays2 = [p2._sample_delay() for _ in range(10)]
        assert delays1 == delays2


# ------------------------------------------------------------------
# DropoutPerturbation
# ------------------------------------------------------------------


class TestDropoutPerturbation:
    def test_single_dropout_on_correct_step(self):
        pert = DropoutPerturbation(mode=DropoutMode.SINGLE, drop_step=0)
        ctx = _make_ctx(timestep=0)
        ctx = pert.apply(ctx, "planner")
        assert ctx.get_output("planner__dropped__") != {}

    def test_single_dropout_not_on_wrong_step(self):
        pert = DropoutPerturbation(mode=DropoutMode.SINGLE, drop_step=5)
        ctx = _make_ctx(timestep=0)
        ctx = pert.apply(ctx, "planner")
        assert ctx.get_output("planner__dropped__") == {}

    def test_sustained_dropout(self):
        pert = DropoutPerturbation(mode=DropoutMode.SUSTAINED, start_step=2, duration=3)
        for step in [2, 3, 4]:
            ctx = _make_ctx(timestep=step)
            ctx = pert.apply(ctx, "node")
            assert ctx.get_output("node__dropped__") != {}, f"Should drop at step {step}"
        for step in [0, 1, 5]:
            ctx = _make_ctx(timestep=step)
            ctx = pert.apply(ctx, "node")
            assert ctx.get_output("node__dropped__") == {}, f"Should NOT drop at step {step}"

    def test_invalid_probability_raises(self):
        with pytest.raises(ValueError, match="drop_probability"):
            DropoutPerturbation(drop_probability=1.5)

    def test_node_filtering(self):
        pert = DropoutPerturbation(node_ids={"planner"}, mode=DropoutMode.SINGLE, drop_step=0)
        assert pert.applies_to("planner", 0) is True
        assert pert.applies_to("controller", 0) is False

    def test_dropout_effect_on_executor(self):
        workflow = _simple_workflow()
        pert = DropoutPerturbation(
            node_ids={"planner"},
            mode=DropoutMode.SINGLE,
            drop_step=0,
        )
        executor = DeterministicExecutor(workflow, perturbations=[pert])
        trace = executor.run(timestep=0)
        dropped = trace.get_dropped_nodes()
        assert "planner" in dropped


# ------------------------------------------------------------------
# NoisePerturbation
# ------------------------------------------------------------------


class TestNoisePerturbation:
    def test_noise_modifies_numeric_output(self):
        pert = NoisePerturbation(distribution=NoiseDistribution.GAUSSIAN, magnitude=0.1, seed=42)
        ctx = _make_ctx()
        ctx.set_output("node", {"value": 1.0, "label": "str"})
        pert.apply(ctx, "node")
        out = ctx.get_output("node")
        assert out["value"] != 1.0  # noise was added
        assert out["label"] == "str"  # non-numeric unchanged

    def test_noise_does_not_affect_empty_output(self):
        pert = NoisePerturbation()
        ctx = _make_ctx()
        pert.apply(ctx, "node")
        assert ctx.get_output("node") == {}

    def test_gaussian_noise_centered_near_zero(self):
        import numpy as np

        pert = NoisePerturbation(distribution=NoiseDistribution.GAUSSIAN, magnitude=0.01, seed=0)
        deltas = []
        for _ in range(1000):
            ctx = _make_ctx()
            ctx.set_output("n", {"x": 0.0})
            pert.apply(ctx, "n")
            deltas.append(ctx.get_output("n")["x"])
        assert abs(np.mean(deltas)) < 0.01

    def test_serialization(self):
        pert = NoisePerturbation(magnitude=0.5)
        d = pert.to_dict()
        assert d["type"] == "NoisePerturbation"


# ------------------------------------------------------------------
# OverloadPerturbation
# ------------------------------------------------------------------


class TestOverloadPerturbation:
    def test_overload_advances_clock(self):
        pert = OverloadPerturbation(min_overload_ms=10.0, max_overload_ms=100.0, seed=1)
        ctx = _make_ctx()
        pert.apply(ctx, "planner")
        assert ctx.clock.now() >= 10.0
        assert ctx.clock.now() <= 100.0

    def test_serialization(self):
        pert = OverloadPerturbation(min_overload_ms=5.0, max_overload_ms=50.0)
        d = pert.to_dict()
        assert d["type"] == "OverloadPerturbation"


# ------------------------------------------------------------------
# CascadePerturbation
# ------------------------------------------------------------------


class TestCascadePerturbation:
    def test_empty_list_raises(self):
        with pytest.raises(ValueError):
            CascadePerturbation(perturbations=[])

    def test_parallel_applies_both(self):
        lat = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=10.0)
        ov = OverloadPerturbation(min_overload_ms=5.0, max_overload_ms=5.0, seed=1)
        cascade = CascadePerturbation(perturbations=[lat, ov], mode=CascadeMode.PARALLEL)
        ctx = _make_ctx(timestep=0)
        cascade.apply(ctx, "planner")
        # Both should have applied: latency=10 + overload=5 = 15
        assert ctx.clock.now() == 15.0

    def test_sequential_round_robin(self):
        lat = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=20.0)
        ov = OverloadPerturbation(min_overload_ms=30.0, max_overload_ms=30.0, seed=1)
        cascade = CascadePerturbation(perturbations=[lat, ov], mode=CascadeMode.SEQUENTIAL)
        # step 0 → lat applied (20ms)
        ctx0 = _make_ctx(timestep=0)
        cascade.apply(ctx0, "n")
        # step 1 → ov applied (30ms)
        ctx1 = _make_ctx(timestep=1)
        cascade.apply(ctx1, "n")
        assert ctx0.clock.now() == 20.0
        assert ctx1.clock.now() == 30.0

    def test_serialization(self):
        lat = LatencyPerturbation(mode=LatencyMode.FIXED, delay_ms=5.0)
        cascade = CascadePerturbation(perturbations=[lat])
        d = cascade.to_dict()
        assert d["type"] == "CascadePerturbation"
        assert len(d["perturbations"]) == 1
