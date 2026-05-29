"""Representation of an Afero Valve and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Valve(StandardMixin):
    """Representation of an Afero Valve.

    ``open`` holds the master ``power`` switch (instance ``None``) and each
    spigot's ``toggle``. Per-spigot ``timer`` and ``max-on-time`` values live in
    the inherited ``numbers`` dict (keyed by ``(functionClass, functionInstance)``)
    and ``battery-level`` lives in the inherited ``sensors`` dict.
    """

    type: ResourceTypes = ResourceTypes.WATER_TIMER

    open: dict[str | None, features.OpenFeature] = field(default_factory=dict)
    rain_delay: features.RainDelayFeature | None = None


@dataclass
class ValvePut:
    """States that can be updated for a Valve."""

    open: features.OpenFeature | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
    rain_delay: features.RainDelayFeature | None = None
