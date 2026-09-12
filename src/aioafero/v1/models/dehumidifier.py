"""Representation of an Afero Dehumidifier and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Dehumidifier(StandardMixin):
    """Representation of an Afero Dehumidifier."""

    type: ResourceTypes = ResourceTypes.DEHUMIDIFIER

    on: features.OnFeature | None = None
    mode: features.ModeFeature | None = None
    current_humidity: int | None = None
    target_humidity: features.NumbersFeature | None = None


@dataclass
class DehumidifierPut:
    """States that can be updated for a Dehumidifier."""

    on: features.OnFeature | None = None
    mode: features.ModeFeature | None = None
    target_humidity: features.NumbersFeature | None = None
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
