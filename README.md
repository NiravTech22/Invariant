# FlowGuard: Robotics Runtime Governance Layer

**FlowGuard** is a production-grade runtime safety, validation, and governance layer for autonomous systems. It sits between the autonomy decision system (Planner/Policy) and the execution environment (Controller/Hardware), ensuring that all actions comply with physical constraints, safety policies, and system invariants.

![Status](https://img.shields.io/badge/status-active-success)
![Safety](https://img.shields.io/badge/safety-fail--safe-blue)

## Core Mission

To provide a **deterministic, traceable, and fail-safe** supervisory layer that allows researchers and engineers to deploy experimental autonomy models (LLMs, Neural Policies) without risking physical safety.

## Architecture

FlowGuard operates as a strictly layered pipeline:

1.  **Observability**: Ingests `SystemState` (pose, velocity, sensors).
2.  **Safety Pipeline**: Runs a chain of `SafetyValidator` modules:
    *   **Physical Constraints**: Max velocity, acceleration limits.
    *   **Policies**: Geofencing, operational zones.
    *   **Uncertainty**: Sensor health checks.
3.  **Intervention**:
    *   **Approve**: Pass-through valid actions.
    *   **Modify**: Clamp/Smooth actions to safe bounds.
    *   **Reject/E-Stop**: Block critical violations.

## Project Structure

```bash
FlowGuard/
├── flowguard/          # Core Safety Library
│   ├── core/           # Interfaces & Types
│   ├── validators/     # Safety Checks (Constraints/Policies)
│   ├── intervention/   # Modification Logic
│   └── telemetry/      # Logging & Explainability
├── backend/            # Telemetry Aggregator (FastAPI)
├── examples/           # Simulation Scripts & Demos
└── tests/              # Regression & Unit Tests
```

## Getting Started

### Prerequisites
- Python 3.10+
- (Optional) ROS2 for hardware integration

### Quick Start (Simulated)

```bash
# Install dependencies
pip install pydantic

# Run the demo loop
python examples/simple_loop.py
```

## Contribution

Safety is paramount. All changes require:
1.  Passing regression tests.
2.  No degradation in decision latency.
