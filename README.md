# Invariant — Project Summary & Development Roadmap

**Author:** Nirav Sawant  
**Affiliation:** Queen's University, Mechatronics & Robotics Engineering  
**Status:** Active Development — Hardware Integration Phase  
**Last Updated:** June 2026

---

## Overview

Invariant is a research framework for analyzing the stability, correctness, and failure modes of robotics software pipelines — treating the full stack as a system rather than a collection of isolated components. It represents workflows as directed acyclic graphs (DAGs), executes them under deterministic simulated perturbations, and produces reproducible, quantified stability reports.

The current development phase extends the existing simulation engine to physical hardware, beginning with the SO-ARM100/SO-101 6-DOF robotic arm, with a near-term goal of closing the sim-to-real gap and enabling RL policy training via the HuggingFace LeRobot library.

---

## Repository Structure

```
invariant/
├── core/             Node, Edge, WorkflowGraph, Workflow — pure data model
├── execution/        SimulatedClock, ExecutionContext, DeterministicExecutor
├── perturbation/     BasePerturbation, Latency, Dropout, Noise, Overload, Cascade
├── analysis/         Divergence, Stability, FaultPropagation, Sensitivity
├── instrumentation/  ExecutionTrace, WorkflowProfiler, ExperimentRecorder
├── experiment/       ExperimentConfig, ExperimentRunner, ReportGenerator, Suite
├── adapters/         MockAdapter (built-in), ROS2Adapter (optional)
├── cli/              invariant run | validate | perturbations | analyze
└── utils/            logging, serialization, validation
```

**Test coverage:** 159 passing, 2 skipped — 86% coverage across core modules.

---

## Hardware Platform: SO-ARM100 / SO-101

### Platform Description

The SO-ARM100/SO-101 is a low-cost, open-source 6-DOF desktop robotic arm designed for imitation learning and manipulation research. It uses Feetech STS3215 serial bus servos with position/velocity/load feedback, controlled over a USB-to-serial interface. The design is 3D-printable and pairs directly with the HuggingFace LeRobot library as the `arm101` robot type.

### Hardware Configuration

| Component | Specification |
|---|---|
| Degrees of freedom | 6 (shoulder, elbow, wrist ×3, gripper) |
| Servos | Feetech STS3215 (serial bus, 12-bit encoder, 19 kg·cm) |
| Communication | Serial bus over USB-TTL adapter |
| Control interface | LeRobot `arm101` / Python `lerobot.common.robot_devices` |
| 3D printing | Bambu A1 Mini (ASA/PETG recommended for structural parts) |
| Power | 12V DC regulated supply |
| Build status | **Fully assembled — gripper actuator pending** |

### Current Build Status

All structural joints and servo linkages are assembled and calibrated. The arm currently operates across 5 DOF (shoulder pan/tilt, elbow, wrist pitch/roll). The 6th axis — the gripper — is the remaining mechanical dependency before full-pipeline operation. Gripper servo hardware is on order (estimated delivery late June / early July 2026).

The arm is functional for data collection experiments that do not require end-effector grasping (point-reaching, joint trajectory tasks, sweep motions).

---

## Diagnostic Assessment

### Simulation Layer (Current State)

| Subsystem | Status | Notes |
|---|---|---|
| WorkflowGraph / DAG engine | ✅ Stable | Cycle detection, Pydantic validation working |
| DeterministicExecutor | ✅ Stable | SimulatedClock only, seeded RNGs, byte-identical traces |
| Perturbation suite | ✅ Stable | Latency, Dropout, Noise, Overload, Cascade all implemented |
| Divergence analysis | ✅ Stable | DivergenceAnalyzer produces per-node delta metrics |
| StabilityAnalyzer | ✅ Stable | Returns `STABLE` / `MARGINAL` / `UNSTABLE` class |
| FaultPropagationAnalyzer | ✅ Stable | Correctly traces impacted downstream nodes |
| ROS2Adapter | ⚠️ Partial | `rclpy` imports gated — functional only with ROS2 environment present |
| Hardware adapter (SO-ARM100) | 🔴 Not yet implemented | Required for real-device experiments |
| RL policy interface | 🔴 Not yet implemented | Needed for LeRobot training loop |
| Real-time data logging | 🔴 Not yet implemented | Servo telemetry → `ExecutionTrace` bridge missing |

### Known Gaps

**1. No hardware-in-the-loop (HIL) adapter**  
The `adapters/` directory has a MockAdapter and a stub ROS2Adapter, but no direct bridge to the SO-ARM100's serial bus. Perturbation experiments currently run in simulation only and cannot be validated against physical servo behavior.

**2. Sim-to-real divergence is unmeasured**  
The `DivergenceAnalyzer` compares two simulation traces. There is no mechanism to load real hardware telemetry (joint positions, velocities, torques over time) and compute divergence against a simulated baseline. This is the single most important gap to close before the framework produces externally useful results.

**3. Gripper dependency blocks end-effector tasks**  
Without a functional gripper, the task space for policy training is limited to reaching and waving trajectories. Grasp-and-lift (the most data-rich task type for manipulation RL) is blocked until the gripper actuator is installed.

