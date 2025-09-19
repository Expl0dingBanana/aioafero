"""Representation of an Afero Security System Keypad and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class SecuritySystemKeypad(StandardMixin):
    """Representation of an Afero Security Keypad."""

    type: ResourceTypes = ResourceTypes.SECURITY_SYSTEM_KEYPAD


@dataclass
class SecuritySystemKeypadPut:
    """States that can be updated for a Security System Keypad."""

    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
