"""ExperimentSuite: batch runner for multiple experiment configurations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from invariant.experiment.config import ExperimentConfig
from invariant.experiment.runner import ExperimentResult, ExperimentRunner
from invariant.utils.logging import get_logger

logger = get_logger(__name__)


class SuiteResult:
    """Results from running an entire experiment suite.

    Attributes:
        results: List of ExperimentResult, one per experiment in the suite.
        suite_name: Name of the suite.
    """

    def __init__(self, suite_name: str, results: list[ExperimentResult]) -> None:
        self.suite_name = suite_name
        self.results = results

    def save(self, output_dir: str | Path | None = None) -> list[Path]:
        """Save all experiment results to their output directories.

        Returns:
            List of paths to each experiment directory.
        """
        return [r.save(output_dir) for r in self.results]

    def summary(self) -> list[dict[str, Any]]:
        """Return a list of summary dicts, one per experiment."""
        return [r.to_dict() for r in self.results]


class ExperimentSuite:
    """Run multiple experiments defined in a single suite config file.

    The suite config YAML has this structure::

        suite_name: my_suite
        experiments:
          - name: latency_low
            workflow_path: examples/simple_pipeline.yaml
            num_perturbed_runs: 5
            perturbations:
              - type: LatencyPerturbation
                params: {mode: fixed, delay_ms: 10}
          - name: latency_high
            workflow_path: examples/simple_pipeline.yaml
            num_perturbed_runs: 5
            perturbations:
              - type: LatencyPerturbation
                params: {mode: fixed, delay_ms: 100}

    Args:
        configs: List of ExperimentConfig objects.
        suite_name: Name of the suite.

    Example::

        suite = ExperimentSuite.from_config("experiments/latency_sweep.yaml")
        results = suite.run()
        results.save()
    """

    def __init__(self, configs: list[ExperimentConfig], suite_name: str = "suite") -> None:
        self.configs = configs
        self.suite_name = suite_name

    @classmethod
    def from_config(cls, path: str | Path) -> ExperimentSuite:
        """Load a suite from a YAML config file.

        Args:
            path: Path to the suite configuration YAML.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValidationError: If any experiment config is invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Suite config not found: {path}")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        suite_name = data.get("suite_name", path.stem)
        experiments_data = data.get("experiments", [])

        configs: list[ExperimentConfig] = []
        for exp_data in experiments_data:
            configs.append(ExperimentConfig(**exp_data))

        return cls(configs=configs, suite_name=suite_name)

    def run(self) -> SuiteResult:
        """Run all experiments in the suite sequentially.

        Returns:
            SuiteResult with results from every experiment.
        """
        results: list[ExperimentResult] = []
        for i, config in enumerate(self.configs, start=1):
            logger.info(f"Running experiment {i}/{len(self.configs)}: {config.name}")
            runner = ExperimentRunner(config)
            result = runner.run()
            results.append(result)

        return SuiteResult(suite_name=self.suite_name, results=results)
