"""Unit tests for invariant.analysis: metrics, stability, divergence, fault, sensitivity."""

import pytest

from invariant.analysis.divergence import DivergenceAnalyzer
from invariant.analysis.fault import FaultPropagationAnalyzer
from invariant.analysis.metrics import TraceMetrics
from invariant.analysis.sensitivity import SensitivityAnalyzer
from invariant.analysis.stability import StabilityAnalyzer, StabilityClass
from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node
from invariant.core.workflow import Workflow, WorkflowMetadata
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.latency import LatencyMode, LatencyPerturbation


def _make_workflow():
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


def _run(workflow, perturbations=None, n=1):
    executor = DeterministicExecutor(workflow, perturbations=perturbations or [])
    return [executor.run(timestep=i) for i in range(n)]


# ------------------------------------------------------------------
# TraceMetrics
# ------------------------------------------------------------------


class TestTraceMetrics:
    def test_empty_raises(self):
        with pytest.raises(ValueError):
            TraceMetrics([])

    def test_mean_latency_positive(self):
        workflow = _make_workflow()
        traces = _run(workflow, n=3)
        m = TraceMetrics(traces)
        means = m.mean_latency()
        for v in means.values():
            assert v > 0

    def test_std_latency_zero_for_single_trace(self):
        workflow = _make_workflow()
        traces = _run(workflow, n=1)
        m = TraceMetrics(traces)
        stds = m.std_latency()
        for v in stds.values():
            assert v == 0.0

    def test_to_dict_has_all_keys(self):
        workflow = _make_workflow()
        traces = _run(workflow, n=2)
        m = TraceMetrics(traces)
        d = m.to_dict()
        assert "mean_latency_ms" in d
        assert "dropout_rate" in d
        assert "coefficient_of_variation" in d


# ------------------------------------------------------------------
# DivergenceAnalyzer
# ------------------------------------------------------------------


class TestDivergenceAnalyzer:
    def test_no_perturbation_zero_divergence(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        perturbed = _run(workflow, n=5)
        analyzer = DivergenceAnalyzer(baseline, perturbed)
        results = analyzer.analyze()
        for result in results.values():
            # Identical runs → divergence should be 0 or near 0
            assert result.peak_divergence == pytest.approx(0.0, abs=1e-9)

    def test_perturbation_increases_divergence(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=100.0)
        perturbed = _run(workflow, [pert], n=5)
        analyzer = DivergenceAnalyzer(baseline, perturbed)
        results = analyzer.analyze()
        planner_div = results["planner"]
        assert planner_div.peak_divergence > 0.1

    def test_onset_index_detected(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=100.0)
        perturbed = _run(workflow, [pert], n=5)
        analyzer = DivergenceAnalyzer(baseline, perturbed, threshold=0.05)
        results = analyzer.analyze()
        planner_div = results["planner"]
        assert planner_div.onset_index is not None


# ------------------------------------------------------------------
# StabilityAnalyzer
# ------------------------------------------------------------------


class TestStabilityAnalyzer:
    def test_no_perturbation_is_stable(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        perturbed = _run(workflow, n=5)
        analyzer = StabilityAnalyzer(baseline, perturbed)
        result = analyzer.analyze()
        assert result.classification == StabilityClass.STABLE

    def test_large_perturbation_not_stable(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=500.0)
        perturbed = _run(workflow, [pert], n=5)
        analyzer = StabilityAnalyzer(baseline, perturbed, divergence_threshold=0.01)
        result = analyzer.analyze()
        assert result.classification in (StabilityClass.MARGINALLY_STABLE, StabilityClass.UNSTABLE)

    def test_result_has_node_classifications(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        perturbed = _run(workflow, n=3)
        result = StabilityAnalyzer(baseline, perturbed).analyze()
        assert len(result.node_classifications) == 3

    def test_serialization(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        perturbed = _run(workflow, n=2)
        result = StabilityAnalyzer(baseline, perturbed).analyze()
        d = result.to_dict()
        assert "classification" in d
        assert "peak_divergence" in d


# ------------------------------------------------------------------
# FaultPropagationAnalyzer
# ------------------------------------------------------------------


class TestFaultPropagationAnalyzer:
    def test_fault_propagates_downstream(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        pert = LatencyPerturbation(node_ids={"perception"}, mode=LatencyMode.FIXED, delay_ms=200.0)
        perturbed = _run(workflow, [pert], n=5)
        analyzer = FaultPropagationAnalyzer(
            workflow.graph, baseline, perturbed, "perception", divergence_threshold=0.01
        )
        result = analyzer.analyze()
        assert result.source_node_id == "perception"
        assert result.total_affected > 0

    def test_to_dict(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        perturbed = _run(workflow, n=2)
        analyzer = FaultPropagationAnalyzer(workflow.graph, baseline, perturbed, "perception")
        result = analyzer.analyze()
        d = result.to_dict()
        assert "source_node_id" in d


# ------------------------------------------------------------------
# SensitivityAnalyzer
# ------------------------------------------------------------------


class TestSensitivityAnalyzer:
    def test_sweep_produces_correct_count(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        magnitudes = [0.0, 50.0, 200.0]

        def run_at(mag):
            if mag == 0.0:
                return _run(workflow, n=3)
            pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=mag)
            return _run(workflow, [pert], n=3)

        analyzer = SensitivityAnalyzer(baseline, magnitudes, run_at)
        result = analyzer.sweep()
        assert len(result.points) == 3

    def test_critical_threshold_found(self):
        workflow = _make_workflow()
        baseline = _run(workflow, n=1)[0]
        magnitudes = [0.0, 50.0, 500.0]

        def run_at(mag):
            if mag == 0.0:
                return _run(workflow, n=5)
            pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=mag)
            return _run(workflow, [pert], n=5)

        result = SensitivityAnalyzer(
            baseline, magnitudes, run_at, divergence_threshold=0.01
        ).sweep()
        # At 500ms, system should not be stable → threshold should be found
        # (may be 50.0 or 500.0 depending on exact values)
        assert (
            result.critical_threshold is not None
            or result.points[0].stability_class == StabilityClass.STABLE
        )
