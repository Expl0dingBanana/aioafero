"""Representation of an Afero Valve and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Valve:
    """Representation of an Afero Valve."""

    id: str  # ID used when interacting with Afero
    available: bool

    open: dict[str | None, features.OpenFeature]
    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.WATER_TIMER

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
class ValvePut:
    """States that can be updated for a Valve."""

    open: features.OpenFeature | None = None
