"""Representation of an Afero Security System and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class SecuritySystem(StandardMixin):
    """Representation of an Afero Security Panel."""

    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM

    alarm_state: features.ModeFeature | None = None
    siren_action: features.SecuritySensorSirenFeature | None = None

    @property
    def supports_away(self) -> bool:
        """States if the panel supports away mode."""
        return "arm-away" in self.alarm_state.modes

    @property
    def supports_arm_bypass(self) -> bool:
        """States if the panel supports arm-bypass mode."""
        return False

    @property
    def supports_home(self) -> bool:
        """States if the panel supports home mode."""
        return "arm-stay" in self.alarm_state.modes

    @property
    def supports_night(self) -> bool:
        """States if the panel supports night mode."""
        return False

    @property
    def supports_vacation(self) -> bool:
        """States if the panel supports vacation mode."""
        return False

    @property
    def supports_trigger(self) -> bool:
        """States if the panel supports manually triggering."""
        return "alarming-sos" in self.alarm_state.modes


@dataclass
class SecuritySystemPut:
    """States that can be updated for a Security System."""

    alarm_state: features.ModeFeature | None = None
    siren_action: features.SecuritySensorSirenFeature | None = None
    disarm_pin: features.SecuritySystemDisarmPin | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
