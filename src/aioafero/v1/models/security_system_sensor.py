from dataclasses import dataclass, field

from ..models import features
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class SecuritySystemSensor:
    """Representation of a security system sensor"""

    _id: str  # ID used when interacting with Afero
    available: bool
    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    # Defined at initialization
    instances: dict = field(default_factory=lambda: dict(), repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=lambda: dict())
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=lambda: dict())
    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM_SENSOR

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
    def id(self):
        return self._id

    @property
    def sensor_id(self):
        return int(self._id.rsplit("-sensor-", 1)[1])

    @property
    def update_id(self):
        return self._id.split("-sensor-", 1)[0]


@dataclass
class SecuritySystemSensorPut:
    """States that can be updated for a Security System Sensor"""

    callback: callable
    sensor_config: features.SecuritySensorConfigFeature | None = field(
        default_factory=lambda: dict(), repr=False, init=False
    )
