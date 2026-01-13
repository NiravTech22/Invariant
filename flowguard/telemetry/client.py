import requests
import time
import json
from ..core.outcome import SafetyOutcome, Decision
from ..core.types import SystemState, ProposedAction

class TelemetryBridge:
    def __init__(self, endpoint: str = "http://localhost:8000"):
        self.endpoint = endpoint
        self.enabled = True

    def log_decision(self, state: SystemState, action: ProposedAction, outcome: SafetyOutcome):
        if not self.enabled:
            return

        payload = {
            "decision": outcome.decision.value,
            "reason": outcome.reason,
            "violations": [
                {
                    "rule_id": v.rule_id, 
                    "description": v.description, 
                    "severity": v.severity
                } for v in outcome.violations
            ],
            "original_action_id": action.action_id,
            "processing_time_ms": outcome.processing_time_ms
        }
        
        try:
            # In a real high-frequency loop, this MUST be async or off-thread.
            # detailed implementation would use a Queue + Worker Thread.
            # sending sync for prototype simplicity (with short timeout)
            requests.post(
                f"{self.endpoint}/api/v1/telemetry/decision", 
                json=payload,
                timeout=0.1
            )
        except Exception:
            # Fail silently to not crash the robot
            pass

class ConsoleTelemetryBridge(TelemetryBridge):
    def log_decision(self, state, action, outcome):
        # Just print beautiful logs to console
        tag = "[SAFE]" if outcome.is_safe() else "[WARN]" if outcome.decision == Decision.MODIFIED else "[CRIT]"
        print(f"[TELEM] {tag} {outcome.decision.value.upper()} | {outcome.reason} ({outcome.processing_time_ms:.2f}ms)")
