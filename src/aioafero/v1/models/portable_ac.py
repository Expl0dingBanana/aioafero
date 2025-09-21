"""Representation of an Afero Portable AC and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.util import calculate_hubspace_fahrenheit
from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class PortableAC(StandardMixin):
    """Representation of an Afero Portable AC."""

    type: ResourceTypes = ResourceTypes.PORTABLE_AC

    display_celsius: bool | None
    current_temperature: features.CurrentTemperatureFeature | None
    hvac_mode: features.HVACModeFeature | None
    target_temperature_cooling: features.TargetTemperatureFeature | None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    @property
    def target_temperature(self) -> float | None:
        """Temperature which the HVAC will try to achieve."""
        if self.display_celsius:
            return self.target_temperature_cooling.value
        return calculate_hubspace_fahrenheit(self.target_temperature_cooling.value)

    @property
    def target_temperature_step(self) -> float:
        """Smallest increment for adjusting the temperature."""
        if self.display_celsius:
            return self.target_temperature_cooling.step
        return 1

    @property
    def target_temperature_max(self) -> float:
        """Maximum target temperature."""
        if self.display_celsius:
            return self.target_temperature_cooling.max
        return calculate_hubspace_fahrenheit(self.target_temperature_cooling.max)

    @property
    def target_temperature_min(self) -> float | None:
        """Minimum target temperature."""
        if self.display_celsius:
            return self.target_temperature_cooling.min
        return calculate_hubspace_fahrenheit(self.target_temperature_cooling.min)

    @property
    def supports_fan_mode(self) -> bool:
        """Can enable fan-only mode."""
        return False

    @property
    def supports_temperature_range(self) -> bool:
        """Range which the thermostat will heat / cool."""
        return False

    @property
    def temperature(self) -> float | None:
        """Current temperature of the selected mode."""
        if self.display_celsius:
            return self.current_temperature.temperature
        return calculate_hubspace_fahrenheit(self.current_temperature.temperature)


@dataclass
class PortableACPut:
    """States that can be updated for a Portable AC."""

    # This feels wrong but based on data dumps, setting timer increases the
    # current temperature by 1 to turn it on
    current_temperature: features.CurrentTemperatureFeature | None = None
    hvac_mode: features.HVACModeFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
