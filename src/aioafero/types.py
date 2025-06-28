from enum import Enum


class EventType(Enum):
    """Enum with possible Events."""

    RESOURCE_ADDED = "add"
    RESOURCE_UPDATED = "update"
    RESOURCE_DELETED = "delete"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTED = "reconnected"
    INVALID_AUTH = "invalid_auth"
    POLLED_DATA = "polled_data"
    POLLED_DEVICES = "polled_devices"
