from dataclasses import dataclass, field

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoSensor


@dataclass
class Device:
    """Representation of an Afero parent item"""

    id: str  # ID used when interacting with Afero
    available: bool

    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoSensor] = field(default_factory=dict)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)

    type: ResourceTypes = ResourceTypes.PARENT_DEVICE
