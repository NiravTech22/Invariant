import random
from dataclasses import dataclass


@dataclass
class PerturbationModel:
    """Declarative perturbation model."""

    latency_min_ms: float = 0
    latency_max_ms: float = 0
    jitter_ms: float = 0
    drop_probability: float = 0
    seed: int | None = None


class SeededPerturbator:
    """Injects seeded, reproducible perturbations into node execution."""

    def __init__(self, model: PerturbationModel):
        self.model = model
        self.rng = random.Random(model.seed)

    def get_latency_injection(self) -> float:
        """Returns latency to inject in seconds."""
        base_latency = self.rng.uniform(self.model.latency_min_ms, self.model.latency_max_ms)
        jitter = self.rng.uniform(-self.model.jitter_ms, self.model.jitter_ms)
        return max(0, (base_latency + jitter) / 1000.0)

    def should_drop(self) -> bool:
        """Determines if a message/execution should be dropped."""
        return self.rng.random() < self.model.drop_probability
