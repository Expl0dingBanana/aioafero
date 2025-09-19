"""Representation of an Afero Portable AC and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .hvac_mixin import HVACMixin
from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class PortableAC(HVACMixin, StandardMixin):
    """Representation of an Afero Portable AC."""

    type: ResourceTypes = ResourceTypes.PORTABLE_AC

    @property
    def supports_fan_mode(self) -> bool:
        """Can enable fan-only mode."""
        return False

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
