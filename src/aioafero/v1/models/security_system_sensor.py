"""Representation of an Afero Security System Sensor (derived) and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class SecuritySystemSensor:
    """Representation of a security system sensor."""

    _id: str  # ID used when interacting with Afero
    available: bool
    selects: dict[tuple[str, str | None], features.SelectFeature] | None
    config_key: str | None
    # Security System Sensors are always split devices
    split_identifier: str

    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)
    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM_SENSOR

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

    @property
    def id(self):
        """ID for the device (split or normal)."""
        return self._id

    @property
    def instance(self):
        """Instance for the split device."""
        return int(self._id.rsplit(f"-{self.split_identifier}-", 1)[1])

    @property
    def update_id(self) -> str:
        """ID used when sending updates to Afero API."""
        return self._id.rsplit(f"-{self.split_identifier}-", 1)[0]


@dataclass
class SecuritySystemSensorPut:
    """States that can be updated for a Security System Sensor."""

    callback: callable
    sensor_config: features.SecuritySensorConfigFeature | None = field(
        default_factory=dict, repr=False, init=False
    )
