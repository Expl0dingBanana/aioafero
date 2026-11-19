"""Representation of an Afero roller shade and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Blind(StandardMixin):
    """Representation of one roller shade (a zone on a blinds gateway).

    ``position`` runs from ``position.min`` (fully closed) to ``position.max``
    (fully open). ``commands`` maps each one-shot function class the shade
    accepts (``stop-moving``, ``move-coarse``, ...) to its command values.
    """

    type: ResourceTypes = ResourceTypes.BLINDS_ZONE

    position: features.PositionFeature | None = None
    commands: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class BlindPut:
    """States that can be updated for a Blind."""

    position: features.PositionFeature | None = None
