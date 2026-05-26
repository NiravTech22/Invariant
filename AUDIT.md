# Invariant — Pre-Refactor Audit Report

**Audit Date:** 2026-05-26  
**Auditor:** Senior Robotics Software Engineer  
**Repository:** NiravTech22/Invariant  

---

## 1. Repository Inventory

| File | What It Does | State | Belongs in Final Architecture |
|------|-------------|-------|------------------------------|
| `invariant/core/engine.py` | FlowGuard SafetySupervisor — runtime safety filter for velocity/action commands | Working (FlowGuard, not Invariant) | No — wrong project |
| `invariant/core/interfaces.py` | Abstract SafetyValidator interface for FlowGuard | Working | No — wrong project |
| `invariant/core/types.py` | SystemState, ProposedAction, SafetyMode Pydantic models for FlowGuard | Working | No — wrong project |
| `invariant/core/outcome.py` | SafetyOutcome, Decision, Violation for FlowGuard | Working | No — wrong project |
| `invariant/core/config.py` | ExperimentConfig: run ID, timestamp, config hash | Working | Yes — keep and migrate |
| `invariant/execution/engine.py` | DeterministicEngine: runs workflow in topological order, simulated clock, seeded perturbations | Working | Yes — keep and expand |
| `invariant/execution/perturbation.py` | PerturbationModel (dataclass) + SeededPerturbator (latency + dropout) | Working | Yes — keep and expand |
| `invariant/execution/scheduler.py` | TopologicalScheduler: wraps nx.topological_sort | Working | Yes — keep |
| `invariant/execution/signals.py` | ExecutionSignal + WorkflowExecutionTrace dataclasses | Working | Yes — keep and expand |
| `invariant/execution/ros_runner.py` | ROSEngine: monitors live ROS 2 system; populates trace from spin loop | Incomplete (no actual message capture) | Yes — migrate to adapters/ros2.py |
| `invariant/workflow/graph.py` | WorkflowGraph: nx.DiGraph with DAG enforcement, topological sort, invariant exposure | Working | Yes — keep and expand |
| `invariant/workflow/node.py` | Node, Port, PortType, NodeConstraints dataclasses | Working | Yes — keep and expand |
| `invariant/workflow/loader.py` | WorkflowLoader: YAML/JSON → WorkflowGraph | Working | Yes — keep and expand |
| `invariant/workflow/registry.py` | NodeRegistry: template-based node factory | Working | Yes — migrate to adapters/mock.py |
| `invariant/validation/base.py` | ValidationResult + BaseValidator ABC | Working | Yes — keep (becomes analysis/base.py) |
| `invariant/validation/structural.py` | StructuralValidator: checks DAG, empty graph | Working | Yes — keep |
| `invariant/validation/temporal.py` | TemporalValidator: checks latency constraints per trace | Working | Yes — keep |
| `invariant/validation/behavioral.py` | BehavioralValidator: variance/CV analysis across traces | Working | Yes — keep |
| `invariant/validation/metrics.py` | StabilityMetrics: weighted stability score from ValidationResults | Working | Yes — keep |
| `invariant/validators/physical.py` | PhysicalConstraintValidator: velocity limit checker for FlowGuard | Working (FlowGuard) | No — wrong project |
| `invariant/validators/policy.py` | GeofenceValidator: spatial bounds checker for FlowGuard | Working (FlowGuard) | No — wrong project |
| `invariant/validators/uncertainty.py` | UncertaintyValidator: sensor health checker for FlowGuard | Working (FlowGuard) | No — wrong project |
| `invariant/ml/supervisor.py` | MLPSupervisor + GNNSupervisor: PyTorch neural nets for failure prediction | Working (heavy dep) | No — out of scope for research framework |
| `invariant/ml/features.py` | AggregatedFeatureExtractor: graph + temporal feature vector | Working | No — supplanted by analysis layer |
| `invariant/ml/data.py` | ReplayDataGenerator: creates training samples from traces | Working | No — out of scope |
| `invariant/reporting/generator.py` | ReportGenerator: Markdown + JSON report from ValidationResults | Working | Yes — keep and expand |
| `invariant/ros/bridge.py` | ActiveBridge: rclpy-based ROS 2 graph introspection | Working (conditional) | Yes — migrate to adapters/ros2.py |
| `invariant/telemetry/client.py` | TelemetryBridge: HTTP POST to FlowGuard backend | Working (FlowGuard) | No — wrong project |
| `invariant/cli.py` | CLI: `validate` and `monitor` commands | Working | Yes — rewrite as cli/ package |
| `backend/` | FastAPI FlowGuard telemetry server | Working (separate service) | No — separate project |
| `examples/simple_workflow.yaml` | Three-node perception→planning→control workflow YAML | Working | Yes — keep |
| `examples/simple_loop.py` | FlowGuard demo loop (imports non-existent `flowguard` module) | Broken | No — replace with Invariant demo |
| `tests/test_mock_ros.py` | ROS integration test with mocked rclpy | Working | Yes — keep and expand |
| `verify_determinism.py` | Script: runs same workflow twice, asserts identical traces | Working | Yes — convert to pytest test |
| `verify_ml.py` | Script: runs ML training loop with PyTorch | Working | No — PyTorch out of scope |
| `stability_report.md` | Output artifact from a previous CLI run | N/A | No — generated artifact |
| `pyproject.toml` | Root package config: `invariant`, Python ≥3.8, includes torch | Incomplete | Yes — rewrite |
| `backend/pyproject.toml` | Backend package config | Separate | No |
| `backend/scripts/invariant_check.sh` | Lint/type/test CI script (has syntax bug: `mypy backend--ignore`) | Broken | Yes — replace with CI YAML |
| `README.md` | Project overview with Mermaid diagram | Mostly good, mentions ML prominently | Yes — rewrite |

