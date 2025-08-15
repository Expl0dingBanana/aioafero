"""Generic/base Resource Model(s)."""

from dataclasses import dataclass
from enum import Enum


class ResourceTypes(Enum):
    """Type of the supported resources."""

    DEVICE = "metadevice.device"
    HOME = "metadata.home"
    ROOM = "metadata.room"
    EXHAUST_FAN = "exhaust-fan"
    FAN = "fan"
    LANDSCAPE_TRANSFORMER = "landscape-transformer"
    LIGHT = "light"
    LOCK = "door-lock"
    PARENT_DEVICE = "parent-device"
    PORTABLE_AC = "portable-air-conditioner"
    POWER_OUTLET = "power-outlet"
    SECURITY_SYSTEM = "security-system"
    SECURITY_SYSTEM_SENSOR = "security-system-sensor"  # Create from device splits
    SWITCH = "switch"
    THERMOSTAT = "thermostat"
    UNKNOWN = "unknown"
    WATER_TIMER = "water-timer"

    @classmethod
    def _missing_(cls: type, value: object):
        """Set default enum member if an unknown value is provided."""
        return ResourceTypes.UNKNOWN


@dataclass
class DeviceInformation:
    """Generic Device Information."""

    device_class: str | None = None
    default_image: str | None = None
    default_name: str | None = None
    manufacturer: str | None = None
    model: str | None = None
    name: str | None = None
    parent_id: str | None = None
    wifi_mac: str | None = None
    ble_mac: str | None = None
    version_data: dict | None = None
