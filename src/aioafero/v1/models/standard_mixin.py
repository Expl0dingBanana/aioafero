"""Handles generic information related to all devices."""

from dataclasses import dataclass, field

from . import features
from .resource import DeviceInformation
from .sensor import AferoBinarySensor, AferoSensor


@dataclass(kw_only=True)
class StandardMixin:
    """Mixin for standard properties and methods."""

    _id: str  # ID used when interacting with Afero
    available: bool
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    split_identifier: str | None = None

    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict
    )
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)
    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)

    def __post_init__(self):
        """Configure the available instances."""
        instances = {}
        for function in self.device_information.functions or []:
            instances[function["functionClass"]] = function.get(
                "functionInstance", None
            )
        self.instances = instances

    def get_instance(self, elem):
        """Lookup the instance associated with the elem."""
        return self.instances.get(elem, None)

    @property
    def id(self):
        """ID for the device (split or normal)."""
        return self._id

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
