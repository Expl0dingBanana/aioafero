"""Representation of an Afero Security System Keypad and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class SecuritySystemKeypad:
    """Representation of an Afero Security Keypad."""

    id: str  # ID used when interacting with Afero
    available: bool

    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM

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
class SecuritySystemKeypadPut:
    """States that can be updated for a Security System Keypad."""

    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
