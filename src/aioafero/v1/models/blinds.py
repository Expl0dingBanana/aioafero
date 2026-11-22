"""Representation of Afero Blinds and their corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class Blinds(StandardMixin):
    """Representation of an Afero Blinds zone.

    A zone moves every blind assigned to it together. ``position`` is 0-100
    where 100 is fully open and 0 is closed.
    """

    type: ResourceTypes = ResourceTypes.BLINDS_ZONE

    position: features.PositionFeature | None = None
    # One-shot functions the zone accepts (``stop-moving``, ``move-coarse``, ...)
    # mapped to their command values
    commands: dict[str, set[str]] = field(default_factory=dict)


@dataclass
class BlindsPut:
    """States that can be updated for Blinds."""

    position: features.PositionFeature | None = None


@dataclass(kw_only=True)
class BlindsGateway(StandardMixin):
    """Representation of an Afero Smart Blinds Gateway.

    The gateway pairs the blinds zones to Wi-Fi. It is read-only: its Wi-Fi state
    is exposed as ``sensors`` for troubleshooting.
    """

    type: ResourceTypes = ResourceTypes.BLINDS_GATEWAY
