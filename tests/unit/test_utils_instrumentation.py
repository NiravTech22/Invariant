"""Unit tests for utils, instrumentation/profiler, and experiment/suite."""

from pathlib import Path

import pytest

from invariant.core.edge import Edge
from invariant.core.graph import WorkflowGraph
from invariant.core.node import LatencyBounds, Node
from invariant.core.workflow import Workflow, WorkflowMetadata
from invariant.execution.executor import DeterministicExecutor
from invariant.instrumentation.profiler import WorkflowProfiler
from invariant.instrumentation.recorder import ExperimentRecorder
from invariant.utils.logging import get_logger
from invariant.utils.serialization import load_json, load_yaml, save_json, save_yaml
from invariant.utils.validation import (
    require_file_exists,
    require_in_range,
    require_non_empty_string,
    require_non_negative,
    require_positive,
)


def _simple_workflow() -> Workflow:
    graph = WorkflowGraph()
    for nid in ["a", "b", "c"]:
        graph.add_node(
            Node(
                node_id=nid,
                latency_bounds=LatencyBounds(min_ms=1.0, max_ms=5.0),
                exec_fn=lambda inputs: {"val": 1.0},
            )
        )
    graph.add_edge(Edge(source_id="a", target_id="b"))
    graph.add_edge(Edge(source_id="b", target_id="c"))
    return Workflow(graph=graph, metadata=WorkflowMetadata(name="test"))


# ------------------------------------------------------------------
# Utils: serialization
# ------------------------------------------------------------------


class TestSerialization:
    def test_save_load_yaml(self, tmp_path):
        data = {"key": "value", "number": 42}
        p = tmp_path / "test.yaml"
        save_yaml(data, p)
        loaded = load_yaml(p)
        assert loaded == data

    def test_save_load_json(self, tmp_path):
        data = {"key": "value", "list": [1, 2, 3]}
        p = tmp_path / "test.json"
        save_json(data, p)
        loaded = load_json(p)
        assert loaded == data

    def test_load_yaml_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_yaml("/nonexistent/file.yaml")

    def test_load_json_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_json("/nonexistent/file.json")

    def test_save_creates_parent_dirs(self, tmp_path):
        nested = tmp_path / "a" / "b" / "c" / "file.yaml"
        save_yaml({"x": 1}, nested)
        assert nested.exists()


# ------------------------------------------------------------------
# Utils: validation
# ------------------------------------------------------------------


