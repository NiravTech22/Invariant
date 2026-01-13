from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class TelemetryEvent(BaseModel):
    timestamp: float
    type: str # "decision", "heartbeat"
    data: Dict[str, Any]

class ViolationLog(BaseModel):
    rule_id: str
    description: str
    severity: str

class DecisionLog(BaseModel):
    decision: str
    reason: str
    violations: List[ViolationLog]
    original_action_id: str
    processing_time_ms: float