---

## 2. Core Identification

### What Currently Works

| Component | Location | Status | Notes |
|-----------|----------|--------|-------|
| Workflow graph (DAG) | `invariant/workflow/graph.py` | ✅ Working | Uses networkx, DAG-enforced on edge add |
| Workflow loader (YAML) | `invariant/workflow/loader.py` | ✅ Working | Parses nodes, edges, ports, constraints |
| Topological scheduler | `invariant/execution/scheduler.py` | ✅ Working | Thin wrapper around nx.topological_sort |
| Deterministic executor | `invariant/execution/engine.py` | ✅ Working | Virtual clock, seeded perturbations |
| Latency + dropout perturbation | `invariant/execution/perturbation.py` | ✅ Working | Seeded RNG, configurable params |
| Execution trace | `invariant/execution/signals.py` | ✅ Working | Per-node signal capture |
| Structural validator | `invariant/validation/structural.py` | ✅ Working | DAG check, empty graph check |
| Temporal validator | `invariant/validation/temporal.py` | ✅ Working | Per-node latency vs. constraint |
| Behavioral validator | `invariant/validation/behavioral.py` | ✅ Working | Variance/CV across traces |
| Stability scoring | `invariant/validation/metrics.py` | ✅ Working | Weighted score, 0.0–1.0 |
| Report generator | `invariant/reporting/generator.py` | ✅ Working | Markdown + JSON |
| ROS 2 bridge | `invariant/ros/bridge.py` | ✅ Conditional | Gracefully degrades without rclpy |
| Experiment config | `invariant/core/config.py` | ✅ Working | UUID, timestamp, config hash |
| Determinism guarantee | `verify_determinism.py` | ✅ Verified | Same seed → same trace, confirmed |

---

## 3. Technical Debt

### 3.1 Identity Crisis (Critical)
The repository conflates **two different projects**: 
- **Invariant** (the workflow analysis framework)
- **FlowGuard** (a runtime safety supervisor for live robot commands)

The `core/` directory, `validators/` directory, and `telemetry/` module all belong to FlowGuard. The `examples/simple_loop.py` imports from a non-existent `flowguard` package. The `backend/` is a FlowGuard telemetry server. These must be removed from the Invariant package.

