from dataclasses import dataclass, field

from ..models import features
from .resource import DeviceInformation, ResourceTypes
from .sensor import AferoBinarySensor, AferoSensor


@dataclass
class Light:
    """Representation of an Afero Light"""

    id: str  # ID used when interacting with Afero
    available: bool

    on: features.OnFeature | None
    color: features.ColorFeature | None
    color_mode: features.ColorModeFeature | None
    color_modes: list[str] | None
    color_temperature: features.ColorTemperatureFeature | None
    dimming: features.DimmingFeature | None
    effect: features.EffectFeature | None

    # Defined at initialization
    instances: dict = field(default_factory=lambda: dict(), repr=False, init=False)
    device_information: DeviceInformation = field(default_factory=DeviceInformation)
    sensors: dict[str, AferoSensor] = field(default_factory=lambda: dict())
    binary_sensors: dict[str, AferoBinarySensor] = field(default_factory=lambda: dict())

    type: ResourceTypes = ResourceTypes.LIGHT

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

    def get_instance(self, elem):
        """Lookup the instance associated with the elem"""
        return self.instances.get(elem, None)

    @property
    def supports_color(self) -> bool:
        """Return if this light supports color control."""
        return self.color is not None

    @property
    def supports_color_temperature(self) -> bool:
        """Return if this light supports color_temperature control."""
        return self.color_temperature is not None

    @property
    def supports_color_white(self) -> bool:
        """Return if this light supports setting white"""
        return self.color_modes is not None and "white" in self.color_modes

    @property
    def supports_dimming(self) -> bool:
        """Return if this light supports brightness control."""
        return self.dimming is not None

    @property
    def supports_effects(self) -> bool:
        """Return if this light supports brightness control."""
        return self.effect is not None

    @property
    def supports_on(self):
        return self.on is not None

    @property
    def is_on(self) -> bool:
        """Return bool if light is currently powered on."""
        if self.on is not None:
            return self.on.on
        return False

    @property
    def brightness(self) -> float:
        """Return current brightness of light."""
        if self.dimming is not None:
            return self.dimming.brightness
        return 100.0 if self.is_on else 0.0


@dataclass
class LightPut[AferoResource]:
    """States that can be updated for a light"""

    on: features.OnFeature | None = None
    color: features.ColorFeature | None = None
    color_mode: features.ColorModeFeature | None = None
    color_temperature: features.ColorTemperatureFeature | None = None
    dimming: features.DimmingFeature | None = None
    effect: features.EffectFeature | None = None
