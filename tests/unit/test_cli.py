"""Unit tests for the Invariant CLI commands."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from invariant.cli.main import main

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples"
SIMPLE_PIPELINE = str(EXAMPLES_DIR / "simple_pipeline.yaml")
CALIBRA_TEMPLATE = str(EXAMPLES_DIR / "calibra_template.yaml")


@pytest.fixture
def runner():
    return CliRunner()


class TestValidateCommand:
    def test_valid_workflow_passes(self, runner):
        result = runner.invoke(main, ["validate", SIMPLE_PIPELINE])
        assert result.exit_code == 0
        assert "[OK]" in result.output

    def test_calibra_template_valid(self, runner):
        result = runner.invoke(main, ["validate", CALIBRA_TEMPLATE])
        assert result.exit_code == 0

    def test_nonexistent_file_fails(self, runner):
        result = runner.invoke(main, ["validate", "/nonexistent/workflow.yaml"])
        assert result.exit_code == 1

    def test_cyclic_workflow_fails(self, runner, tmp_path):
        cyclic = tmp_path / "cyclic.yaml"
        cyclic.write_text("""
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
""")
        result = runner.invoke(main, ["validate", str(cyclic)])
        assert result.exit_code == 1


class TestPerturbationsCommand:
    def test_list_perturbations(self, runner):
        result = runner.invoke(main, ["perturbations", "list"])
        assert result.exit_code == 0
        assert "LatencyPerturbation" in result.output
        assert "DropoutPerturbation" in result.output
        assert "NoisePerturbation" in result.output

    def test_describe_latency(self, runner):
        result = runner.invoke(main, ["perturbations", "describe", "LatencyPerturbation"])
        assert result.exit_code == 0
        assert "mode" in result.output.lower()

    def test_describe_dropout(self, runner):
        result = runner.invoke(main, ["perturbations", "describe", "DropoutPerturbation"])
        assert result.exit_code == 0

    def test_describe_unknown_fails(self, runner):
        result = runner.invoke(main, ["perturbations", "describe", "UnknownType"])
        assert result.exit_code == 1


class TestRunCommand:
    def test_run_experiment_config(self, runner, tmp_path):
        config = tmp_path / "exp.yaml"
        config.write_text(f"""
name: cli_test
workflow_path: {SIMPLE_PIPELINE}
num_perturbed_runs: 2
seed: 42
output_dir: {tmp_path}
perturbations:
  - type: LatencyPerturbation
    node_ids: [planner]
    params:
      mode: fixed
      delay_ms: 20.0
    seed: 42
""")
        result = runner.invoke(main, ["run", str(config), "--output-dir", str(tmp_path)])
        assert result.exit_code == 0
        assert "Stability" in result.output

    def test_run_nonexistent_config_fails(self, runner):
        result = runner.invoke(main, ["run", "/nonexistent/config.yaml"])
        assert result.exit_code == 1

    def test_run_quiet_flag(self, runner, tmp_path):
        config = tmp_path / "exp.yaml"
        config.write_text(f"""
name: cli_quiet
workflow_path: {SIMPLE_PIPELINE}
num_perturbed_runs: 2
seed: 42
output_dir: {tmp_path}
""")
        result = runner.invoke(main, ["--quiet", "run", str(config), "--no-save"])
        # Quiet mode: should still succeed but produce minimal output
        assert result.exit_code == 0


class TestVersionCommand:
    def test_version_flag(self, runner):
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
