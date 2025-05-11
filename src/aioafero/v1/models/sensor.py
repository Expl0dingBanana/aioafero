from dataclasses import dataclass, field


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
class AferoBinarySensor:
    id: str
    owner: str
    _value: str
    _error: str

    unit: str | None = field(default=None)
    instance: str | None = field(default=None)

    @property
    def value(self) -> bool:
        return self._value == self._error

    @value.setter
    def value(self, value):
        self._value = value
