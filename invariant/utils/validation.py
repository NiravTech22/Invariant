"""Input validation utilities used across Invariant boundaries."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def require_non_empty_string(value: Any, name: str) -> str:
    """Assert that value is a non-empty string.

    Args:
        value: Value to check.
        name: Parameter name for error messages.

    Raises:
        TypeError: If value is not a string.
        ValueError: If value is empty or whitespace-only.
    """
    if not isinstance(value, str):
        raise TypeError(f"'{name}' must be a str, got {type(value).__name__}")
    if not value.strip():
        raise ValueError(f"'{name}' must not be empty")
    return value


def require_positive(value: Any, name: str) -> float:
    """Assert that value is a positive number.

    Args:
        value: Value to check.
        name: Parameter name for error messages.

    Raises:
        TypeError: If value is not numeric.
        ValueError: If value is not positive.
    """
    if not isinstance(value, (int, float)):
        raise TypeError(f"'{name}' must be numeric, got {type(value).__name__}")
    if value <= 0:
        raise ValueError(f"'{name}' must be positive, got {value}")
    return float(value)


def require_non_negative(value: Any, name: str) -> float:
    """Assert that value is >= 0.

    Args:
        value: Value to check.
        name: Parameter name for error messages.

    Raises:
        TypeError: If value is not numeric.
        ValueError: If value is negative.
    """
    if not isinstance(value, (int, float)):
        raise TypeError(f"'{name}' must be numeric, got {type(value).__name__}")
    if value < 0:
        raise ValueError(f"'{name}' must be non-negative, got {value}")
    return float(value)


def require_file_exists(path: str | Path, name: str = "path") -> Path:
    """Assert that a file exists at path.

    Args:
        path: Path to check.
        name: Parameter name for error messages.

    Raises:
        FileNotFoundError: If the file does not exist.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found for '{name}': {p}")
    return p


def require_in_range(value: float, lo: float, hi: float, name: str) -> float:
    """Assert that value is in [lo, hi].

    Args:
        value: Value to check.
        lo: Inclusive lower bound.
        hi: Inclusive upper bound.
        name: Parameter name for error messages.

    Raises:
        ValueError: If value is outside [lo, hi].
    """
    if not lo <= value <= hi:
        raise ValueError(f"'{name}' must be in [{lo}, {hi}], got {value}")
    return value