### 3.2 Missing `__init__.py` Files
No `__init__.py` files exist anywhere in the `invariant/` package tree, making the package non-importable without path manipulation. All subpackages are missing their module declarations.

### 3.3 Duplicate/Misplaced Logic
- `core/engine.py` (SafetySupervisor) and `execution/engine.py` (DeterministicEngine) are two completely different engines with the same filename — confusion guaranteed
- `validators/` (FlowGuard) and `validation/` (Invariant) serve different purposes but the naming implies they are parallel

### 3.4 Dead Code
- `invariant/validators/` — FlowGuard validators, never called from Invariant paths
- `invariant/core/engine.py`, `interfaces.py`, `types.py`, `outcome.py` — FlowGuard core, never used by workflow analysis
- `invariant/telemetry/client.py` — FlowGuard telemetry, never used
- `invariant/ml/` — PyTorch MLP, out of scope; `GNNSupervisor.predict` always returns `0.5`
- `examples/simple_loop.py` — imports `flowguard`, which does not exist

### 3.5 Hardcoded Values
- `execution/engine.py` line 46: `self.virtual_time += 0.001` — baseline node execution time is hardcoded to 1ms; not a node property
- `validation/behavioral.py` line 37: `if cv > 0.5` — instability threshold hardcoded, not configurable
- `validation/metrics.py` weights dict — fixed weights for structural/temporal/behavioral validators
- `reporting/generator.py` score thresholds `0.8` / `0.5` — report status thresholds hardcoded

### 3.6 Missing Error Handling
- `workflow/graph.py:get_node` raises bare `KeyError` if node not found
- `workflow/loader.py` does no schema validation; a malformed YAML produces confusing errors
- `execution/engine.py` has no handling for nodes that raise exceptions during execution

### 3.7 Assumptions Baked In
- The executor assumes all nodes are passive (no execution function). Every node gets 1ms execution time
- The perturbation model assumes latency is applied globally (before every node), not per-node
- The temporal validator only checks the last trace, not all traces
- `WorkflowExecutionTrace.get_node_latencies()` returns the last signal per node if a node appears multiple times

### 3.8 Type Annotation Gaps
- `core/config.py` — no type annotations
- `execution/engine.py` — partial annotations
- `validation/base.py` — `metrics` field typed as `Dict[str, Any] = None` (should be `Optional`)
- `workflow/registry.py` — uses untyped `overrides: Dict[str, Any] = None`

### 3.9 Dependency Bloat
- `pyproject.toml` requires `torch>=2.0.0` as a core dependency; PyTorch is ~2GB and entirely unnecessary for the workflow analysis core

### 3.10 Script Bugs
- `backend/scripts/invariant_check.sh`: `mypy backend--ignore-missing-imports` missing space before `--`

---

## 4. Gaps (Specified but Not Implemented)

