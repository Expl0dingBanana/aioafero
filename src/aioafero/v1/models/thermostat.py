from dataclasses import dataclass, field

from ..models import features
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Thermostat:
    """Representation of an Afero Thermostat"""

    id: str  # ID used when interacting with Afero
    available: bool

    current_temperature: float | None
    fan_running: bool | None
    fan_mode: features.ModeFeature | None
    hvac_action: str | None
    hvac_mode: features.HVACModeFeature | None
    safety_max_temp: features.TargetTemperatureFeature | None
    safety_min_temp: features.TargetTemperatureFeature | None
    target_temperature_auto_heating: features.TargetTemperatureFeature | None
    target_temperature_auto_cooling: features.TargetTemperatureFeature | None
    target_temperature_heating: features.TargetTemperatureFeature | None
    target_temperature_cooling: features.TargetTemperatureFeature | None

    # Defined at initialization
    instances: dict = field(default_factory=lambda: dict(), repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=lambda: dict())
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=lambda: dict())

    type: ResourceTypes = ResourceTypes.THERMOSTAT

    def __init__(self, functions: list, **kwargs):
        for key, value in kwargs.items():
            if key == "instances":
                continue
            setattr(self, key, value)
        instances = {}
        for function in functions:
            instances[function["functionClass"]] = function.get(
                "functionInstance", None
            )
        self.instances = instances

    @property
    def target_temperature(self) -> float | None:
        if self.hvac_mode is None or self.hvac_mode.mode not in [
            "cool",
            "heat",
            "fan",
            "off",
        ]:
            return None
        return getattr(
            self._get_target_feature(self.get_mode_to_check()), "value", None
        )

    def get_mode_to_check(self) -> str | None:
        if not self.hvac_mode:
            return None
        if self.hvac_mode.mode in ["cool", "heat"]:
            return self.hvac_mode.mode
        elif self.hvac_mode.previous_mode in ["cool", "heat"]:
            return self.hvac_mode.previous_mode
        else:
            return None

    def _get_target_feature(self, mode: str) -> float | None:
        if mode == "cool":
            return self.target_temperature_cooling
        elif mode == "heat":
            return self.target_temperature_heating
        else:
            return None

    @property
    def target_temperature_range(self) -> tuple[float, float]:
        return (
            self.target_temperature_auto_heating.value,
            self.target_temperature_auto_cooling.value,
        )

    @property
    def target_temperature_step(self) -> float:
        set_mode = self.get_mode_to_check()
        if not set_mode:
            return 0.5  # Default from Hubspace
        else:
            return getattr(
                self._get_target_feature(self.get_mode_to_check()), "step", None
            )

    @property
    def target_temperature_max(self) -> float:
        set_mode = self.get_mode_to_check()
        if not set_mode or self.hvac_mode.mode == "auto":
            return self.target_temperature_auto_cooling.max
        else:
            return getattr(self._get_target_feature(set_mode), "max", None)

    @property
    def target_temperature_min(self) -> float | None:
        set_mode = self.get_mode_to_check()
        if not set_mode or self.hvac_mode.mode == "auto":
            return self.target_temperature_auto_heating.min
        else:
            return getattr(
                self._get_target_feature(self.get_mode_to_check()), "min", None
            )

    @property
    def supports_fan_mode(self) -> bool:
        return self.fan_mode is not None

    @property
    def supports_temperature_range(self) -> bool:
        return (
            self.target_temperature_auto_cooling is not None
            and self.target_temperature_auto_heating is not None
        )

    def get_instance(self, elem):
        """Lookup the instance associated with the elem"""
        return self.instances.get(elem, None)


@dataclass
class ThermostatPut:
    """States that can be updated for a Thermostat"""

    fan_mode: features.ModeFeature | None = None
    hvac_mode: features.HVACModeFeature | None = None
    safety_max_temp: features.TargetTemperatureFeature | None = None
    safety_min_temp: features.TargetTemperatureFeature | None = None
    target_temperature_auto_heating: features.TargetTemperatureFeature | None = None
    target_temperature_auto_cooling: features.TargetTemperatureFeature | None = None
    target_temperature_heating: features.TargetTemperatureFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
