"""ReportGenerator: produce Markdown, JSON, CSV, and LaTeX reports from ExperimentResult."""

from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from invariant.experiment.runner import ExperimentResult


class ReportGenerator:
    """Generate experiment reports in multiple formats.

    All format methods accept an ExperimentResult and return a string.
    """

    # ------------------------------------------------------------------
    # Markdown
    # ------------------------------------------------------------------

    def markdown(self, result: "ExperimentResult") -> str:
        """Generate a human-readable Markdown report.

        Args:
            result: The experiment result to report on.

        Returns:
            Markdown-formatted string.
        """
        lines: list[str] = []
        cfg = result.config
        stab = result.stability
        metrics = result.metrics.to_dict()

        lines.append("# Invariant Experiment Report")
        lines.append("")
        lines.append(f"**Experiment:** {cfg.name}")
        lines.append(f"**Generated:** {datetime.now(tz=timezone.utc).isoformat()}")
        lines.append(f"**Workflow:** {cfg.workflow_path}")
        lines.append(f"**Perturbed runs:** {len(result.perturbed_runs)}")
        lines.append("")

        # Perturbations
        lines.append("## Perturbations Applied")
        if cfg.perturbations:
            for p in cfg.perturbations:
                lines.append(f"- **{p.type}**: nodes={p.node_ids or 'all'}, params={p.params}")
        else:
            lines.append("- None (baseline only)")
        lines.append("")

        # Stability
        stab_label = {
            "stable": "STABLE",
            "marginally_stable": "MARGINALLY STABLE",
            "unstable": "UNSTABLE",
        }.get(stab.classification.value, stab.classification.value.upper())
        lines.append("## Stability Assessment")
        lines.append(f"**Classification:** `{stab_label}`")
        lines.append(f"**Peak divergence:** {stab.peak_divergence:.4f}")
        recovery = str(stab.recovery_steps) if stab.recovery_steps is not None else "not observed"
        lines.append(f"**Recovery (runs):** {recovery}")
        lines.append("")

        # Per-node stability
        lines.append("### Per-Node Stability")
        lines.append("| Node | Classification |")
        lines.append("|------|---------------|")
        for nid, cls in stab.node_classifications.items():
            lines.append(f"| {nid} | {cls.value} |")
        lines.append("")

        # Divergence table
        lines.append("## Divergence Summary")
        lines.append("| Node | Mean Latency (ms) | Std (ms) | CV | Dropout Rate |")
        lines.append("|------|-------------------|----------|----|--------------|")
        for nid in metrics.get("mean_latency_ms", {}).keys():
            mean = metrics["mean_latency_ms"].get(nid, 0.0)
            std = metrics["std_latency_ms"].get(nid, 0.0)
            cv = metrics["coefficient_of_variation"].get(nid, 0.0)
            dr = metrics["dropout_rate"].get(nid, 0.0)
            lines.append(f"| {nid} | {mean:.2f} | {std:.2f} | {cv:.3f} | {dr:.3f} |")
        lines.append("")

        # Key findings
        lines.append("## Key Findings")
        lines.append(
            f"- The workflow was classified as **{stab_label}** under the applied perturbations."
        )
        if stab.peak_divergence > cfg.divergence_threshold:
            lines.append(
                f"- Peak divergence of **{stab.peak_divergence:.4f}** exceeded the "
                f"threshold of **{cfg.divergence_threshold}**."
            )
        if stab.recovery_steps is not None:
            lines.append(
                f"- The system recovered within **{stab.recovery_steps}** perturbed run(s)."
            )
        else:
            lines.append("- No full recovery was observed within the experiment window.")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # JSON
    # ------------------------------------------------------------------

    def json(self, result: "ExperimentResult") -> str:  # noqa: A003
        """Generate a full structured JSON report.

        Args:
            result: The experiment result.

        Returns:
            JSON string with complete results.
        """
        data: dict[str, Any] = {
            "experiment": result.to_dict(),
            "stability": result.stability.to_dict(),
            "metrics": result.metrics.to_dict(),
            "baseline": result.baseline.to_dict(),
            "perturbed_runs": [t.to_dict() for t in result.perturbed_runs],
        }
        return json.dumps(data, indent=2)

    # ------------------------------------------------------------------
    # CSV
    # ------------------------------------------------------------------

    def csv(self, result: "ExperimentResult") -> str:  # noqa: A003
        """Generate a machine-readable CSV report.

        One row per (run_label, node_id): containing timing, health, and
        divergence metrics. Suitable for R, Python, or MATLAB analysis.

        Args:
            result: The experiment result.

        Returns:
            CSV-formatted string.
        """
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "run_label", "node_id", "timestep", "start_ms", "end_ms",
            "duration_ms", "health", "dropped", "perturbations",
        ])

        for record in result.baseline.node_records:
            writer.writerow([
                "baseline",
                record["node_id"],
                record["timestep"],
                record["start_ms"],
                record["end_ms"],
                record["duration_ms"],
                record["health"],
                record["dropped"],
                "",
            ])

        for i, trace in enumerate(result.perturbed_runs, start=1):
            for record in trace.node_records:
                writer.writerow([
                    f"run_{i:03d}",
                    record["node_id"],
                    record["timestep"],
                    record["start_ms"],
                    record["end_ms"],
                    record["duration_ms"],
                    record["health"],
                    record["dropped"],
                    "|".join(record.get("perturbations_applied", [])),
                ])

        return buf.getvalue()

    # ------------------------------------------------------------------
    # LaTeX
    # ------------------------------------------------------------------

    def latex(self, result: "ExperimentResult") -> str:
        """Generate a LaTeX table ready for inclusion in a paper.

        Produces an IEEE/ACM-style table with columns: perturbation type,
        magnitude, stability class, peak divergence, and recovery time.

        Args:
            result: The experiment result.

        Returns:
            LaTeX tabular environment as a string.
        """
        stab = result.stability
        lines: list[str] = []

        lines.append("% Invariant Experiment Table")
        lines.append("% Generated by Invariant report generator")
        lines.append(r"\begin{table}[ht]")
        lines.append(r"  \centering")
        lines.append(f"  \\caption{{Stability Analysis: {result.config.name}}}")
        lines.append(r"  \label{tab:invariant-stability}")
        lines.append(r"  \begin{tabular}{llccc}")
        lines.append(r"    \toprule")
        lines.append(r"    \textbf{Perturbation} & \textbf{Nodes} & "
                     r"\textbf{Stability} & \textbf{Peak Div.} & \textbf{Recovery} \\")
        lines.append(r"    \midrule")

        for pc in result.config.perturbations:
            nodes_str = ", ".join(pc.node_ids) if pc.node_ids else "all"
            stab_str = stab.classification.value.replace("_", " ").title()
            peak_str = f"{stab.peak_divergence:.4f}"
            rec_str = str(stab.recovery_steps) if stab.recovery_steps is not None else "N/A"
            lines.append(
                f"    {pc.type} & {nodes_str} & {stab_str} & {peak_str} & {rec_str} \\\\"
            )

        if not result.config.perturbations:
            lines.append(r"    (baseline) & — & Stable & 0.0000 & N/A \\")

        lines.append(r"    \bottomrule")
        lines.append(r"  \end{tabular}")
        lines.append(r"\end{table}")

        return "\n".join(lines)