| Specified Feature | Implementation Status |
|------------------|-----------------------|
| `core/graph.py` — graph representation | Exists as `workflow/graph.py`, close but needs edge abstraction |
| `core/edge.py` — edge abstraction | **Missing** — edges stored only in networkx attrs |
| `core/workflow.py` — workflow container with metadata | **Missing** — no version, author, description fields |
| `execution/context.py` — ExecutionContext passed between nodes | **Missing** — no inter-node data passing mechanism |
| `execution/clock.py` — simulated clock | **Missing** — virtual_time is an instance variable, not a standalone clock object |
| `perturbation/base.py` — abstract perturbation interface | **Missing** — PerturbationModel is a dataclass, no apply() method |
| `perturbation/latency.py` | Partially in `execution/perturbation.py`, not as standalone class |
| `perturbation/dropout.py` | `should_drop()` exists, not a standalone perturbation class |
| `perturbation/noise.py` | **Missing** |
| `perturbation/overload.py` | **Missing** |
| `perturbation/cascade.py` | **Missing** |
| `analysis/stability.py` — Lyapunov convergence classification | **Missing** |
| `analysis/divergence.py` — per-node divergence curves | **Missing** |
| `analysis/fault.py` — fault propagation tracing | **Missing** |
| `analysis/sensitivity.py` — perturbation sensitivity sweep | **Missing** |
| `instrumentation/tracer.py` | **Missing** — execution/signals.py is a partial substitute |
| `instrumentation/profiler.py` | **Missing** |
| `instrumentation/recorder.py` | **Missing** — no experiment directory structure |
| `experiment/runner.py` | **Missing** |
| `experiment/suite.py` | **Missing** |
| `experiment/config.py` | **Missing** — core/config.py is partial substitute |
| `experiment/report.py` | **Missing** — reporting/generator.py is partial substitute |
| `adapters/base.py` | **Missing** |
| `adapters/mock.py` — mock nodes for testing | **Missing** — workflow/registry.py is a shell |
| `adapters/ros2.py` | Partially in ros/bridge.py |
| `adapters/custom.py` | **Missing** |
| CLI: `invariant run` | Exists as `invariant validate`, different semantics |
| CLI: `invariant analyze` | **Missing** |
| CLI: `invariant report` | **Missing** |
| CLI: `invariant validate` | Exists (validate command) |
| CLI: `invariant perturbations list/describe` | **Missing** |
| CSV report format | **Missing** |
| LaTeX report format | **Missing** |
| Unit tests for core modules | **Missing** — only one integration test |
| Integration tests (linear, branching, cyclic pipelines) | **Missing** |
| Regression/golden trace tests | **Missing** |
| `pyproject.toml` entry point `invariant` CLI | Present but package uninstallable (no `__init__.py`) |
| CI pipeline `.github/workflows/ci.yml` | **Missing** |
| Pre-commit config | **Missing** |
| Example: `latency_sweep.yaml` | **Missing** |
| Example: `branching_pipeline.yaml` | **Missing** |
| Example: `calibra_template.yaml` | **Missing** |
| API documentation (sphinx/mkdocs) | **Missing** |
| Tutorial documents | **Missing** |

---

## 5. Proposed Final Architecture

```
invariant/
├── __init__.py
├── core/
│   ├── __init__.py
│   ├── graph.py          # WorkflowGraph: nx.DiGraph, DAG enforcement, topological sort
│   ├── node.py           # Node: id, type, exec_fn, latency bounds, health state
│   ├── edge.py           # Edge: source, target, data_type, latency model, reliability
│   └── workflow.py       # Workflow: container, metadata, validation, serialization
├── execution/
│   ├── __init__.py
│   ├── executor.py       # DeterministicExecutor: topological execution, virtual clock
│   ├── scheduler.py      # TopologicalScheduler: ordering respecting dependencies
│   ├── context.py        # ExecutionContext: timestep, outputs, events, active perturbations
│   └── clock.py          # SimulatedClock: discrete, perturbation-injectable, no wall time
├── perturbation/
│   ├── __init__.py
│   ├── base.py           # BasePerturbation: applies_to(), apply(), description
│   ├── latency.py        # LatencyPerturbation: fixed / uniform / gaussian delay
│   ├── dropout.py        # DropoutPerturbation: single-step / sustained / probabilistic
│   ├── noise.py          # NoisePerturbation: output noise injection by distribution
│   ├── overload.py       # OverloadPerturbation: node execution window exceeded
│   └── cascade.py        # CascadePerturbation: multiple perturbations in parallel/sequence
├── analysis/
│   ├── __init__.py
│   ├── metrics.py        # Core metric definitions and collection from traces
│   ├── stability.py      # Lyapunov-style convergence classification
│   ├── divergence.py     # Per-node divergence curves between baseline and perturbed
│   ├── fault.py          # Fault propagation tracing through graph
│   └── sensitivity.py    # Perturbation magnitude sweep → sensitivity curves
├── instrumentation/
│   ├── __init__.py
│   ├── tracer.py         # Structured trace collection per execution
│   ├── profiler.py       # Timing profiler per node and edge
│   └── recorder.py       # Experiment recorder: config + all traces → directory
├── experiment/
│   ├── __init__.py
│   ├── runner.py         # ExperimentRunner: baseline + N perturbed runs + analysis
│   ├── suite.py          # ExperimentSuite: batch of runners from config
│   ├── config.py         # ExperimentConfig: Pydantic schema, validated on load
│   └── report.py         # ReportGenerator: Markdown, CSV, LaTeX, JSON
├── adapters/
│   ├── __init__.py
│   ├── base.py           # AbstractAdapter interface
│   ├── ros2.py           # ROS2 adapter: introspect, wrap, intercept
│   ├── mock.py           # Mock adapter: pre-built mock nodes, configurable behavior
│   └── custom.py         # Custom adapter template
├── cli/
│   ├── __init__.py
│   ├── main.py           # CLI entry point (click group)
│   ├── run.py            # `invariant run` command
│   ├── analyze.py        # `invariant analyze` command
│   └── report.py         # `invariant report` command
└── utils/
    ├── __init__.py
    ├── logging.py        # Structured logging
    ├── serialization.py  # Save/load workflows and results
    └── validation.py     # Input validation utilities
```

