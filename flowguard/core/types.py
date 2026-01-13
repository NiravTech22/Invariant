from enum import Enum, auto
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field
import time

class SystemState(BaseModel):
    """
    Represents the snapshot of the system at a specific timestamp.
    This is the inputs to the safety layer.
    """
    timestamp: float = Field(default_factory=time.time)
    pose: Dict[str, float] = Field(default_factory=dict, description="x, y, z, roll, pitch, yaw")
    velocity: Dict[str, float] = Field(default_factory=dict, description="vx, vy, vz, angular_v...")
    sensor_health: Dict[str, bool] = Field(default_factory=dict, description="Status of critical sensors")
    environment_context: Dict[str, Any] = Field(default_factory=dict, description="Map data, zones, etc.")
    
    class Config:
        arbitrary_types_allowed = True

class ActionType(str, Enum):
    VELOCITY_CMD = "velocity_cmd"
    TRAJECTORY = "trajectory"
    TASK_COMMAND = "task_command"

class ProposedAction(BaseModel):
    """
    The action the autonomy system WANTS to take.
    """
    action_id: str
    timestamp: float = Field(default_factory=time.time)
    type: ActionType
    payload: Dict[str, Any] = Field(..., description="The raw command data (e.g., v=1.0, w=0.1)")
    source: str = Field("unknown", description="Planner ID or Neural Policy ID")

class SafetyMode(str, Enum):
    NORMAL = "normal"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
