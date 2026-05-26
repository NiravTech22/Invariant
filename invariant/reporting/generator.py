import json
from typing import Any

from ..validation.base import ValidationResult


class ReportGenerator:
    """Generates structured stability reports in Markdown and JSON."""

    def generate_markdown(
        self, results: list[ValidationResult], stability_score: float, run_info: dict[str, Any]
    ) -> str:
        report = []
        report.append("# Invariant Stability Report")
        report.append(f"**Run ID:** {run_info.get('run_id')}")
        report.append(f"**Timestamp:** {run_info.get('timestamp')}")
        report.append(f"\n## Overall Stability Score: `{stability_score:.2f}`")

        status_emoji = "✅" if stability_score > 0.8 else "⚠️" if stability_score > 0.5 else "❌"
        report.append(f"**Status:** {status_emoji}")

        report.append("\n## Validation Phases")
        for res in results:
            pass_mark = "PASS" if res.pass_status else "FAIL"
            report.append(f"### {res.validator_id.capitalize()}: {pass_mark}")
            report.append(f"- **Message:** {res.message}")
            if res.metrics:
                report.append("- **Details:** See JSON data")

        return "\n".join(report)

    def generate_json(
        self, results: list[ValidationResult], stability_score: float, run_info: dict[str, Any]
    ) -> str:
        data = {
            "run_info": run_info,
            "stability_score": stability_score,
            "results": [
                {
                    "validator_id": r.validator_id,
                    "pass": r.pass_status,
                    "message": r.message,
                    "metrics": r.metrics,
                }
                for r in results
            ],
        }
        return json.dumps(data, indent=2)
