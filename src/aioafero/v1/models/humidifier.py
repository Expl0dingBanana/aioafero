"""Representation of an Afero Humidifier and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Humidifier(StandardMixin):
    """Representation of an Afero Humidifier."""

    type: ResourceTypes = ResourceTypes.HUMIDIFIER

    on: features.OnFeature | None = None
    mode: features.ModeFeature | None = None
    current_humidity: int | None = None
    target_humidity: features.NumbersFeature | None = None


@dataclass
class HumidifierPut:
    """States that can be updated for a Humidifier."""

    on: features.OnFeature | None = None
    mode: features.ModeFeature | None = None
    target_humidity: features.NumbersFeature | None = None
    selects: dict[tuple[str, str | None], features.SelectFeature] = field(
        default_factory=dict, repr=False, init=False
    )
