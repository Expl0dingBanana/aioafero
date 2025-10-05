"""Representation of an Afero Thermostat and its corresponding updates."""

from dataclasses import dataclass

from aioafero.v1.models import features

from .hvac_mixin import HVACMixin
from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Thermostat(StandardMixin, HVACMixin):
    """Representation of an Afero Thermostat."""

    type: ResourceTypes = ResourceTypes.THERMOSTAT

    safety_max_temp: features.TargetTemperatureFeature | None = None
    safety_min_temp: features.TargetTemperatureFeature | None = None

    @property
    def target_temperature_range(self) -> tuple[float, float]:
        """Range which the thermostat supports."""
        return (
            self.target_temperature_auto_heating.value,
            self.target_temperature_auto_cooling.value,
        )

    def get_mode_to_check(self) -> str | None:
        """Determine the current mode of the thermostat."""
        if not self.hvac_mode:
            return None
        if self.hvac_mode.mode in ["cool", "heat"]:
            return self.hvac_mode.mode
        if self.hvac_mode.previous_mode in ["cool", "heat"]:
            return self.hvac_mode.previous_mode
        return None

    @property
    def supports_fan_mode(self) -> bool:
        """Can enable fan-only mode."""
        return self.fan_mode is not None

    @property
    def supports_temperature_range(self) -> bool:
        """Range which the thermostat will heat / cool."""
        if not self.hvac_mode or "auto" not in self.hvac_mode.supported_modes:
            return False
        return (
            self.target_temperature_auto_cooling is not None
            and self.target_temperature_auto_heating is not None
        )


@dataclass
class ThermostatPut:
    """States that can be updated for a Thermostat."""

    fan_mode: features.ModeFeature | None = None
    hvac_mode: features.HVACModeFeature | None = None
    safety_max_temp: features.TargetTemperatureFeature | None = None
    safety_min_temp: features.TargetTemperatureFeature | None = None
    target_temperature_auto_heating: features.TargetTemperatureFeature | None = None
    target_temperature_auto_cooling: features.TargetTemperatureFeature | None = None
    target_temperature_heating: features.TargetTemperatureFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
