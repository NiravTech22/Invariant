from typing import Optional
from ..core.interfaces import SafetyValidator
from ..core.types import SystemState, ProposedAction
from ..core.outcome import Violation

class GeofenceValidator(SafetyValidator):
    def __init__(self, x_limit: float = 10.0, y_limit: float = 10.0):
        self.x_limit = x_limit
        self.y_limit = y_limit

    @property
    def name(self) -> str:
        return "GeofencePolicy"

    def check(self, state: SystemState, action: ProposedAction) -> Optional[Violation]:
        # Simple check: If robot is OUTSIDE bounds, block any motion that moves FURTHER away
        # For simplicity in this demo, we just fault if specific zones are entered or if state says we are OOB
        
        x = state.pose.get("x", 0.0)
        y = state.pose.get("y", 0.0)

        if abs(x) > self.x_limit or abs(y) > self.y_limit:
            return Violation(
                rule_id="GEO_001",
                description=f"System outside operational area ({x}, {y})",
                severity="critical",
                context={"pose": state.pose, "limits": [self.x_limit, self.y_limit]}
            )
            
        return None