**Layer rules (strictly enforced):**
- `core` has zero imports from any other Invariant module
- `execution` imports from `core` only
- `perturbation` imports from `core` and `execution` only
- `analysis` imports from `core`, `execution`, `instrumentation` only
- `instrumentation` imports from `core`, `execution` only
- `experiment` imports from all lower layers
- `adapters` imports from `core`, `execution`, `perturbation`, `instrumentation`
- `cli` imports from `experiment`, `adapters`, `utils`
- `utils` imports from `core` only

---

## 6. Migration Plan

### Keep (minimal changes)
- `workflow/graph.py` → `core/graph.py` (keep networkx core, add edge serialization)
- `workflow/node.py` → `core/node.py` (add execution function field, health state)
- `workflow/loader.py` → `core/workflow.py` (merge into Workflow class)
- `execution/scheduler.py` → `execution/scheduler.py` (unchanged)
- `execution/signals.py` → `instrumentation/tracer.py` (enhance with full trace structure)
- `core/config.py` → `experiment/config.py` (expand with Pydantic schema)

### Refactor (significant changes)
- `execution/engine.py` → `execution/executor.py` (add ExecutionContext, real node execution, full trace recording)
- `execution/perturbation.py` → `perturbation/` (split into individual classes with base interface)
- `validation/` → `analysis/` (keep validators, add stability/divergence/fault/sensitivity)
- `reporting/generator.py` → `experiment/report.py` (add CSV, LaTeX, JSON formats)
- `ros/bridge.py` → `adapters/ros2.py` (clean up, proper adapter interface)
- `invariant/cli.py` → `cli/` (rewrite as proper command package)

### Discard
- `core/engine.py`, `core/interfaces.py`, `core/types.py`, `core/outcome.py` — FlowGuard
- `validators/` — FlowGuard  
- `telemetry/client.py` — FlowGuard
- `ml/` — Out of scope
- `backend/` — Separate project
- `examples/simple_loop.py` — FlowGuard demo
- `verify_ml.py` — PyTorch, out of scope

### Create New
- `core/edge.py` — Edge abstraction
- `execution/context.py` — ExecutionContext
- `execution/clock.py` — SimulatedClock
- `perturbation/base.py`, `latency.py`, `dropout.py`, `noise.py`, `overload.py`, `cascade.py`
- `analysis/stability.py`, `divergence.py`, `fault.py`, `sensitivity.py`
- `instrumentation/profiler.py`, `recorder.py`
- `experiment/runner.py`, `suite.py`
- `adapters/base.py`, `mock.py`, `custom.py`
- `cli/main.py`, `run.py`, `analyze.py`, `report.py`
- `utils/logging.py`, `serialization.py`, `validation.py`
- All `__init__.py` files
- `tests/` — full pytest suite
- `examples/latency_sweep.yaml`, `branching_pipeline.yaml`, `calibra_template.yaml`
- `pyproject.toml` — rewrite (remove torch, add proper deps, entry points)
- `.github/workflows/ci.yml` — CI pipeline
- `.pre-commit-config.yaml` — pre-commit hooks
- `docs/` — mkdocs + mkdocstrings
