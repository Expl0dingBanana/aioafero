"""Representation of an Afero Sensor and its corresponding updates."""

from dataclasses import dataclass, field


@dataclass
class AferoSensor:
    """Sensor that can return any value."""

    id: str
    owner: str
    value: str | int | float | None

    unit: str | None = field(default=None)
    instance: str | None = field(default=None)


@dataclass
class AferoBinarySensor:
    """Sensor that can return True (alerting) or False (normal)."""

    id: str
    owner: str
    current_value: str | int
    _error: str | int

    unit: str | None = field(default=None)
    instance: str | None = field(default=None)

    @property
    def value(self) -> bool:
        """Determine if the binary sensor is in an alert state."""
        return self.current_value == self._error
