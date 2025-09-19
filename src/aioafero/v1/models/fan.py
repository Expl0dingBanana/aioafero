"""Representation of an Afero Fan and its corresponding updates."""

from dataclasses import dataclass

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Fan(StandardMixin):
    """Representation of an Afero Fan."""

    type: ResourceTypes = ResourceTypes.FAN

    on: features.OnFeature | None = None
    speed: features.SpeedFeature | None = None
    direction: features.DirectionFeature | None = None
    preset: features.PresetFeature | None = None

    @property
    def supports_direction(self):
        """Determine if you can change the direction of the fan."""
        return self.direction is not None

    @property
    def supports_on(self):
        """Determine if you can turn the fan on or off."""
        return self.on is not None

    @property
    def supports_presets(self):
        """Determine if presets are supported by this fan."""
        return self.preset is not None

    @property
    def supports_speed(self):
        """Determine if a speed feature is supported by this fan."""
        return self.speed is not None

    @property
    def is_on(self) -> bool:
        """Return bool if fan is currently powered on."""
        if self.on:
            return self.on.on
        return False

    @property
    def current_direction(self) -> bool:
        """Return if the direction is forward."""
        if self.direction:
            return self.direction.forward
        return False

    @property
    def current_speed(self) -> int:
        """Current speed of the fan, as a percentage."""
        if self.speed:
            return self.speed.speed
        return 0

    @property
    def current_preset(self) -> str | None:
        """Current fan preset."""
        if self.preset and self.preset.enabled:
            return self.preset.func_instance
        return None


@dataclass
class FanPut:
    """States that can be updated for a Fan."""

    on: features.OnFeature | None = None
    speed: features.SpeedFeature | None = None
    direction: features.DirectionFeature | None = None
    preset: features.PresetFeature | None = None
