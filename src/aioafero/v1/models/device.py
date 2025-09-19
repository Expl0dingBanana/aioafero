"""Representation of a top-level item."""

from dataclasses import dataclass

from .resource import ResourceTypes
from .standard_mixin import StandardMixin


@dataclass
class Device(StandardMixin):
    """Representation of an Afero parent item."""

    type: ResourceTypes = ResourceTypes.PARENT_DEVICE
