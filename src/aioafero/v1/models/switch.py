"""Representation of an Afero Switch and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Switch:
    """Representation of an Afero Switch."""

    id: str  # ID used when interacting with Afero
    available: bool

    on: dict[str | None, features.OnFeature]
    # Defined at initialization
    split_identifier: str | None = None
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.FAN

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

    @property
    def instance(self):
        """Instance for the split device."""
        if self.split_identifier:
            return self.id.rsplit(f"-{self.split_identifier}-", 1)[1]
        return None

    @property
    def update_id(self) -> str:
        """ID used when sending updates to Afero API."""
        if self.split_identifier:
            return self.id.rsplit(f"-{self.split_identifier}-", 1)[0]
        return self.id


@dataclass
class SwitchPut:
    """States that can be updated for a Switch."""

    on: features.OnFeature | None = None
