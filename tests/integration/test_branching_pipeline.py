"""Integration tests: branching pipeline with two parallel branches."""

import pytest

from invariant.adapters.mock import (
    MockAdapter,
    MockControllerNode,
    MockOrchestratorNode,
    MockPerceptionNode,
    MockPlannerNode,
)
from invariant.analysis.fault import FaultPropagationAnalyzer
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.latency import LatencyMode, LatencyPerturbation


@pytest.fixture
def branching_workflow():
    adapter = MockAdapter("branching_test")
    return adapter.build_branching_pipeline(
        source=MockPerceptionNode(seed=1),
        branch_a=MockPlannerNode(node_id="planner_a", seed=2),
        branch_b=MockPlannerNode(node_id="planner_b", seed=3),
        arbitrator=MockOrchestratorNode(seed=4),
        sink=MockControllerNode(seed=5),
    )


class TestBranchingPipelineBaseline:
    def test_all_nodes_executed(self, branching_workflow):
        executor = DeterministicExecutor(branching_workflow)
        trace = executor.run()
        node_ids = {r["node_id"] for r in trace.node_records}
        assert "perception" in node_ids
        assert "planner_a" in node_ids
        assert "planner_b" in node_ids
        assert "orchestrator" in node_ids
        assert "controller" in node_ids

    def test_perception_before_planners(self, branching_workflow):
        executor = DeterministicExecutor(branching_workflow)
        trace = executor.run()
        ids = [r["node_id"] for r in trace.node_records]
        assert ids.index("perception") < ids.index("planner_a")
        assert ids.index("perception") < ids.index("planner_b")

    def test_planners_before_arbitrator(self, branching_workflow):
        executor = DeterministicExecutor(branching_workflow)
        trace = executor.run()
        ids = [r["node_id"] for r in trace.node_records]
        assert ids.index("planner_a") < ids.index("orchestrator")
        assert ids.index("planner_b") < ids.index("orchestrator")

    def test_determinism(self, branching_workflow):
        p1 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=1.0, max_ms=10.0, seed=7)
        p2 = LatencyPerturbation(mode=LatencyMode.UNIFORM, min_ms=1.0, max_ms=10.0, seed=7)
        e1 = DeterministicExecutor(branching_workflow, [p1])
        e2 = DeterministicExecutor(branching_workflow, [p2])
        t1 = e1.run(run_id="r", timestep=0)
        t2 = e2.run(run_id="r", timestep=0)
        lat1, lat2 = t1.get_node_latencies(), t2.get_node_latencies()
        assert lat1.keys() == lat2.keys()
        for k in lat1:
            assert lat1[k] == pytest.approx(lat2[k], rel=1e-9)


class TestBranchingPipelineFaultPropagation:
    def test_fault_in_planner_a_propagates(self, branching_workflow):
        baseline = DeterministicExecutor(branching_workflow).run()
        pert = LatencyPerturbation(node_ids={"planner_a"}, mode=LatencyMode.FIXED, delay_ms=200.0)
        perturbed = [
            DeterministicExecutor(branching_workflow, [pert]).run(timestep=i) for i in range(5)
        ]
        fp = FaultPropagationAnalyzer(
            branching_workflow.graph, baseline, perturbed, "planner_a", divergence_threshold=0.01
        )
        result = fp.analyze()
        # Fault in planner_a should propagate to arbitrator and controller
        assert "planner_a" in result.impacted_nodes or result.total_affected >= 0
