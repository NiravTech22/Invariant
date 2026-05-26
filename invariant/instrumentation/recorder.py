"""ExperimentRecorder: manages experiment output directory structure."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml

from invariant.instrumentation.tracer import ExecutionTrace


class ExperimentRecorder:
    """Writes all artifacts from one experiment to a structured directory.

    Creates this layout::

        <output_dir>/<experiment_name>_<timestamp>/
            config.yaml        # Full experiment configuration
            workflow.yaml      # Workflow definition used
            baseline.json      # Baseline (no-perturbation) trace
            run_001.json       # Perturbed run 1
            run_002.json       # Perturbed run 2
            ...
            report.md          # Auto-generated report (written by report layer)

    Args:
        output_dir: Root directory where experiment subdirectories are created.
        experiment_name: Short identifier used in the directory name.

    Raises:
        OSError: If the directory cannot be created.
    """

    def __init__(self, output_dir: str | Path, experiment_name: str) -> None:
        self.output_dir = Path(output_dir)
        self.experiment_name = experiment_name
        self._exp_dir: Path | None = None

    def setup(self, timestamp_suffix: str) -> Path:
        """Create the experiment subdirectory and return its path.

        Args:
            timestamp_suffix: String appended to the directory name
                (e.g. ``"20240601_143022"``).

        Returns:
            Path to the created experiment directory.
        """
        dir_name = f"{self.experiment_name}_{timestamp_suffix}"
        self._exp_dir = self.output_dir / dir_name
        self._exp_dir.mkdir(parents=True, exist_ok=True)
        return self._exp_dir

    @property
    def exp_dir(self) -> Path:
        """Path to the experiment directory (call :meth:`setup` first)."""
        if self._exp_dir is None:
            raise RuntimeError("Call setup() before accessing exp_dir")
        return self._exp_dir

    def save_config(self, config: dict[str, Any]) -> None:
        """Write experiment configuration to ``config.yaml``.

        Args:
            config: Serializable dict of experiment parameters.
        """
        path = self.exp_dir / "config.yaml"
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(config, fh, default_flow_style=False, sort_keys=False)

    def save_workflow(self, workflow_dict: dict[str, Any]) -> None:
        """Write the workflow definition to ``workflow.yaml``.

        Args:
            workflow_dict: Dict as produced by :meth:`Workflow.to_dict`.
        """
        path = self.exp_dir / "workflow.yaml"
        with open(path, "w", encoding="utf-8") as fh:
            yaml.dump(workflow_dict, fh, default_flow_style=False, sort_keys=False)

    def save_baseline(self, trace: ExecutionTrace) -> Path:
        """Write the baseline trace to ``baseline.json``.

        Args:
            trace: Baseline execution trace.

        Returns:
            Path to the written file.
        """
        path = self.exp_dir / "baseline.json"
        path.write_text(trace.to_json(), encoding="utf-8")
        return path

    def save_run(self, trace: ExecutionTrace, run_number: int) -> Path:
        """Write a perturbed run trace to ``run_NNN.json``.

        Args:
            trace: Perturbed execution trace.
            run_number: 1-based run index.

        Returns:
            Path to the written file.
        """
        filename = f"run_{run_number:03d}.json"
        path = self.exp_dir / filename
        path.write_text(trace.to_json(), encoding="utf-8")
        return path

    def save_report(self, report_text: str, filename: str = "report.md") -> Path:
        """Write the generated report to the experiment directory.

        Args:
            report_text: Report content.
            filename: Destination filename within the experiment dir.

        Returns:
            Path to the written file.
        """
        path = self.exp_dir / filename
        path.write_text(report_text, encoding="utf-8")
        return path

    def load_baseline(self) -> ExecutionTrace:
        """Load the baseline trace from the experiment directory."""
        path = self.exp_dir / "baseline.json"
        return ExecutionTrace.from_json(path.read_text(encoding="utf-8"))

    def load_runs(self) -> list[ExecutionTrace]:
        """Load all perturbed run traces in order."""
        run_files = sorted(self.exp_dir.glob("run_*.json"))
        return [ExecutionTrace.from_json(f.read_text(encoding="utf-8")) for f in run_files]

    def load_config(self) -> dict[str, Any]:
        """Load experiment configuration from ``config.yaml``."""
        path = self.exp_dir / "config.yaml"
        with open(path, encoding="utf-8") as fh:
            return cast(dict[str, Any], yaml.safe_load(fh))
