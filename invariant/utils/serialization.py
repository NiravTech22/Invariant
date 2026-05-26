"""Serialization helpers: save and load workflows and results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file as a dict.

    Args:
        path: Path to the YAML file.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError: If the content is not a YAML mapping.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping, got {type(data).__name__}")
    return data


def save_yaml(data: dict[str, Any], path: str | Path) -> None:
    """Write a dict to a YAML file.

    Args:
        data: Data to serialize.
        path: Destination path.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        yaml.dump(data, fh, default_flow_style=False, sort_keys=False)


def load_json(path: str | Path) -> dict[str, Any]:
    """Load a JSON file as a dict.

    Args:
        path: Path to the JSON file.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(data: dict[str, Any], path: str | Path, indent: int = 2) -> None:
    """Write a dict to a JSON file.

    Args:
        data: Data to serialize.
        path: Destination path.
        indent: JSON indentation level.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=indent)
