from dataclasses import dataclass, field

from ..models import features
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class PortableAC:
    """Representation of an Afero Portable AC"""

    id: str  # ID used when interacting with Afero
    available: bool

    current_temperature: float | None
    hvac_mode: features.HVACModeFeature | None
    target_temperature_cooling: features.TargetTemperatureFeature | None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    # Defined at initialization
    instances: dict = field(default_factory=lambda: dict(), repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=lambda: dict())
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=lambda: dict())

    type: ResourceTypes = ResourceTypes.PORTABLE_AC

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
        return self.target_temperature_cooling.value

    @property
    def target_temperature_step(self) -> float:
        return self.target_temperature_cooling.step

    @property
    def target_temperature_max(self) -> float:
        return self.target_temperature_cooling.max

    @property
    def target_temperature_min(self) -> float | None:
        return self.target_temperature_cooling.min

    @property
    def supports_fan_mode(self) -> bool:
        return False

    @property
    def supports_temperature_range(self) -> bool:
        return False

    def get_instance(self, elem):
        """Lookup the instance associated with the elem"""
        return self.instances.get(elem, None)


@dataclass
class PortableACPut:
    """States that can be updated for a Thermostat"""

    hvac_mode: features.HVACModeFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=lambda: dict(), repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=lambda: dict(), repr=False, init=False
    )
