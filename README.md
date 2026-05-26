# Invariant

A research framework for analyzing the stability, correctness, and failure modes of robotics software workflows — treating the entire stack as a system, not as isolated components.

---

## Why This Exists

Robotics research has excellent tools for perception, planning, and control. What is missing is a rigorous way to evaluate how these modules behave **when connected in a full pipeline**. Integration bugs, timing drift, and cascading failures typically surface late in development or only during hardware runs.

Invariant fills this gap. It represents workflows as explicit directed graphs, executes them deterministically with seeded perturbations, and measures stability, divergence, and failure propagation. The results are reproducible and publication-ready.

> **One question:** Is this robotics software stack actually stable when it runs as a system?

---

## Installation

```bash
pip install invariant-robotics          # PyPI (Python ≥ 3.10)
# or from source:
git clone https://github.com/niravtech22/invariant
cd invariant
pip install -e ".[dev]"
```

---

## Quick Start

### 1. Validate a workflow definition

```bash
invariant validate examples/simple_pipeline.yaml
# [OK] simple_pipeline — 3 nodes, 2 edges, no cycles
```

### 2. Run an experiment

```bash
invariant run examples/latency_sweep.yaml --output-dir results/
```

Output:

```
Running experiment: latency_sweep
  Baseline run complete
  Perturbed run 1/10 ...
  ...
Stability: STABLE  |  Mean divergence: 0.0023  |  Affected nodes: 1/3
Results saved → results/latency_sweep_20240101_120000/
```

### 3. List available perturbations

```bash
invariant perturbations list
# LatencyPerturbation   — inject virtual clock delays
# DropoutPerturbation   — drop node inputs with configurable probability
# NoisePerturbation     — add Gaussian/uniform noise to numeric outputs
# OverloadPerturbation  — simulate CPU overload via extended execution time
# CascadePerturbation   — compose multiple perturbations

invariant perturbations describe LatencyPerturbation
```

---

## Core Concepts

### Workflow Graph

A workflow is a directed acyclic graph (DAG) of nodes. Cycles are rejected at construction time.

```python
from invariant.core.graph import WorkflowGraph
from invariant.core.node import Node, NodeType, LatencyBounds
from invariant.core.edge import Edge
from invariant.core.workflow import Workflow, WorkflowMetadata

graph = WorkflowGraph()
perception = Node(node_id="perception", node_type=NodeType.PERCEPTION,
                  latency_bounds=LatencyBounds(min_ms=5, max_ms=15))
planner    = Node(node_id="planner",    node_type=NodeType.PLANNING,
                  latency_bounds=LatencyBounds(min_ms=10, max_ms=30))
controller = Node(node_id="controller", node_type=NodeType.CONTROL,
                  latency_bounds=LatencyBounds(min_ms=2, max_ms=8))

graph.add_node(perception)
graph.add_node(planner)
graph.add_node(controller)
graph.add_edge(Edge(source_id="perception", target_id="planner"))
graph.add_edge(Edge(source_id="planner",    target_id="controller"))

workflow = Workflow(metadata=WorkflowMetadata(name="arm_stack"), graph=graph)
```

### Deterministic Execution

The execution engine uses a **SimulatedClock** — no wall time, no `time.sleep`. The same workflow + perturbations + seed always produce byte-identical traces.

```python
from invariant.execution.executor import DeterministicExecutor
from invariant.perturbation.latency import LatencyPerturbation, LatencyMode

pert = LatencyPerturbation(node_ids={"planner"}, mode=LatencyMode.FIXED, delay_ms=50.0)
executor = DeterministicExecutor(workflow, perturbations=[pert])
trace = executor.run(seed=42)

print(trace.get_node_latencies())
# {'perception': 10.0, 'planner': 70.0, 'controller': 5.0}
```

### Analysis

```python
from invariant.execution.executor import DeterministicExecutor
from invariant.analysis.divergence import DivergenceAnalyzer
from invariant.analysis.stability import StabilityAnalyzer
from invariant.analysis.fault import FaultPropagationAnalyzer

baseline  = DeterministicExecutor(workflow).run()
perturbed = [DeterministicExecutor(workflow, [pert]).run(timestep=i) for i in range(20)]

div  = DivergenceAnalyzer(baseline, perturbed).analyze()
stab = StabilityAnalyzer(baseline, perturbed).analyze()
fp   = FaultPropagationAnalyzer(graph, baseline, perturbed, "planner").analyze()

print(stab.stability_class)   # StabilityClass.STABLE
print(fp.impacted_nodes)      # {'planner', 'controller'}
```

