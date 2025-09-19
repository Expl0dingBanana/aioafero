"""Representation of an Afero Thermostat and its corresponding updates."""

from dataclasses import dataclass

from aioafero.v1.models import features

from .hvac_mixin import HVACMixin
from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Thermostat(HVACMixin, StandardMixin):
    """Representation of an Afero Thermostat."""

    type: ResourceTypes = ResourceTypes.THERMOSTAT

    hvac_action: str | None = None
    safety_max_temp: features.TargetTemperatureFeature | None = None
    safety_min_temp: features.TargetTemperatureFeature | None = None


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
