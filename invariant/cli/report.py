"""CLI `invariant report` command."""

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
    help="Report format to generate",
)
@click.option("--output", default=None, help="Output file path (default: <experiment_dir>/report.<fmt>)")
@click.pass_context
def report(
    ctx: click.Context,
    experiment_dir: str,
    output_format: str,
    output: str | None,
) -> None:
    """Generate a report from an existing experiment directory.

    EXPERIMENT_DIR must contain a baseline.json and at least one run_NNN.json.

    \b
    Examples:
        invariant report experiments/output/latency_sweep_20240601/
        invariant report experiments/output/my_exp/ --format latex --output paper_table.tex
    """
    # Delegate to the analyze command's logic
    from invariant.cli.analyze import analyze as analyze_cmd

    ctx.invoke(
        analyze_cmd,
        experiment_dir=experiment_dir,
        output_format=output_format,
        output=output,
    )
