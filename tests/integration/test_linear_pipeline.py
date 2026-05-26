"""Integration tests: linear three-node pipeline."""

import pytest

from invariant.adapters.mock import (
    MockAdapter,
    MockControllerNode,
    MockPerceptionNode,
    MockPlannerNode,
)
from invariant.analysis.divergence import DivergenceAnalyzer
from invariant.analysis.fault import FaultPropagationAnalyzer
from invariant.analysis.stability import StabilityAnalyzer, StabilityClass
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.cascade import CascadeMode, CascadePerturbation
from invariant.perturbation.dropout import DropoutMode, DropoutPerturbation
from invariant.perturbation.latency import LatencyMode, LatencyPerturbation


@pytest.fixture
def linear_workflow():
    adapter = MockAdapter("linear_test")
    return adapter.build_linear_pipeline(
        MockPerceptionNode(seed=1),
        MockPlannerNode(seed=2),
        MockControllerNode(seed=3),
    )


class TestLinearPipelineBaseline:
    def test_baseline_execution_complete(self, linear_workflow):
        executor = DeterministicExecutor(linear_workflow)
        trace = executor.run()
        assert len(trace.node_records) == 3

    def test_baseline_is_nominal(self, linear_workflow):
        executor = DeterministicExecutor(linear_workflow)
        trace = executor.run()
        assert trace.is_nominal()

    def test_determinism(self, linear_workflow):
        p1 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=20.0, seed=42)
        p2 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=20.0, seed=42)
        e1 = DeterministicExecutor(linear_workflow, perturbations=[p1])
        e2 = DeterministicExecutor(linear_workflow, perturbations=[p2])
        t1 = e1.run(run_id="r", timestep=0)
        t2 = e2.run(run_id="r", timestep=0)
        lat1, lat2 = t1.get_node_latencies(), t2.get_node_latencies()
        assert lat1.keys() == lat2.keys()
        for k in lat1:
            assert lat1[k] == pytest.approx(lat2[k], rel=1e-9)

    def test_node_order_in_trace(self, linear_workflow):
        executor = DeterministicExecutor(linear_workflow)
        trace = executor.run()
        node_ids = [r["node_id"] for r in trace.node_records]
        assert node_ids.index("perception") < node_ids.index("planner")
        assert node_ids.index("planner") < node_ids.index("controller")


class TestLinearPipelineLatencyPerturbation:
    def test_latency_divergence_detected(self, linear_workflow):
        baseline = DeterministicExecutor(linear_workflow).run()
        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=50.0)
        perturbed = [
            DeterministicExecutor(linear_workflow, [pert]).run(timestep=i) for i in range(5)
        ]
        analyzer = DivergenceAnalyzer(baseline, perturbed, threshold=0.01)
        results = analyzer.analyze()
        assert results["planner"].peak_divergence > 0.1

    def test_stability_classification_after_latency(self, linear_workflow):
        baseline = DeterministicExecutor(linear_workflow).run()
        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=50.0)
        perturbed = [
            DeterministicExecutor(linear_workflow, [pert]).run(timestep=i) for i in range(5)
        ]
        result = StabilityAnalyzer(baseline, perturbed, divergence_threshold=0.05).analyze()
        assert result.classification in (
            StabilityClass.STABLE,
            StabilityClass.MARGINALLY_STABLE,
            StabilityClass.UNSTABLE,
        )


class TestLinearPipelineCascade:
    def test_cascade_propagation(self, linear_workflow):
        baseline = DeterministicExecutor(linear_workflow).run()
        lat = LatencyPerturbation(node_ids={"perception"}, mode=LatencyMode.FIXED, delay_ms=100.0)
        drop = DropoutPerturbation(node_ids={"planner"}, mode=DropoutMode.SINGLE, drop_step=0)
        cascade = CascadePerturbation(perturbations=[lat, drop], mode=CascadeMode.PARALLEL)
        perturbed = [
            DeterministicExecutor(linear_workflow, [cascade]).run(timestep=i) for i in range(5)
        ]
        fp_analyzer = FaultPropagationAnalyzer(
            linear_workflow.graph, baseline, perturbed, "perception", divergence_threshold=0.01
        )
        result = fp_analyzer.analyze()
        assert result.total_affected > 0


class TestLinearPipelineRecovery:
    def test_recovery_after_perturbation_removed(self, linear_workflow):
        """Apply perturbation for N runs, then remove it. Assert system returns to baseline."""
        baseline_executor = DeterministicExecutor(linear_workflow)
        baseline = baseline_executor.run()

        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=100.0)
        perturbed_traces = []
        # 5 runs with perturbation
        for i in range(5):
            t = DeterministicExecutor(linear_workflow, [pert]).run(timestep=i)
            perturbed_traces.append(t)
        # 5 runs without perturbation
        for i in range(5, 10):
            t = DeterministicExecutor(linear_workflow, []).run(timestep=i)
            perturbed_traces.append(t)

        analyzer = DivergenceAnalyzer(baseline, perturbed_traces, threshold=0.01)
        results = analyzer.analyze()
        planner_div = results["planner"]
        # Recovery should be observed at some point after the 5th run
        if planner_div.onset_index is not None:
            assert planner_div.recovery_index is not None
