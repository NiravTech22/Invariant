from typing import Optional, Dict
from ..core.interfaces import SafetyValidator
from ..core.types import SystemState, ProposedAction, ActionType
from ..core.outcome import Violation

class PhysicalConstraintValidator(SafetyValidator):
    def __init__(self, max_linear_velocity: float = 2.0, max_angular_velocity: float = 1.0):
        self.max_v = max_linear_velocity
        self.max_w = max_angular_velocity

    @property
    def name(self) -> str:
        return "PhysicalConstraints"

    def check(self, state: SystemState, action: ProposedAction) -> Optional[Violation]:
        # Only check velocity commands for now
        if action.type != ActionType.VELOCITY_CMD:
            return None
        
        payload = action.payload
        # Assume payload has 'v' (linear) and 'w' (angular)
        v = abs(payload.get("v", 0.0))
        w = abs(payload.get("w", 0.0))

        if v > self.max_v:
            return Violation(
                rule_id="PHYS_001",
                description=f"Linear velocity {v:.2f} exceeds limit {self.max_v}",
                severity="critical",
                context={"current_v": v, "max_v": self.max_v}
            )
        
        if w > self.max_w:
            return Violation(
                rule_id="PHYS_002",
                description=f"Angular velocity {w:.2f} exceeds limit {self.max_w}",
                severity="critical",
                context={"current_w": w, "max_w": self.max_w}
            )
            
        return None
