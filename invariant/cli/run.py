"""CLI `invariant run` command."""

from __future__ import annotations

import sys

import click


@click.command()
@click.argument("config_path")
@click.option("--output-dir", default=None, help="Override output directory")
@click.option(
    "--perturb",
    default=None,
    help="Quick perturbation override: type name (e.g. LatencyPerturbation)",
)
@click.option("--node", default=None, help="Node ID to target with --perturb")
@click.option("--delay", default=None, help="Delay for latency perturbation (e.g. 50ms)")
@click.option("--save/--no-save", default=True, help="Save experiment artifacts to disk")
@click.pass_context
def run(
    ctx: click.Context,
    config_path: str,
    output_dir: str | None,
    perturb: str | None,
    node: str | None,
    delay: str | None,
    save: bool,
) -> None:
    """Run an experiment from a config file.

    CONFIG_PATH is the path to an experiment configuration YAML file.

    \b
    Examples:
        invariant run experiments/latency_sweep.yaml
        invariant run experiments/baseline.yaml --perturb LatencyPerturbation --node planner --delay 50ms
    """
    quiet = ctx.obj.get("quiet", False) if ctx.obj else False

    from invariant.experiment.config import ExperimentConfig, PerturbationConfig
    from invariant.experiment.runner import ExperimentRunner

    try:
        config = ExperimentConfig.from_yaml(config_path)
    except FileNotFoundError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"[ERROR] Invalid config: {exc}", err=True)
        sys.exit(1)

    # Command-line perturbation override
    if perturb:
        delay_ms = 0.0
        if delay:
            try:
                delay_ms = float(delay.rstrip("ms").strip())
            except ValueError:
                click.echo(f"[ERROR] Invalid delay value: {delay!r}", err=True)
                sys.exit(1)

        override_config = PerturbationConfig(
            type=perturb,
            node_ids=[node] if node else None,
            params={"mode": "fixed", "delay_ms": delay_ms} if "Latency" in perturb else {},
        )
        config = config.model_copy(update={"perturbations": [override_config]})

    if output_dir:
        config = config.model_copy(update={"output_dir": output_dir})

    if not quiet:
        click.echo(f"Running experiment: {config.name}")
        click.echo(f"  Workflow : {config.workflow_path}")
        click.echo(f"  Runs     : {config.num_perturbed_runs}")

    try:
        runner = ExperimentRunner(config)
        result = runner.run()
    except Exception as exc:
        click.echo(f"[ERROR] Experiment failed: {exc}", err=True)
        sys.exit(1)

    stab = result.stability
    if not quiet:
        click.echo(f"\nStability: {stab.classification.value.upper()}")
        click.echo(f"Peak divergence: {stab.peak_divergence:.4f}")
        rec = str(stab.recovery_steps) if stab.recovery_steps is not None else "not observed"
        click.echo(f"Recovery: {rec} run(s)")

    if save:
        try:
            exp_dir = result.save()
            if not quiet:
                click.echo(f"\nResults saved to: {exp_dir}")
        except Exception as exc:
            click.echo(f"[WARN] Could not save results: {exc}", err=True)

    sys.exit(0)