### Experiment Runner

```python
from invariant.experiment.config import ExperimentConfig
from invariant.experiment.runner import ExperimentRunner

config = ExperimentConfig.from_yaml("examples/latency_sweep.yaml")
result = ExperimentRunner(config).run()

print(result.report(format="markdown"))
result.save("results/")
```

---

## Architecture

```
invariant/
├── core/          Node, Edge, WorkflowGraph, Workflow — pure data model
├── execution/     SimulatedClock, ExecutionContext, DeterministicExecutor
├── perturbation/  BasePerturbation, Latency, Dropout, Noise, Overload, Cascade
├── analysis/      Divergence, Stability, FaultPropagation, Sensitivity
├── instrumentation/ ExecutionTrace, WorkflowProfiler, ExperimentRecorder
├── experiment/    ExperimentConfig, ExperimentRunner, ReportGenerator, Suite
├── adapters/      MockAdapter (built-in), ROS2Adapter (optional)
├── cli/           invariant run | validate | perturbations | analyze
└── utils/         logging, serialization, validation
```

**Key invariants:**

| Invariant | Enforcement |
|-----------|-------------|
| Determinism | SimulatedClock only; seeded RNGs per perturbation instance |
| No hardware deps in core | `rclpy` imports gated behind `try/except`; only `adapters/` may touch hardware |
| Fail loudly | `ExecutionError`, `CycleDetectedError`, Pydantic validators — never swallow exceptions |
| Measurable divergence | `start_ms` recorded **before** perturbation-induced clock advance |

---

## Workflow YAML Format

```yaml
# examples/simple_pipeline.yaml
metadata:
  name: simple_pipeline
  description: Three-node perception → planner → controller stack

nodes:
  - id: perception
    type: perception
    latency_min_ms: 5.0
    latency_max_ms: 15.0
  - id: planner
    type: planning
    latency_min_ms: 10.0
    latency_max_ms: 30.0
  - id: controller
    type: control
    latency_min_ms: 2.0
    latency_max_ms: 8.0

edges:
  - source: perception
    target: planner
  - source: planner
    target: controller
```

---

## Experiment Config YAML

```yaml
# examples/latency_sweep.yaml
name: latency_sweep
workflow_path: examples/simple_pipeline.yaml
num_perturbed_runs: 10
seed: 42
output_dir: results/

perturbations:
  - type: LatencyPerturbation
    node_ids: [planner]
    params:
      mode: fixed
      delay_ms: 50.0
    seed: 42
```

---

## Mock Adapter

For testing without hardware, the `MockAdapter` builds fully functional pipelines:

```python
from invariant.adapters.mock import (
    MockAdapter, MockPerceptionNode, MockPlannerNode, MockControllerNode
)

adapter  = MockAdapter("my_test")
workflow = adapter.build_linear_pipeline(
    MockPerceptionNode(seed=1),
    MockPlannerNode(seed=2),
    MockControllerNode(seed=3),
)
```

---

## Testing

```bash
pytest tests/ -v --cov=invariant --cov-report=term-missing
# 159 passed, 2 skipped — 86% coverage
```

Coverage excludes legacy FlowGuard modules (see `pyproject.toml` → `[tool.coverage.run] omit`).

---

## Design Constraints

- **No wall-clock time** — `SimulatedClock` is the only clock in the execution engine
- **No `time.sleep`** anywhere in `invariant/` (except adapter shims)
- **Seeded RNGs** — every perturbation carries its own `random.Random(seed)` instance
- **Pydantic validation** — workflow and experiment configs fail loudly on bad input
- **DAG enforcement** — `WorkflowGraph.add_edge()` raises `CycleDetectedError` immediately

---

## Reference

H. Araujo, M. R. Mousavi, and M. Varshosaz, "Testing, Validation, and Verification of Robotic and Autonomous Systems: A Systematic Review," *ACM Transactions on Software Engineering and Methodology*, vol. 32, no. 2, pp. 51:1–51:61, 2023. [DOI: 10.1145/3542945](https://doi.org/10.1145/3542945)
