"""aioafero API."""

__all__ = [
    "AferoCapability",
    "AferoDevice",
    "AferoError",
    "AferoState",
    "EventType",
    "InvalidAuth",
    "InvalidOTP",
    "InvalidResponse",
    "OTPError",
    "OTPRequired",
    "SecuritySystemError",
    "TemperatureUnit",
    "anonymize_device",
    "anonymize_devices",
    "get_afero_device",
    "v1",
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
from .device import AferoCapability, AferoDevice, AferoState, get_afero_device
from .errors import (
    AferoError,
    InvalidAuth,
    InvalidOTP,
    InvalidResponse,
    OTPError,
    OTPRequired,
    SecuritySystemError,
)
from .types import EventType, TemperatureUnit
