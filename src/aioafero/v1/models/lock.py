"""Representation of an Afero Lock and its corresponding updates."""

from dataclasses import dataclass

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Lock(StandardMixin):
    """Representation of an Afero Lock."""

    type: ResourceTypes = ResourceTypes.LOCK

    position: features.CurrentPositionFeature | None = None


@dataclass
class LockPut:
    """States that can be updated for a Lock."""

    position: features.CurrentPositionFeature | None = None
