
from ..core.interfaces import SafetyValidator
from ..core.outcome import Violation
from ..core.types import ProposedAction, SystemState


class UncertaintyValidator(SafetyValidator):
    def __init__(self, required_sensors: list[str] = None):
        self.required_sensors = required_sensors or ["lidar", "imu"]

    @property
    def name(self) -> str:
        return "UncertaintyCheck"

    def check(self, state: SystemState, action: ProposedAction) -> Violation | None:
        # Check if critical sensors are healthy
        if not state.sensor_health:
            return None # Assume healthy if not reported, or handle strict mode

        for sensor in self.required_sensors:
            if not state.sensor_health.get(sensor, True):
                return Violation(
                    rule_id="UNCERT_001",
                    description=f"Critical sensor '{sensor}' reported unhealthy",
                    severity="critical",
                    context={"sensor_health": state.sensor_health}
                )
        return None
