"""Representation of an Afero Security System Sensor (derived) and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class SecuritySystemSensor(StandardMixin):
    """Representation of a security system sensor."""

    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM_SENSOR

    config_key: str | None = None

    # Override the instance property to return an int
    @property
    def instance(self):
        """Instance for the split device."""
        return int(self._id.rsplit(f"-{self.split_identifier}-", 1)[1])


@dataclass
class SecuritySystemSensorPut:
    """States that can be updated for a Security System Sensor."""

    sensor_config: features.SecuritySensorConfigFeature | None = field(
        default_factory=dict, repr=False, init=False
    )
