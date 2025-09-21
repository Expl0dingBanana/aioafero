"""Representation of an Afero Switch and its corresponding updates."""

from dataclasses import dataclass

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Switch(StandardMixin):
    """Representation of an Afero Switch."""

    type: ResourceTypes = ResourceTypes.SWITCH

    on: dict[str | None, features.OnFeature] | None = None


@dataclass
class SwitchPut:
    """States that can be updated for a Switch."""

    on: features.OnFeature | None = None
