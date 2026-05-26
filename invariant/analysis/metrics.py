"""Core metric definitions and collection from execution traces."""

from __future__ import annotations

from typing import Any

import numpy as np

from invariant.instrumentation.tracer import ExecutionTrace


class TraceMetrics:
    """Extract standard metrics from a collection of execution traces.

    All metrics are computed lazily and cached. Inputs are immutable
    after construction.

    Args:
        traces: Non-empty list of ExecutionTrace objects.

    Raises:
        ValueError: If traces list is empty.
    """

    def __init__(self, traces: list[ExecutionTrace]) -> None:
        if not traces:
            raise ValueError("TraceMetrics requires at least one trace")
        self._traces = traces
        self._node_ids: list[str] = self._collect_node_ids()

    def _collect_node_ids(self) -> list[str]:
        """Return the union of all node IDs across traces."""
        ids: list[str] = []
        seen: set[str] = set()
        for trace in self._traces:
            for record in trace.node_records:
                nid = record["node_id"]
                if nid not in seen:
                    ids.append(nid)
                    seen.add(nid)
        return ids

    @property
    def node_ids(self) -> list[str]:
        """All node IDs observed across the trace set."""
        return list(self._node_ids)

    def mean_latency(self) -> dict[str, float]:
        """Mean execution duration per node in ms."""
        return self._per_node_stat(np.mean)

    def std_latency(self) -> dict[str, float]:
        """Standard deviation of execution duration per node in ms."""
        return self._per_node_stat(np.std)

    def max_latency(self) -> dict[str, float]:
        """Maximum execution duration per node in ms."""
        return self._per_node_stat(np.max)

    def coefficient_of_variation(self) -> dict[str, float]:
        """Coefficient of variation (std/mean) per node; 0 if mean ≈ 0."""
        means = self.mean_latency()
        stds = self.std_latency()
        return {
            nid: (stds[nid] / means[nid]) if means[nid] > 1e-9 else 0.0
            for nid in self._node_ids
            if nid in means
        }

    def dropout_rate(self) -> dict[str, float]:
        """Fraction of traces in which each node was dropped."""
        drop_counts: dict[str, int] = {nid: 0 for nid in self._node_ids}
        presence: dict[str, int] = {nid: 0 for nid in self._node_ids}

        for trace in self._traces:
            for record in trace.node_records:
                nid = record["node_id"]
                presence[nid] = presence.get(nid, 0) + 1
                if record["dropped"]:
                    drop_counts[nid] = drop_counts.get(nid, 0) + 1

        return {
            nid: (drop_counts.get(nid, 0) / presence[nid]) if presence.get(nid, 0) else 0.0
            for nid in self._node_ids
        }

    def total_duration_stats(self) -> dict[str, float]:
        """Statistics on total workflow execution duration in ms."""
        totals = [t.get_total_duration_ms() for t in self._traces]
        arr = np.array(totals, dtype=float)
        return {
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "p95": float(np.percentile(arr, 95)),
        }

    def to_dict(self) -> dict[str, Any]:
        """Return all metrics as a serializable dict."""
        return {
            "mean_latency_ms": self.mean_latency(),
            "std_latency_ms": self.std_latency(),
            "max_latency_ms": self.max_latency(),
            "coefficient_of_variation": self.coefficient_of_variation(),
            "dropout_rate": self.dropout_rate(),
            "total_duration": self.total_duration_stats(),
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _per_node_stat(self, fn: Any) -> dict[str, float]:
        from collections import defaultdict

        buckets: dict[str, list[float]] = defaultdict(list)
        for trace in self._traces:
            for record in trace.node_records:
                buckets[record["node_id"]].append(record["duration_ms"])
        return {nid: float(fn(np.array(vals))) for nid, vals in buckets.items()}
