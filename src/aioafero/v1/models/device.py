"""Representation of a top-level item."""

from dataclasses import dataclass, field

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Device:
    """Representation of an Afero parent item."""

    id: str  # ID used when interacting with Afero
    available: bool

    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.PARENT_DEVICE
