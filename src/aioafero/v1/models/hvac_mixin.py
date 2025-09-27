"""Handles generic information related to all HVAC devices."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from aioafero.util import calculate_hubspace_fahrenheit

from . import features


@dataclass(kw_only=True)
class HVACMixin(ABC):
    """Mixin for HVAC properties and methods."""

    display_celsius: bool | None = None
    current_temperature: features.CurrentTemperatureFeature | None = None
    fan_running: bool | None = None
    fan_mode: features.ModeFeature | None = None
    hvac_action: str | None = None
    hvac_mode: features.HVACModeFeature | None = None
    target_temperature_heating: features.TargetTemperatureFeature | None = None
    target_temperature_cooling: features.TargetTemperatureFeature | None = None
    target_temperature_auto_heating: features.TargetTemperatureFeature | None = None
    target_temperature_auto_cooling: features.TargetTemperatureFeature | None = None

    @property
    def target_temperature(self) -> float | None:
        """Temperature which the HVAC will try to achieve."""
        if self.hvac_mode is None or self.hvac_mode.mode not in [
            "cool",
            "heat",
            "fan",
            "off",
            "auto-cool",
        ]:
            return None
        target_feature = self._get_target_feature(self.get_mode_to_check())
        if not target_feature:
            return None
        celsius: float | None = getattr(target_feature, "value", None)
        if self.display_celsius:
            return celsius
        return calculate_hubspace_fahrenheit(celsius)

    @abstractmethod
    def get_mode_to_check(self) -> str | None:
        """Determine the current mode of the thermostat."""

    def _get_target_feature(
        self, mode: str
    ) -> features.TargetTemperatureFeature | None:
        if mode == "cool":
            return getattr(self, "target_temperature_cooling", None)
        if mode == "heat":
            return getattr(self, "target_temperature_heating", None)
        return None

    @property
    def target_temperature_step(self) -> float:
        """Smallest increment for adjusting the temperature."""
        set_mode = self.get_mode_to_check()
        if not set_mode:
            val = 0.5  # Default from Hubspace
        else:
            target_feature = self._get_target_feature(set_mode)
            val = getattr(target_feature, "step", 0.5)
        if self.display_celsius:
            return val
        return 1

    @property
    def target_temperature_max(self) -> float | None:
        """Maximum target temperature."""
        set_mode = self.get_mode_to_check()
        if not set_mode or self.hvac_mode.mode == "auto":
            auto_cooling = getattr(self, "target_temperature_auto_cooling", None)
            val = getattr(auto_cooling, "max", None)
        else:
            target_feature = self._get_target_feature(set_mode)
            val = getattr(target_feature, "max", None)

        if val is None:
            return None

        if self.display_celsius:
            return val
        return calculate_hubspace_fahrenheit(val)

    @property
    def target_temperature_min(self) -> float | None:
        """Minimum target temperature."""
        set_mode = self.get_mode_to_check()
        if not set_mode or self.hvac_mode.mode == "auto":
            auto_heating = getattr(self, "target_temperature_auto_heating", None)
            val = getattr(auto_heating, "min", None)
        else:
            target_feature = self._get_target_feature(set_mode)
            val = getattr(target_feature, "min", None)

        if val is None:
            return None

        if self.display_celsius:
            return val
        return calculate_hubspace_fahrenheit(val)

    @property
    def temperature(self) -> float | None:
        """Current temperature of the selected mode."""
        if self.current_temperature is None:
            return None
        if self.display_celsius:
            return self.current_temperature.temperature
        return calculate_hubspace_fahrenheit(self.current_temperature.temperature)
