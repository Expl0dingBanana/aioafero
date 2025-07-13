"""Errors used through aioafero."""


class AferoError(Exception):
    """Generic exception for Afero API or the responses."""


class DeviceNotFound(AferoError):
    """Device not found within the controller."""


class DeviceUpdateError(AferoError):
    """Unable to send a device update to Afero API."""


class ExceededMaximumRetries(AferoError):
    """Maximum retries exceeded when contacting Afero API."""


class InvalidAuth(AferoError):
    """Invalid credentials supplied during authentication."""


class InvalidResponse(AferoError):
    """An invalid response was received from Afero API."""
