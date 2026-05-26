"""Integration tests for ExperimentRunner and report generation."""

import json
from pathlib import Path

import pytest

from invariant.experiment.config import ExperimentConfig, PerturbationConfig
from invariant.experiment.report import ReportGenerator
from invariant.experiment.runner import ExperimentRunner

WORKFLOW_PATH = str(Path(__file__).parent.parent.parent / "examples" / "simple_pipeline.yaml")


@pytest.fixture
def base_config():
    return ExperimentConfig(
        name="test_run",
        workflow_path=WORKFLOW_PATH,
        num_perturbed_runs=3,
        seed=42,
        output_dir="/tmp/invariant_test_output",
        perturbations=[
            PerturbationConfig(
                type="LatencyPerturbation",
                node_ids=["planner"],
                params={"mode": "fixed", "delay_ms": 50.0},
                seed=42,
            )
        ],
    )


class TestExperimentRunner:
    def test_runner_produces_result(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        assert len(result.perturbed_runs) == 3
        assert result.baseline is not None
        assert result.stability is not None

    def test_stability_result_has_classification(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        assert result.stability.classification is not None

    def test_save_creates_directory(self, base_config, tmp_path):
        base_config = base_config.model_copy(update={"output_dir": str(tmp_path)})
        runner = ExperimentRunner(base_config)
        result = runner.run()
        exp_dir = result.save(tmp_path)
        assert exp_dir.exists()
        assert (exp_dir / "baseline.json").exists()
        assert (exp_dir / "run_001.json").exists()
        assert (exp_dir / "config.yaml").exists()
        assert (exp_dir / "report.md").exists()


class TestReportGenerator:
    def test_markdown_report(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        generator = ReportGenerator()
        md = generator.markdown(result)
        assert "# Invariant Experiment Report" in md
        assert "Stability Assessment" in md

    def test_json_report(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        generator = ReportGenerator()
        json_str = generator.json(result)
        data = json.loads(json_str)
        assert "stability" in data
        assert "metrics" in data

    def test_csv_report(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        generator = ReportGenerator()
        csv_str = generator.csv(result)
        lines = csv_str.strip().split("\n")
        assert lines[0].startswith("run_label")
        assert len(lines) > 1  # header + data rows

    def test_latex_report(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        generator = ReportGenerator()
        latex = generator.latex(result)
        assert r"\begin{table}" in latex
        assert r"\end{table}" in latex

    def test_unknown_format_raises(self, base_config):
        runner = ExperimentRunner(base_config)
        result = runner.run()
        with pytest.raises(ValueError, match="Unknown report format"):
            result.report(format="xml")

    def test_dropout_perturbation_in_config(self, tmp_path):
        config = ExperimentConfig(
            name="dropout_test",
            workflow_path=WORKFLOW_PATH,
            num_perturbed_runs=3,
            output_dir=str(tmp_path),
            perturbations=[
                PerturbationConfig(
                    type="DropoutPerturbation",
                    node_ids=["planner"],
                    params={"mode": "single", "drop_step": 0},
                )
            ],
        )
        runner = ExperimentRunner(config)
        result = runner.run()
        assert result.stability is not None

    def test_noise_perturbation_in_config(self, tmp_path):
        config = ExperimentConfig(
            name="noise_test",
            workflow_path=WORKFLOW_PATH,
            num_perturbed_runs=3,
            output_dir=str(tmp_path),
            perturbations=[
                PerturbationConfig(
                    type="NoisePerturbation",
                    params={"magnitude": 0.1},
                    seed=99,
                )
            ],
        )
        runner = ExperimentRunner(config)
        result = runner.run()
        assert result.stability is not None
