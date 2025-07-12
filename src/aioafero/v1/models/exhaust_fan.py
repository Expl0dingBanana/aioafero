"""Representation of an Afero Exhaust Fan and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class ExhaustFan:
    """Representation of an Afero Exhaust Fan."""

    id: str  # ID used when interacting with Afero
    available: bool

    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None
    # Defined at initialization
    instances: dict = field(default_factory=dict, repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=dict)
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=dict)

    type: ResourceTypes = ResourceTypes.EXHAUST_FAN

    def __init__(self, functions: list, **kwargs):  # noqa: D107
        for key, value in kwargs.items():
            setattr(self, key, value)
        instances = {}
        for function in functions:
            instances[function["functionClass"]] = function.get(
                "functionInstance", None
            )
        self.instances = instances


@dataclass
class ExhaustFanPut:
    """States that can be updated for an exhaust fan."""

    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
