"""SimulatedClock: discrete virtual clock for deterministic execution timing.

This clock never uses wall time or time.sleep. All time values are in
milliseconds. The clock can be advanced by perturbations to inject delays
into the virtual timeline.
"""

from __future__ import annotations

from typing import Any


class SimulatedClock:
    """A discrete virtual clock for deterministic experiment timing.

    The clock starts at ``initial_time_ms`` and advances only through
    explicit :meth:`advance` calls. This guarantees that two experiments
    run with the same perturbations and seed produce identical timestamps.

    No wall-clock time is ever observed or used.

    Args:
        initial_time_ms: Starting time value in milliseconds.

    Typical usage::

        clock = SimulatedClock(initial_time_ms=0.0)
        t0 = clock.now()
        clock.advance(5.0)   # inject 5 ms delay
        t1 = clock.now()     # t1 == 5.0
    """

    def __init__(self, initial_time_ms: float = 0.0) -> None:
        self._time_ms: float = initial_time_ms
        self._events: list[dict[str, Any]] = []

    def now(self) -> float:
        """Return the current virtual time in milliseconds."""
        return self._time_ms

    def advance(self, delta_ms: float) -> None:
        """Advance the clock by ``delta_ms`` milliseconds.

        Args:
            delta_ms: Time increment in milliseconds. Must be non-negative.

        Raises:
            ValueError: If delta_ms is negative (time cannot go backwards).
        """
        if delta_ms < 0:
            raise ValueError(
                f"Cannot advance clock by negative delta ({delta_ms} ms); "
                "time does not flow backwards"
            )
        self._time_ms += delta_ms

    def record_event(self, label: str, extra: dict[str, Any] | None = None) -> None:
        """Record a timestamped event on the clock's event log.

        Args:
            label: Short description of the event.
            extra: Optional extra key-value context.
        """
        self._events.append({"time_ms": self._time_ms, "label": label, **(extra or {})})

    @property
    def events(self) -> list[dict[str, Any]]:
        """All recorded events in chronological order."""
        return list(self._events)

    def reset(self, initial_time_ms: float = 0.0) -> None:
        """Reset the clock to a new starting time and clear event log.

        Args:
            initial_time_ms: New starting time in milliseconds.
        """
        self._time_ms = initial_time_ms
        self._events.clear()

    def __repr__(self) -> str:
        return f"SimulatedClock(now={self._time_ms:.3f} ms)"
