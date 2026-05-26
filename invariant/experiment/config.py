"""ExperimentConfig: Pydantic-validated experiment configuration schema."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import yaml
from pydantic import BaseModel, Field, field_validator


class PerturbationConfig(BaseModel):
    """Configuration for one perturbation in an experiment.

    Args:
        type: Perturbation class name (e.g. ``"LatencyPerturbation"``).
        node_ids: Target node IDs. ``None`` means all nodes.
        params: Perturbation-specific parameters. Passed as kwargs to the
            perturbation constructor.
        seed: RNG seed for reproducibility.
    """

    type: str = Field(..., description="Perturbation class name")
    node_ids: list[str] | None = Field(default=None)
    params: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = Field(default=None)


class ExperimentConfig(BaseModel):
    """Complete validated configuration for one experiment.

    A malformed config raises a ``ValidationError`` on construction —
    Invariant never silently runs with bad configuration.

    Args:
        name: Short experiment identifier (used in output directory names).
        workflow_path: Path to the YAML workflow definition file.
        num_perturbed_runs: Number of perturbed trials per perturbation config.
        perturbations: List of perturbation configs to apply.
        seed: Global random seed for reproducibility.
        output_dir: Where to write experiment output directories.
        divergence_threshold: Divergence threshold passed to analysis layer.
        description: Human-readable experiment description.
    """

    name: str = Field(..., min_length=1, description="Experiment identifier")
    workflow_path: str = Field(..., description="Path to workflow YAML")
    num_perturbed_runs: int = Field(default=5, ge=1)
    perturbations: list[PerturbationConfig] = Field(default_factory=list)
    seed: int = Field(default=42)
    output_dir: str = Field(default="experiments/output")
    divergence_threshold: float = Field(default=0.1, ge=0.0, le=1.0)
    description: str = Field(default="")

    @field_validator("workflow_path")
    @classmethod
    def workflow_must_exist(cls, v: str) -> str:
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Workflow file not found: {path}")
        return v

    @classmethod
    def from_yaml(cls, path: str | Path) -> ExperimentConfig:
        """Load and validate experiment config from a YAML file.

        Args:
            path: Path to the experiment config YAML.

        Raises:
            FileNotFoundError: If the config file does not exist.
            ValidationError: If the config is structurally invalid.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"Experiment config not found: {path}")
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        if not isinstance(data, dict):
            raise ValueError(f"Config file must be a YAML mapping, got {type(data).__name__}")
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict."""
        return cast(dict[str, Any], self.model_dump())
