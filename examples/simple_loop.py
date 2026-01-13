import time
import sys
import os

# Add parent dir to path so we can import flowguard
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from flowguard.core.types import SystemState, ProposedAction, ActionType
from flowguard.core.engine import SafetySupervisor
from flowguard.validators.physical import PhysicalConstraintValidator
from flowguard.validators.policy import GeofenceValidator

def run_demo():
    print("Starting FlowGuard Demo Loop...")
    
    # 1. Setup Supervisor
    supervisor = SafetySupervisor()
    supervisor.register_validator(PhysicalConstraintValidator(max_linear_velocity=2.0))
    supervisor.register_validator(GeofenceValidator(x_limit=10.0))
    
    # 2. Simulate Scenarios
    scenarios = [
        {
            "name": "Normal Operation",
            "state": SystemState(pose={"x": 0, "y": 0}, velocity={"vx": 0.5}),
            "action": ProposedAction(
                action_id="1", 
                type=ActionType.VELOCITY_CMD, 
                payload={"v": 1.5, "w": 0.1}
            )
        },
        {
            "name": "Overspeed Violation",
            "state": SystemState(pose={"x": 5, "y": 5}, velocity={"vx": 1.0}),
            "action": ProposedAction(
                action_id="2", 
                type=ActionType.VELOCITY_CMD, 
                payload={"v": 5.0, "w": 0.1} # Exceeds limit 2.0
            ) 
        },
        {
            "name": "Geofence Breach",
            "state": SystemState(pose={"x": 12, "y": 0}), # Out of bounds 10.0
            "action": ProposedAction(
                action_id="3", 
                type=ActionType.VELOCITY_CMD, 
                payload={"v": 0.5, "w": 0.0}
            )
        }
    ]

    for s in scenarios:
        print(f"\n--- Scenario: {s['name']} ---")
        outcome = supervisor.evaluate(s['state'], s['action'])
        
        status_text = "[SAFE]" if outcome.is_safe() else "[MODIFIED]" if outcome.decision.value == "modified" else "[BLOCKED]"
        print(f"Decision: {status_text} {outcome.decision.value.upper()}")
        print(f"Reason: {outcome.reason}")
        
        if outcome.decision.value == "modified":
             print(f"  -> Original: {s['action'].payload}")
             print(f"  -> Modified: {outcome.modified_action.payload}")

        if outcome.violations:
            for v in outcome.violations:
                print(f"  - Violation: {v.description} [{v.rule_id}]")

if __name__ == "__main__":
    run_demo()
