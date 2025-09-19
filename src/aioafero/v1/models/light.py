"""Representation of an Afero Light and its corresponding updates."""

from dataclasses import dataclass
import re

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin

rgbw_name_search = re.compile(r"RGB\w*W")


@dataclass(kw_only=True)
class Light(StandardMixin):
    """Representation of an Afero Light."""

    type: ResourceTypes = ResourceTypes.LIGHT

    on: features.OnFeature | None = None
    color: features.ColorFeature | None = None
    color_mode: features.ColorModeFeature | None = None
    color_modes: list[str] | None = None
    color_temperature: features.ColorTemperatureFeature | None = None
    dimming: features.DimmingFeature | None = None
    effect: features.EffectFeature | None = None
    supports_white: bool = False

    def __post_init__(self):
        """Determine if white only is supported."""
        super().__post_init__()
        model = getattr(getattr(self, "device_information", None), "model", None)
        if model is not None and rgbw_name_search.search(model):
            self.supports_white = True

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
        """Return if this light supports setting white."""
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
        """If the light can be toggled on or off."""
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
    """States that can be updated for a light."""

    on: features.OnFeature | None = None
    color: features.ColorFeature | None = None
    color_mode: features.ColorModeFeature | None = None
    color_temperature: features.ColorTemperatureFeature | None = None
    dimming: features.DimmingFeature | None = None
    effect: features.EffectFeature | None = None
