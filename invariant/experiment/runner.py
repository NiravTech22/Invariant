"""ExperimentRunner: orchestrates baseline + perturbed runs with full analysis."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from invariant.analysis.metrics import TraceMetrics
from invariant.analysis.stability import StabilityAnalyzer, StabilityResult
from invariant.core.workflow import Workflow
from invariant.execution.executor import DeterministicExecutor
from invariant.experiment.config import ExperimentConfig
from invariant.experiment.report import ReportGenerator
from invariant.instrumentation.recorder import ExperimentRecorder
from invariant.instrumentation.tracer import ExecutionTrace
from invariant.perturbation.base import BasePerturbation
from invariant.utils.logging import get_logger

logger = get_logger(__name__)


class ExperimentResult:
    """Aggregated results from one experiment run.

    Attributes:
        experiment_id: Unique identifier for this experiment.
        config: The configuration that produced these results.
        baseline: Baseline trace (no perturbations).
        perturbed_runs: All perturbed traces.
        stability: Stability analysis result.
        metrics: Aggregate trace metrics.
        exp_dir: Path to output directory (None if not saved).
    """

    def __init__(
        self,
        experiment_id: str,
        config: ExperimentConfig,
        baseline: ExecutionTrace,
        perturbed_runs: list[ExecutionTrace],
        stability: StabilityResult,
        metrics: TraceMetrics,
        exp_dir: Path | None = None,
    ) -> None:
        self.experiment_id = experiment_id
        self.config = config
        self.baseline = baseline
        self.perturbed_runs = perturbed_runs
        self.stability = stability
        self.metrics = metrics
        self.exp_dir = exp_dir

    def save(self, output_dir: str | Path | None = None) -> Path:
        """Save all artifacts to an experiment directory.

        Args:
            output_dir: Override for the output directory. Falls back to
                ``config.output_dir`` if None.

        Returns:
            Path to the created experiment directory.
        """
        out = Path(output_dir or self.config.output_dir)
        timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
        recorder = ExperimentRecorder(out, self.config.name)
        exp_dir = recorder.setup(timestamp)

        recorder.save_config(self.config.to_dict())

        workflow = Workflow.from_yaml(self.config.workflow_path)
        recorder.save_workflow(workflow.to_dict())

        recorder.save_baseline(self.baseline)
        for i, run in enumerate(self.perturbed_runs, start=1):
            recorder.save_run(run, i)

        generator = ReportGenerator()
        md_report = generator.markdown(self)
        recorder.save_report(md_report, "report.md")

        self.exp_dir = exp_dir
        logger.info(f"Experiment saved to {exp_dir}")
        return exp_dir

    def report(self, format: str = "markdown") -> str:  # noqa: A002
        """Generate a report string.

        Args:
            format: One of ``"markdown"``, ``"json"``, ``"csv"``, ``"latex"``.

        Returns:
            Report as a string.

        Raises:
            ValueError: If format is unknown.
        """
        generator = ReportGenerator()
        fmt = format.lower()
        if fmt == "markdown":
            return generator.markdown(self)
        if fmt == "json":
            return generator.json(self)
        if fmt == "csv":
            return generator.csv(self)
        if fmt == "latex":
            return generator.latex(self)
        raise ValueError(f"Unknown report format '{format}'. Choose: markdown, json, csv, latex")

    def to_dict(self) -> dict[str, Any]:
        """Return a summary dict of this result."""
        return {
            "experiment_id": self.experiment_id,
            "config_name": self.config.name,
            "stability_class": self.stability.classification.value,
            "peak_divergence": self.stability.peak_divergence,
            "recovery_steps": self.stability.recovery_steps,
            "num_perturbed_runs": len(self.perturbed_runs),
            "metrics": self.metrics.to_dict(),
        }


def _build_perturbations(config: ExperimentConfig) -> list[BasePerturbation]:
    """Instantiate perturbation objects from config."""
    from invariant.perturbation.dropout import DropoutPerturbation
    from invariant.perturbation.latency import LatencyPerturbation
    from invariant.perturbation.noise import NoisePerturbation
    from invariant.perturbation.overload import OverloadPerturbation

    registry = {
        "LatencyPerturbation": LatencyPerturbation,
        "DropoutPerturbation": DropoutPerturbation,
        "NoisePerturbation": NoisePerturbation,
        "OverloadPerturbation": OverloadPerturbation,
    }

    perturbations: list[BasePerturbation] = []
    for pc in config.perturbations:
        cls = registry.get(pc.type)
        if cls is None:
            raise ValueError(
                f"Unknown perturbation type '{pc.type}'. Available: {list(registry.keys())}"
            )
        node_ids = set(pc.node_ids) if pc.node_ids else None
        params = {**pc.params}
        if pc.seed is not None:
            params["seed"] = pc.seed
        if node_ids is not None:
            params["node_ids"] = node_ids
        perturbations.append(cls(**params))

    return perturbations


class ExperimentRunner:
    """Orchestrates a complete experiment: baseline + perturbed runs + analysis.

    Steps:
    1. Load workflow from config.
    2. Run baseline (no perturbations).
    3. Run ``num_perturbed_runs`` perturbed trials.
    4. Run stability, divergence, and fault propagation analysis.
    5. Collect all results into an ExperimentResult.

    Args:
        config: Validated ExperimentConfig.

    Example::

        config = ExperimentConfig.from_yaml("experiments/latency_sweep.yaml")
        runner = ExperimentRunner(config)
        result = runner.run()
        result.save()
        print(result.report(format="markdown"))
    """

    def __init__(self, config: ExperimentConfig) -> None:
        self.config = config
        self._workflow = Workflow.from_yaml(config.workflow_path)
        self._workflow.validate()

    def run(self) -> ExperimentResult:
        """Execute the experiment and return results.

        Returns:
            ExperimentResult with all traces and analysis.
        """
        experiment_id = str(uuid.uuid4())
        perturbations = _build_perturbations(self.config)

        logger.info(
            f"Starting experiment '{self.config.name}' "
            f"(seed={self.config.seed}, runs={self.config.num_perturbed_runs})"
        )

        # Baseline run
        baseline_executor = DeterministicExecutor(
            workflow=self._workflow,
            perturbations=[],
            initial_time_ms=0.0,
        )
        baseline = baseline_executor.run(run_id=f"{experiment_id}-baseline", timestep=0)
        logger.info("Baseline run complete")

        # Perturbed runs
        perturbed_runs: list[ExecutionTrace] = []
        for i in range(self.config.num_perturbed_runs):
            executor = DeterministicExecutor(
                workflow=self._workflow,
                perturbations=perturbations,
                initial_time_ms=0.0,
            )
            trace = executor.run(
                run_id=f"{experiment_id}-run-{i + 1:03d}",
                timestep=i,
            )
            perturbed_runs.append(trace)
            logger.debug(f"Perturbed run {i + 1}/{self.config.num_perturbed_runs} complete")

        logger.info("All runs complete; running analysis")

        # Analysis
        all_traces = [baseline] + perturbed_runs
        metrics = TraceMetrics(all_traces)

        stability_analyzer = StabilityAnalyzer(
            baseline=baseline,
            perturbed_traces=perturbed_runs,
            divergence_threshold=self.config.divergence_threshold,
        )
        stability = stability_analyzer.analyze()

        return ExperimentResult(
            experiment_id=experiment_id,
            config=self.config,
            baseline=baseline,
            perturbed_runs=perturbed_runs,
            stability=stability,
            metrics=metrics,
        )
