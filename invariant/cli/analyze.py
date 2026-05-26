"""CLI `invariant analyze` command."""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command()
@click.argument("experiment_dir")
@click.option(
    "--format",
    "output_format",
    default="markdown",
    type=click.Choice(["markdown", "json", "csv", "latex"], case_sensitive=False),
    help="Report output format",
)
@click.option("--output", default=None, help="Write report to this file (default: stdout)")
@click.pass_context
def analyze(
    ctx: click.Context,
    experiment_dir: str,
    output_format: str,
    output: str | None,
) -> None:
    """Analyze results from an existing experiment directory.

    EXPERIMENT_DIR is the path to a saved experiment directory (created by
    `invariant run`). Loads all traces and runs the full analysis pipeline.

    \b
    Examples:
        invariant analyze experiments/output/latency_sweep_20240601_143022/
        invariant analyze experiments/output/my_exp/ --format json --output results.json
    """
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    exp_path = Path(experiment_dir)
    if not exp_path.exists():
        click.echo(f"[ERROR] Experiment directory not found: {exp_path}", err=True)
        sys.exit(1)

    from invariant.analysis.stability import StabilityAnalyzer
    from invariant.analysis.metrics import TraceMetrics
    from invariant.experiment.config import ExperimentConfig
    from invariant.experiment.report import ReportGenerator
    from invariant.experiment.runner import ExperimentResult
    from invariant.instrumentation.recorder import ExperimentRecorder
    from invariant.analysis.stability import StabilityResult, StabilityClass

    # Load artifacts from directory
    recorder = ExperimentRecorder(exp_path.parent, exp_path.name)
    recorder._exp_dir = exp_path  # point directly at the dir

    try:
        baseline = recorder.load_baseline()
        perturbed_runs = recorder.load_runs()
        config_data = recorder.load_config()
    except Exception as exc:
        click.echo(f"[ERROR] Failed to load experiment: {exc}", err=True)
        sys.exit(1)

    if not quiet:
        click.echo(f"Loaded experiment from: {exp_path}")
        click.echo(f"  Baseline + {len(perturbed_runs)} perturbed run(s)")

    all_traces = [baseline] + perturbed_runs
    metrics = TraceMetrics(all_traces)

    stability_analyzer = StabilityAnalyzer(
        baseline=baseline,
        perturbed_traces=perturbed_runs,
        divergence_threshold=config_data.get("divergence_threshold", 0.1),
    )
    stability = stability_analyzer.analyze()

    # Build minimal ExperimentResult for report generation
    try:
        config = ExperimentConfig(**config_data)
    except Exception:
        from pydantic import ValidationError
        # Config may be from an older format — create a minimal one
        from invariant.experiment.config import ExperimentConfig as EC
        config = EC(
            name=config_data.get("name", exp_path.name),
            workflow_path=config_data.get("workflow_path", "unknown"),
        )

    result = ExperimentResult(
        experiment_id=config_data.get("experiment_id", "loaded"),
        config=config,
        baseline=baseline,
        perturbed_runs=perturbed_runs,
        stability=stability,
        metrics=metrics,
        exp_dir=exp_path,
    )

    generator = ReportGenerator()
    fmt = output_format.lower()
    if fmt == "markdown":
        report_text = generator.markdown(result)
    elif fmt == "json":
        report_text = generator.json(result)
    elif fmt == "csv":
        report_text = generator.csv(result)
    elif fmt == "latex":
        report_text = generator.latex(result)
    else:
        click.echo(f"[ERROR] Unknown format: {fmt}", err=True)
        sys.exit(1)

    if output:
        Path(output).write_text(report_text, encoding="utf-8")
        if not quiet:
            click.echo(f"Report written to: {output}")
    else:
        click.echo(report_text)

    sys.exit(0)
