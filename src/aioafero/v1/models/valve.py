"""Representation of an Afero Valve and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Valve(StandardMixin):
    """Representation of an Afero Valve."""

    type: ResourceTypes = ResourceTypes.WATER_TIMER

    open: dict[str | None, features.OpenFeature] = field(default_factory=dict)


@dataclass
class ValvePut:
    """States that can be updated for a Valve."""

    open: features.OpenFeature | None = None