**4. No episode data format**  
LeRobot expects data in HuggingFace `datasets` format (parquet + video). Invariant has no exporter that maps an `ExecutionTrace` to this schema, which would enable cross-framework evaluation.

---

## Next Steps: Training & Reinforcement Learning

### Phase 1 — Hardware Adapter (Immediate, pre-gripper)

Build `invariant/adapters/soarm.py` — a hardware adapter that:
- Opens a serial connection to the SO-ARM100 bus
- Reads joint state (position, velocity, load) at configurable Hz
- Wraps each read cycle as an `ExecutionTrace` timestep
- Exposes the same interface as `MockAdapter` so existing analyzers work without modification

This lets you run real divergence experiments as soon as the arm is powered — no gripper needed.

```python
# Target API
from invariant.adapters.soarm import SOArmAdapter

adapter = SOArmAdapter(port="/dev/ttyUSB0", baud=1000000)
workflow = adapter.build_pipeline()
trace = DeterministicExecutor(workflow).run_hardware(duration_s=5.0)
```

### Phase 2 — Sim-to-Real Divergence Baseline (pre-gripper)

Once the hardware adapter is working:

1. Run a joint trajectory on the simulated arm (5-DOF) under nominal conditions → `baseline_trace`
2. Replay the same trajectory on the physical arm → `hardware_trace`
3. Pass both to `DivergenceAnalyzer` to quantify per-joint deviation
4. Introduce latency / dropout perturbations in simulation and measure whether divergence predictions hold on hardware

This produces your first real result: *"How well does Invariant's simulation predict real hardware instability?"*

### Phase 3 — Gripper Integration & Dataset Collection

After gripper hardware arrives:

1. Calibrate the 6th axis servo (home offset, torque limits)
2. Collect imitation learning episodes via LeRobot teleoperation:
   ```bash
   python lerobot/scripts/control_robot.py teleoperate \
     --robot-path lerobot/configs/robot/arm101.yaml
   ```
3. Record 50–100 pick-and-place episodes for training
4. Export traces to HuggingFace dataset format for cross-analysis with Invariant

### Phase 4 — Policy Training (LeRobot / ACT)

Target architecture: **ACT (Action Chunking with Transformers)**, which is well-suited to the SO-101's data volume and task complexity.

```bash
python lerobot/scripts/train.py \
  policy=act \
  env=soarm101 \
  dataset_repo_id=NiravTech22/soarm101-pickplace \
  training.num_epochs=100
```

Key training decisions:
- **Observation space:** joint positions (6) + optionally wrist camera RGB
- **Action space:** joint position deltas, chunked over horizon H=100
- **Data augmentation:** color jitter on camera feed, small joint noise to improve generalization
- **Evaluation:** run trained policy and capture telemetry → feed back into Invariant's `DivergenceAnalyzer` to measure policy-induced instability vs. human teleoperation baseline

### Phase 5 — Invariant as RL Diagnostic Tool

The longer-term research hook: use Invariant not just to test software pipelines, but to evaluate trained policies as dynamic systems.

- **Stability under perturbation:** Does a trained policy remain stable when latency is injected into its perception-to-action loop?
- **Fault propagation:** If the wrist encoder drops out, does the policy degrade gracefully or catastrophically?
- **Divergence from nominal:** How much does policy behavior diverge from the demonstration distribution as a function of perturbation magnitude?

This reframes Invariant from a dev tool into a **policy evaluation framework** — a meaningful research contribution, particularly combined with sim-to-real analysis.

---

## Immediate Action Items

| Priority | Task | Blocker |
|---|---|---|
| 🔴 High | Build `SOArmAdapter` (hardware serial bridge) | None — doable now |
| 🔴 High | Implement `hardware_trace` → `DivergenceAnalyzer` pipeline | Needs adapter |
| 🟡 Medium | Define `ExecutionTrace` → LeRobot dataset exporter | None — doable now |
| 🟡 Medium | Run 5-DOF sim-to-real divergence baseline experiment | Needs adapter |
| 🟢 Low | Install gripper servo + calibrate 6th axis | Hardware delivery ~late June |
| 🟢 Low | Collect pick-and-place teleoperation dataset | Needs gripper |
| 🟢 Low | Train ACT policy on SO-101 | Needs dataset |

---

## References

- H. Araujo, M. R. Mousavi, and M. Varshosaz, "Testing, Validation, and Verification of Robotic and Autonomous Systems: A Systematic Review," *ACM Trans. Softw. Eng. Methodol.*, vol. 32, no. 2, pp. 51:1–51:61, 2023. DOI: 10.1145/3542945
- T. Zhao et al., "Learning Fine-Grained Bimanual Manipulation with Low-Cost Hardware," *RSS 2023* (ACT paper)
- HuggingFace LeRobot: https://github.com/huggingface/lerobot
- SO-ARM100/SO-101 hardware design: https://github.com/TheRobotStudio/SO-ARM100
