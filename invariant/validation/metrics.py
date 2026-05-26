from typing import Any

from .base import ValidationResult


class StabilityMetrics:
    """Computes global stability scores based on validation results."""

    @staticmethod
    def compute_stability_score(results: list[ValidationResult]) -> float:
        """
        Computes a stability score from 0.0 to 1.0.
        Heuristic for v1: weighted average of pass statuses.
        """
        if not results:
            return 0.0

        weights = {
            "structural": 0.4,
            "temporal": 0.3,
            "behavioral": 0.3
        }

        score = 0.0
        total_weight = 0.0

        for res in results:
            weight = weights.get(res.validator_id, 0.1)
            if res.pass_status:
                score += weight
            total_weight += weight

        return score / total_weight if total_weight > 0 else 0.0

    @staticmethod
    def aggregate_metrics(results: list[ValidationResult]) -> dict[str, Any]:
        return {res.validator_id: res.metrics for res in results}
