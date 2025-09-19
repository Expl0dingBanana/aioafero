"""Representation of an Afero Thermostat and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .hvac_mixin import HVACMixin
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Thermostat(HVACMixin):
    """Representation of an Afero Thermostat."""

    id: str  # ID used when interacting with Afero
    available: bool
    hvac_action: str | None
    safety_max_temp: features.TargetTemperatureFeature | None
    safety_min_temp: features.TargetTemperatureFeature | None

    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.THERMOSTAT

    def __init__(self, functions: list, **kwargs):  # noqa: D107
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

    def get_instance(self, elem):
        """Lookup the instance associated with the elem."""
        return self.instances.get(elem, None)


@dataclass
class ThermostatPut:
    """States that can be updated for a Thermostat."""

    fan_mode: features.ModeFeature | None = None
    hvac_mode: features.HVACModeFeature | None = None
    safety_max_temp: features.TargetTemperatureFeature | None = None
    safety_min_temp: features.TargetTemperatureFeature | None = None
    target_temperature_auto_heating: features.TargetTemperatureFeature | None = None
    target_temperature_auto_cooling: features.TargetTemperatureFeature | None = None
    target_temperature_heating: features.TargetTemperatureFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
