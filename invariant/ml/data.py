
import torch

from ..execution.signals import WorkflowExecutionTrace
from ..workflow.graph import WorkflowGraph
from .features import AggregatedFeatureExtractor


class ReplayDataGenerator:
    """Generates synthetic training data from validation runs."""

    def __init__(self, extractor: AggregatedFeatureExtractor):
        self.extractor = extractor

    def generate_sample(self, graph: WorkflowGraph, traces: list[WorkflowExecutionTrace], stability_score: float) -> tuple[torch.Tensor, torch.Tensor]:
        features = self.extractor.extract(graph, traces)
        # Failure label is 1.0 if stability score is low
        label = 1.0 if stability_score < 0.7 else 0.0

        return torch.from_numpy(features), torch.tensor([label], dtype=torch.float32)
