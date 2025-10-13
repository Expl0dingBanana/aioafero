"""Types used by the bridge and supporting elements."""

from enum import Enum
from typing import TypedDict


class EventType(Enum):
    """Enum with possible Events."""

    RESOURCE_ADDED = "add"
    RESOURCE_UPDATED = "update"
    RESOURCE_DELETED = "delete"
    RESOURCE_VERSION = "version"
    RESOURCE_UPDATE_RESPONSE = "update_response"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTED = "reconnected"
    INVALID_AUTH = "invalid_auth"
    POLLED_DATA = "polled_data"
    POLLED_DEVICES = "polled_devices"


class TemperatureUnit(Enum):
    """Temperature unit enum."""

    CELSIUS = "celsius"
    FAHRENHEIT = "fahrenheit"


class AferoRoom(TypedDict):
    """TypedDict for Afero Room."""

    id: str
    name: str
    children: list[str]