class TestValidationUtils:
    def test_require_non_empty_string_ok(self):
        assert require_non_empty_string("hello", "x") == "hello"

    def test_require_non_empty_string_empty_raises(self):
        with pytest.raises(ValueError):
            require_non_empty_string("", "x")

    def test_require_non_empty_string_whitespace_raises(self):
        with pytest.raises(ValueError):
            require_non_empty_string("   ", "x")

    def test_require_non_empty_string_non_str_raises(self):
        with pytest.raises(TypeError):
            require_non_empty_string(42, "x")

    def test_require_positive_ok(self):
        assert require_positive(5.0, "x") == 5.0

    def test_require_positive_zero_raises(self):
        with pytest.raises(ValueError):
            require_positive(0.0, "x")

    def test_require_positive_negative_raises(self):
        with pytest.raises(ValueError):
            require_positive(-1.0, "x")

    def test_require_non_negative_ok(self):
        assert require_non_negative(0.0, "x") == 0.0

    def test_require_non_negative_negative_raises(self):
        with pytest.raises(ValueError):
            require_non_negative(-0.1, "x")

    def test_require_file_exists_ok(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("x")
        assert require_file_exists(f, "f") == f

    def test_require_file_exists_raises(self):
        with pytest.raises(FileNotFoundError):
            require_file_exists("/nonexistent", "f")

    def test_require_in_range_ok(self):
        assert require_in_range(0.5, 0.0, 1.0, "x") == 0.5

    def test_require_in_range_out_raises(self):
        with pytest.raises(ValueError):
            require_in_range(1.5, 0.0, 1.0, "x")


# ------------------------------------------------------------------
# Utils: logging
# ------------------------------------------------------------------


class TestLogging:
    def test_get_logger_returns_logger(self):
        import logging

        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_idempotent(self):
        l1 = get_logger("same_name")
        l2 = get_logger("same_name")
        assert l1 is l2


# ------------------------------------------------------------------
# WorkflowProfiler
# ------------------------------------------------------------------


class TestWorkflowProfiler:
    def _make_traces(self, n=5):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        return [executor.run(timestep=i) for i in range(n)]

    def test_node_profiles_all_nodes(self):
        traces = self._make_traces(5)
        profiler = WorkflowProfiler(traces)
        profiles = profiler.node_profiles()
        assert set(profiles.keys()) == {"a", "b", "c"}

    def test_node_profile_stats_positive(self):
        traces = self._make_traces(5)
        profiler = WorkflowProfiler(traces)
        profiles = profiler.node_profiles()
        for p in profiles.values():
            assert p.mean_ms > 0
            assert p.min_ms <= p.mean_ms <= p.max_ms
            assert p.sample_count == 5

    def test_total_duration_stats(self):
        traces = self._make_traces(5)
        profiler = WorkflowProfiler(traces)
        stats = profiler.total_duration_stats()
        assert "mean_ms" in stats
        assert stats["mean_ms"] > 0

    def test_bottleneck_nodes_returns_top_n(self):
        traces = self._make_traces(5)
        profiler = WorkflowProfiler(traces)
        bottlenecks = profiler.bottleneck_nodes(top_n=2)
        assert len(bottlenecks) == 2


# ------------------------------------------------------------------
# ExperimentRecorder
# ------------------------------------------------------------------


class TestExperimentRecorder:
    def test_save_load_baseline(self, tmp_path):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        trace = executor.run()

        recorder = ExperimentRecorder(tmp_path, "test_exp")
        recorder.setup("20240101_120000")
        recorder.save_baseline(trace)
        loaded = recorder.load_baseline()
        assert loaded.run_id == trace.run_id

    def test_save_load_runs(self, tmp_path):
        workflow = _simple_workflow()
        executor = DeterministicExecutor(workflow)
        traces = [executor.run(timestep=i) for i in range(3)]

        recorder = ExperimentRecorder(tmp_path, "test_exp")
        recorder.setup("20240101_120000")
        for i, t in enumerate(traces, 1):
            recorder.save_run(t, i)
        loaded = recorder.load_runs()
        assert len(loaded) == 3

    def test_save_report(self, tmp_path):
        recorder = ExperimentRecorder(tmp_path, "test_exp")
        recorder.setup("20240101_120000")
        path = recorder.save_report("# Test Report\n", "report.md")
        assert path.exists()
        assert path.read_text() == "# Test Report\n"

    def test_exp_dir_before_setup_raises(self):
        recorder = ExperimentRecorder("/tmp", "test")
        with pytest.raises(RuntimeError):
            _ = recorder.exp_dir

    def test_save_config(self, tmp_path):
        recorder = ExperimentRecorder(tmp_path, "test_exp")
        recorder.setup("20240101_120000")
        recorder.save_config({"name": "test", "seed": 42})
        config = recorder.load_config()
        assert config["name"] == "test"


# ------------------------------------------------------------------
# ExperimentSuite
# ------------------------------------------------------------------


SIMPLE_PIPELINE = str(Path(__file__).parent.parent.parent / "examples" / "simple_pipeline.yaml")


class TestExperimentSuite:
    def test_suite_from_config(self, tmp_path):
        suite_yaml = tmp_path / "suite.yaml"
        suite_yaml.write_text(f"""
suite_name: test_suite
experiments:
  - name: exp_1
    workflow_path: {SIMPLE_PIPELINE}
    num_perturbed_runs: 2
    seed: 42
    output_dir: {tmp_path}
  - name: exp_2
    workflow_path: {SIMPLE_PIPELINE}
    num_perturbed_runs: 2
    seed: 7
    output_dir: {tmp_path}
""")
        from invariant.experiment.suite import ExperimentSuite

        suite = ExperimentSuite.from_config(suite_yaml)
        assert len(suite.configs) == 2
        assert suite.suite_name == "test_suite"

    def test_suite_run(self, tmp_path):
        suite_yaml = tmp_path / "suite.yaml"
        suite_yaml.write_text(f"""
suite_name: run_suite
experiments:
  - name: run_1
    workflow_path: {SIMPLE_PIPELINE}
    num_perturbed_runs: 2
    seed: 1
    output_dir: {tmp_path}
""")
        from invariant.experiment.suite import ExperimentSuite

        suite = ExperimentSuite.from_config(suite_yaml)
        suite_result = suite.run()
        assert len(suite_result.results) == 1

    def test_suite_not_found_raises(self):
        from invariant.experiment.suite import ExperimentSuite

        with pytest.raises(FileNotFoundError):
            ExperimentSuite.from_config("/nonexistent/suite.yaml")
