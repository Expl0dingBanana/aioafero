from dataclasses import dataclass, field

from ..models import features
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class SecuritySystem:
    """Representation of an Afero Security Panel"""

    id: str  # ID used when interacting with Afero
    available: bool

    alarm_state: features.ModeFeature | None
    siren_action: features.SecuritySensorSirenFeature | None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    # Defined at initialization
    instances: dict = field(default_factory=lambda: dict(), repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=lambda: dict())
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=lambda: dict())

    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM

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
    def supports_away(self) -> bool:
        """States if the panel supports away mode"""
        return "arm-away" in self.alarm_state.modes

    @property
    def supports_arm_bypass(self) -> bool:
        """States if the panel supports arm-bypass mode"""
        return False

    @property
    def supports_home(self) -> bool:
        """States if the panel supports home mode"""
        return "arm-stay" in self.alarm_state.modes

    @property
    def supports_night(self) -> bool:
        """States if the panel supports night mode"""
        return False

    @property
    def supports_vacation(self) -> bool:
        """States if the panel supports vacation mode"""
        return False

    @property
    def supports_trigger(self) -> bool:
        """States if the panel supports manually triggering"""
        return "alarming-sos" in self.alarm_state.modes

    def get_instance(self, elem):
        """Lookup the instance associated with the elem"""
        return self.instances.get(elem, None)


@dataclass
class SecuritySystemPut:
    """States that can be updated for a Security System"""

    alarm_state: features.ModeFeature | None = None
    siren_action: features.SecuritySensorSirenFeature | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=lambda: dict(), repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=lambda: dict(), repr=False, init=False
    )
