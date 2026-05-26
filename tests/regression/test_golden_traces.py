"""Regression tests: golden trace comparison for determinism guarantee.

These tests generate golden traces on first run and assert exact reproduction
on subsequent runs. They guard against any code change that breaks the
determinism guarantee.

To regenerate golden traces (e.g., after an intentional API change):
    INVARIANT_REGEN_GOLDEN=1 pytest tests/regression/test_golden_traces.py
"""

import json
import os
from pathlib import Path

import pytest

from invariant.adapters.mock import (
    MockAdapter,
    MockControllerNode,
    MockPerceptionNode,
    MockPlannerNode,
)
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.latency import LatencyMode, LatencyPerturbation

GOLDEN_DIR = Path(__file__).parent / "golden"
REGEN = os.environ.get("INVARIANT_REGEN_GOLDEN", "0") == "1"


@pytest.fixture(scope="session")
def linear_workflow_session():
    adapter = MockAdapter("regression_linear")
    return adapter.build_linear_pipeline(
        MockPerceptionNode(seed=10),
        MockPlannerNode(seed=20),
        MockControllerNode(seed=30),
    )


def _get_golden_path(name: str) -> Path:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    return GOLDEN_DIR / f"{name}.json"


def _run_regression(workflow, perturbations, run_id, timestep):
    executor = DeterministicExecutor(workflow, perturbations=perturbations, initial_time_ms=0.0)
    trace = executor.run(run_id=run_id, timestep=timestep)
    return trace


class TestGoldenTraces:
    def test_baseline_golden(self, linear_workflow_session):
        golden_path = _get_golden_path("baseline_linear")
        trace = _run_regression(linear_workflow_session, [], "golden-baseline", 0)
        actual = trace.get_node_latencies()

        if REGEN or not golden_path.exists():
            golden_path.write_text(json.dumps(actual, indent=2))
            pytest.skip(f"Golden trace written to {golden_path}")

        expected = json.loads(golden_path.read_text())
        assert actual == pytest.approx(expected, rel=1e-9), (
            f"Determinism regression: baseline trace differs from golden.\n"
            f"Expected: {expected}\nActual: {actual}"
        )

    def test_latency_perturbed_golden(self, linear_workflow_session):
        golden_path = _get_golden_path("latency_50ms_linear")
        pert = LatencyPerturbation(
            node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=50.0, seed=42
        )
        trace = _run_regression(linear_workflow_session, [pert], "golden-latency", 0)
        actual = trace.get_node_latencies()

        if REGEN or not golden_path.exists():
            golden_path.write_text(json.dumps(actual, indent=2))
            pytest.skip(f"Golden trace written to {golden_path}")

        expected = json.loads(golden_path.read_text())
        assert actual == pytest.approx(expected, rel=1e-9), (
            f"Determinism regression: latency trace differs from golden.\n"
            f"Expected: {expected}\nActual: {actual}"
        )

    def test_uniform_latency_golden(self, linear_workflow_session):
        golden_path = _get_golden_path("uniform_latency_linear")
        pert = LatencyPerturbation(
            node_ids=None, mode=LatencyMode.UNIFORM, min_ms=5.0, max_ms=20.0, seed=77
        )
        trace = _run_regression(linear_workflow_session, [pert], "golden-uniform", 0)
        actual = trace.get_node_latencies()

        if REGEN or not golden_path.exists():
            golden_path.write_text(json.dumps(actual, indent=2))
            pytest.skip(f"Golden trace written to {golden_path}")

        expected = json.loads(golden_path.read_text())
        assert actual == pytest.approx(expected, rel=1e-9)
