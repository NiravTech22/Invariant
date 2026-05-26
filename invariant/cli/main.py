"""Main CLI entry point for the `invariant` command."""

from __future__ import annotations

import sys

import click

from invariant.cli.analyze import analyze
from invariant.cli.report import report
from invariant.cli.run import run


@click.group()
@click.version_option(package_name="invariant-robotics")
@click.option("--verbose", is_flag=True, default=False, help="Enable verbose logging")
@click.option("--quiet", is_flag=True, default=False, help="Suppress all output except errors")
@click.pass_context
def main(ctx: click.Context, verbose: bool, quiet: bool) -> None:
    """Invariant: research framework for analyzing robotics workflow stability."""
    import os

    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose
    ctx.obj["quiet"] = quiet

    if verbose:
        os.environ["INVARIANT_LOG_LEVEL"] = "DEBUG"
    elif quiet:
        os.environ["INVARIANT_LOG_LEVEL"] = "ERROR"


main.add_command(run)
main.add_command(analyze)
main.add_command(report)


@main.command()
@click.argument("workflow_path")
def validate(workflow_path: str) -> None:
    """Validate a workflow definition file.

    Checks that the workflow YAML is structurally correct: no cycles,
    no missing node references, valid field types.

    \b
    Example:
        invariant validate examples/simple_pipeline.yaml
    """
    import sys

    from invariant.core.workflow import Workflow

    try:
        workflow = Workflow.from_yaml(workflow_path)
        workflow.validate()
        click.echo(f"[OK] Workflow '{workflow.metadata.name}' is valid.")
        click.echo(workflow.summary())
        sys.exit(0)
    except FileNotFoundError as exc:
        click.echo(f"[ERROR] {exc}", err=True)
        sys.exit(1)
    except Exception as exc:
        click.echo(f"[ERROR] Validation failed: {exc}", err=True)
        sys.exit(1)


@main.group()
def perturbations() -> None:
    """Commands for exploring available perturbation types."""


@perturbations.command(name="list")
def perturbations_list() -> None:
    """List all available perturbation types."""
    types = [
        ("LatencyPerturbation", "Inject a delay into node execution"),
        ("DropoutPerturbation", "Drop node inputs for one or more timesteps"),
        ("NoisePerturbation", "Add numeric noise to node outputs"),
        ("OverloadPerturbation", "Simulate a node exceeding its execution time budget"),
        ("CascadePerturbation", "Apply multiple perturbations simultaneously or in sequence"),
    ]
    click.echo("Available perturbation types:")
    for name, description in types:
        click.echo(f"  {name:<28} {description}")


@perturbations.command(name="describe")
@click.argument("perturbation_type")
def perturbations_describe(perturbation_type: str) -> None:
    """Show detailed description and parameters for a perturbation type.

    \b
    Example:
        invariant perturbations describe LatencyPerturbation
    """
    descriptions = {
        "LatencyPerturbation": (
            "Delays a node's virtual execution time.\n\n"
            "Modes: fixed (constant delay), uniform (random in [min_ms, max_ms]),\n"
            "       gaussian (mean=max_ms, std=std_ms)\n\n"
            "Parameters:\n"
            "  node_ids    Target node IDs (null = all nodes)\n"
            "  mode        Sampling mode: fixed | uniform | gaussian\n"
            "  delay_ms    Delay for fixed mode\n"
            "  min_ms      Lower bound for uniform mode\n"
            "  max_ms      Upper bound / mean for uniform / gaussian mode\n"
            "  std_ms      Standard deviation for gaussian mode\n"
            "  start_step  First simulation step to apply (default 0)\n"
            "  end_step    Last simulation step (null = indefinite)\n"
            "  seed        RNG seed for reproducibility"
        ),
        "DropoutPerturbation": (
            "Causes a node to receive no inputs for one or more timesteps.\n\n"
            "Modes: single (drop once), sustained (drop N steps), probabilistic\n\n"
            "Parameters:\n"
            "  node_ids         Target node IDs\n"
            "  mode             single | sustained | probabilistic\n"
            "  drop_step        Step to drop (single mode)\n"
            "  start_step       First step of sustained dropout\n"
            "  duration         Number of consecutive steps to drop\n"
            "  drop_probability Probability of dropping each step\n"
            "  seed             RNG seed"
        ),
        "NoisePerturbation": (
            "Adds numerical noise to a node's output values.\n\n"
            "Only affects numeric (int/float) output fields.\n\n"
            "Parameters:\n"
            "  node_ids     Target node IDs\n"
            "  distribution gaussian | uniform\n"
            "  magnitude    Noise standard deviation / half-width\n"
            "  start_step   First step\n"
            "  end_step     Last step (null = indefinite)\n"
            "  seed         RNG seed"
        ),
        "OverloadPerturbation": (
            "Simulates a node taking longer than its execution window.\n"
            "Advances the virtual clock by an extra random amount.\n\n"
            "Parameters:\n"
            "  node_ids         Target node IDs\n"
            "  min_overload_ms  Minimum extra delay\n"
            "  max_overload_ms  Maximum extra delay\n"
            "  start_step       First step\n"
            "  end_step         Last step (null = indefinite)\n"
            "  seed             RNG seed"
        ),
        "CascadePerturbation": (
            "Applies multiple perturbations together.\n\n"
            "Modes:\n"
            "  parallel   Apply all matching perturbations each step\n"
            "  sequential Round-robin through perturbations by timestep\n\n"
            "Parameters:\n"
            "  perturbations  List of perturbation configs\n"
            "  mode           parallel | sequential"
        ),
    }

    desc = descriptions.get(perturbation_type)
    if desc is None:
        click.echo(
            f"[ERROR] Unknown perturbation type '{perturbation_type}'. "
            "Run `invariant perturbations list` to see available types.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"{perturbation_type}\n{'=' * len(perturbation_type)}\n")
    click.echo(desc)
