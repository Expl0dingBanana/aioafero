"""Representation of an Afero Portable AC and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .hvac_mixin import HVACMixin
from .resource import ResourceTypes
from .standard_mixin import StandardMixin

mode_checks = {
    "auto-cool": "cool",
}


@dataclass(kw_only=True)
class PortableAC(StandardMixin, HVACMixin):
    """Representation of an Afero Portable AC."""

    type: ResourceTypes = ResourceTypes.PORTABLE_AC

    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None

    @property
    def supports_fan_mode(self) -> bool:
        """Can enable fan-only mode."""
        return False

    def get_mode_to_check(self) -> str | None:
        """Determine the current mode of the thermostat."""
        if not self.hvac_mode:
            return None
        checked_mode = mode_checks.get(self.hvac_mode.mode, self.hvac_mode.mode)
        checked_prev_mode = mode_checks.get(
            self.hvac_mode.previous_mode, self.hvac_mode.previous_mode
        )
        if checked_mode in [
            "cool",
            "heat",
        ]:
            return checked_mode
        if checked_mode in ["dehumidify"]:
            return checked_prev_mode
        return None

    @property
    def supports_temperature_range(self) -> bool:
        """Range which the thermostat will heat / cool."""
        return False


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
