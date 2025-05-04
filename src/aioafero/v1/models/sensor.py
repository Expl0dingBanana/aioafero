from dataclasses import dataclass, field

MAPPED_SENSORS = [
    "battery-level",
    "output-voltage-switch",
    "watts",
    "wifi-rssi",
]

BINARY_SENSORS = ["error"]


# Sensor -> Issue
BINARY_SENSOR_MAPPING = {
    "error": "alerting",
    "filter-replacement": "replacement-needed",
    "min-temp-exceeded": "alerting",
    "max-temp-exceeded": "alerting",
}

SWITCH_MAPPING = {
    "safety-cool-mode": "on",
    "safety-heat-mode": "on",
}


@dataclass
class AferoSensor:
    id: str
    owner: str
    _value: str | int | float | None

    unit: str | None = field(default=None)
    instance: str | None = field(default=None)

    @property
    def value(self):
        return self._value


@dataclass
class AferoSensorError:
    id: str
    owner: str
    _value: str

    unit: str | None = field(default=None)
    instance: str | None = field(default=None)

    @property
    def value(self) -> bool:
        return self._value == "alerting"

    @value.setter
    def value(self, value):
        self._value = value


@dataclass
class AferoSensorMappedError:
    id: str
    owner: str
    _value: str
    _error: str

    instance: str | None = field(default=None)

    @property
    def value(self) -> bool:
        return self._value == self._error

    @value.setter
    def value(self, value):
        self._value = value
