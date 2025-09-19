"""Representation of an Afero Exhaust Fan and its corresponding updates."""

from dataclasses import dataclass, field

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass(kw_only=True)
class ExhaustFan(StandardMixin):
    """Representation of an Afero Exhaust Fan."""

    type: ResourceTypes = ResourceTypes.EXHAUST_FAN


@dataclass
class ExhaustFanPut:
    """States that can be updated for an exhaust fan."""

    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
    selects: dict[tuple[str, str | None], features.SelectFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
