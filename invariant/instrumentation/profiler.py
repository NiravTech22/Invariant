"""Profiler: aggregate timing statistics per node and edge across traces."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np

from invariant.instrumentation.tracer import ExecutionTrace


class NodeProfile:
    """Aggregated timing statistics for a single node across multiple traces.

    Attributes:
        node_id: The profiled node.
        durations_ms: Raw duration samples.
        mean_ms: Mean execution duration.
        std_ms: Standard deviation.
        min_ms: Minimum observed duration.
        max_ms: Maximum observed duration.
        p95_ms: 95th percentile duration.
        sample_count: Number of observations.
    """

    def __init__(self, node_id: str, durations_ms: list[float]) -> None:
        self.node_id = node_id
        self.durations_ms = durations_ms
        arr = np.array(durations_ms, dtype=float)
        self.mean_ms: float = float(np.mean(arr))
        self.std_ms: float = float(np.std(arr))
        self.min_ms: float = float(np.min(arr))
        self.max_ms: float = float(np.max(arr))
        self.p95_ms: float = float(np.percentile(arr, 95))
        self.sample_count: int = len(durations_ms)

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "mean_ms": self.mean_ms,
            "std_ms": self.std_ms,
            "min_ms": self.min_ms,
            "max_ms": self.max_ms,
            "p95_ms": self.p95_ms,
            "sample_count": self.sample_count,
        }


class WorkflowProfiler:
    """Compute per-node and per-edge timing profiles from a set of execution traces.

    Args:
        traces: List of ExecutionTrace objects to profile.

    Example::

        profiler = WorkflowProfiler(traces)
        profiles = profiler.node_profiles()
        for nid, profile in profiles.items():
            print(f"{nid}: mean={profile.mean_ms:.2f}ms")
    """

    def __init__(self, traces: list[ExecutionTrace]) -> None:
        self._traces = traces

    def node_profiles(self) -> dict[str, NodeProfile]:
        """Compute timing statistics for each node across all traces.

        Returns:
            Dict mapping node_id → NodeProfile.
        """
        durations: dict[str, list[float]] = defaultdict(list)
        for trace in self._traces:
            for record in trace.node_records:
                durations[record["node_id"]].append(record["duration_ms"])

        return {nid: NodeProfile(nid, durs) for nid, durs in durations.items()}

    def total_duration_stats(self) -> dict[str, float]:
        """Return stats on total workflow execution duration across traces."""
        totals = [t.get_total_duration_ms() for t in self._traces]
        arr = np.array(totals, dtype=float)
        return {
            "mean_ms": float(np.mean(arr)),
            "std_ms": float(np.std(arr)),
            "min_ms": float(np.min(arr)),
            "max_ms": float(np.max(arr)),
            "p95_ms": float(np.percentile(arr, 95)),
        }

    def bottleneck_nodes(self, top_n: int = 3) -> list[str]:
        """Return node IDs of the top-N slowest nodes by mean execution time.

        Args:
            top_n: How many nodes to return.

        Returns:
            Ordered list of node IDs (slowest first).
        """
        profiles = self.node_profiles()
        sorted_nodes = sorted(profiles.values(), key=lambda p: p.mean_ms, reverse=True)
        return [p.node_id for p in sorted_nodes[:top_n]]
