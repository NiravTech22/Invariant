"""Bounded exponential backoff for the network calls this agent makes.

Only transient faults are retried. A bug, a bad argument or an auth failure
re-raises immediately -- retrying those just delays the error report.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, TypeVar

T = TypeVar("T")

DEFAULT_ATTEMPTS = 4
DEFAULT_BASE_DELAY = 1.0
DEFAULT_MAX_DELAY = 16.0

# HTTP statuses worth a second try: rate limiting and server-side faults.
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


def _status_of(exc: BaseException) -> int | None:
    """Pull an HTTP status off an exception, whatever library raised it."""
    for attr in ("status_code", "status"):
        value = getattr(exc, attr, None)
        if isinstance(value, int):
            return value
    # googleapiclient.errors.HttpError keeps it on .resp.status
    resp = getattr(exc, "resp", None)
    status = getattr(resp, "status", None)
    return status if isinstance(status, int) else None


def is_transient(exc: BaseException) -> bool:
    """True when `exc` is worth retrying."""
    if isinstance(exc, (ConnectionError, TimeoutError, OSError)):
        return True

    status = _status_of(exc)
    if status is not None:
        return status in RETRYABLE_STATUS

    # ollama raises its own ResponseError; fall back to the message text.
    text = str(exc).lower()
    return any(
        marker in text
        for marker in ("timed out", "timeout", "connection reset", "temporarily unavailable")
    )


def call_with_retry(
    func: Callable[..., T],
    *args: Any,
    attempts: int = DEFAULT_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY,
    max_delay: float = DEFAULT_MAX_DELAY,
    sleep: Callable[[float], None] = time.sleep,
    on_retry: Callable[[int, float, BaseException], None] | None = None,
    retryable: Callable[[BaseException], bool] = is_transient,
    **kwargs: Any,
) -> T:
    """Call `func`, retrying transient failures with exponential backoff.

    Delays double from `base_delay`, capped at `max_delay`: 1s, 2s, 4s, 8s.
    The final failure is re-raised unchanged so the caller sees the real
    exception rather than a wrapper.
    """
    if attempts < 1:
        raise ValueError("attempts must be at least 1")

    last: BaseException
    for attempt in range(1, attempts + 1):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            last = exc
            if attempt == attempts or not retryable(exc):
                raise
            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if on_retry is not None:
                on_retry(attempt, delay, exc)
            sleep(delay)

    raise last  # pragma: no cover -- loop always returns or raises above


def retry_iter(items: Iterable[T]) -> list[T]:  # pragma: no cover - convenience
    """Materialise an iterable so a retried call cannot return a spent iterator."""
    return list(items)
