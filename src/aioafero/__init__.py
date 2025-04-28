__all__ = [
    "AferoError",
    "InvalidAuth",
    "InvalidResponse",
    "AferoDevice",
    "AferoState",
    "get_afero_device",
    "anonymize_device",
    "anonymize_devices",
    "v1",
    "EventType",
]


from importlib.metadata import PackageNotFoundError, version

try:
    # Change here if project is renamed and does not equal the package name
    dist_name = "aioafero"
    __version__ = version(dist_name)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
finally:
    del version, PackageNotFoundError


from . import v1
from .anonomyize_data import anonymize_device, anonymize_devices
from .device import AferoDevice, AferoState, get_afero_device
from .errors import AferoError, InvalidAuth, InvalidResponse
from .types import EventType
