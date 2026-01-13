from enum import Enum
from typing import Optional, Any, Dict, List
from pydantic import BaseModel
from .types import ProposedAction, SystemState

class Decision(str, Enum):
    APPROVED = "approved"       # Action is safe
    MODIFIED = "modified"       # Action was unsafe, but fixed (clamped/smoothed)
    REJECTED = "rejected"       # Action is unsafe and cannot be fixed
    EMERGENCY_STOP = "estop"    # Critical failure, stop system immediately

class Violation(BaseModel):
    """
    Details of a specific safety check failure.
    """
    rule_id: str
    description: str
    severity: str # "warning", "critical"
    context: Dict[str, Any] = {}

class SafetyOutcome(BaseModel):
    """
    The final result of the FlowGuard evaluation pipeline.
    """
    decision: Decision
    modified_action: Optional[ProposedAction] = None
    violations: List[Violation] = []
    reason: str = "Safe"
    processing_time_ms: float = 0.0
    
    def is_safe(self) -> bool:
        return self.decision == Decision.APPROVED
