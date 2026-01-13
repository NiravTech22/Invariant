import time
from typing import List
from .types import SystemState, ProposedAction, SafetyMode
from .outcome import SafetyOutcome, Decision
from .interfaces import SafetyValidator

from ..telemetry.client import TelemetryBridge, ConsoleTelemetryBridge

class SafetySupervisor:
    def __init__(self, telemetry_bridge: TelemetryBridge = None):
        self.validators: List[SafetyValidator] = []
        self.mode = SafetyMode.NORMAL
        self.telemetry = telemetry_bridge or ConsoleTelemetryBridge()

    def register_validator(self, validator: SafetyValidator):
        self.validators.append(validator)

    def evaluate(self, state: SystemState, action: ProposedAction) -> SafetyOutcome:
        start_time = time.time()
        violations = []

        # 1. Run all validators
        for v in self.validators:
            violation = v.check(state, action)
            if violation:
                violations.append(violation)

        # 2. Determine Decision
        decision = Decision.APPROVED
        reason = "Safe"
        
        if violations:
            # 3. Attempt Intervention (Clamping)
            if action.type == "velocity_cmd" and all(v.rule_id.startswith("PHYS") for v in violations):
                # Simple Logic: If only Physical violations, try to clamp
                # In a real system, we'd iterate through specialized Modifiers
                # Here we just hardcode a 'safe' clamp for the demo
                modified_payload = action.payload.copy()
                
                # Check for specific violations
                for v in violations:
                     if "exceeds limit" in v.description:
                         # Extraction logic would be more robust in prod
                         # context={"current_v": v, "max_v": self.max_v}
                         if "max_v" in v.context:
                             modified_payload["v"] = v.context["max_v"]
                         if "max_w" in v.context:
                             modified_payload["w"] = v.context["max_w"]

                decision = Decision.MODIFIED
                reason = "Action Clamped to Limits"
                return SafetyOutcome(
                    decision=decision,
                    modified_action=ProposedAction(
                        action_id=action.action_id,
                        type=action.type,
                        payload=modified_payload,
                        source="FlowGuardModifier"
                    ),
                    violations=violations,
                    reason=reason,
                    processing_time_ms=(time.time() - start_time) * 1000
                )
            
            # Default to REJECT if we can't safely modify
            decision = Decision.REJECTED
            reason = f"Blocked by {len(violations)} checks"

        result = SafetyOutcome(
            decision=decision,
            violations=violations,
            reason=reason,
            processing_time_ms=(time.time() - start_time) * 1000
        )
        
        # Log to telemetry
        self.telemetry.log_decision(state, action, result)
        
        return result
