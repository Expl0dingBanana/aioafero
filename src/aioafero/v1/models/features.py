"""Feature Schemas used by various Afero resources."""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from aioafero.util import percentage_to_ordered_list_item


@dataclass(frozen=True, slots=True)
class AferoValueEmission:
    """One outbound Afero state derived from a feature."""

    function_class: str
    function_instance: str | None
    value: Any


@dataclass(kw_only=True)
class AferoFeature:
    """Base feature with required Afero function identity."""

    function_class: str
    function_instance: str | None

    @property
    def api_value(self) -> Any:
        """Value member to send to the Afero API."""
        raise NotImplementedError

    def iter_afero_values(self) -> list[AferoValueEmission]:
        """Return outbound states owned by this feature."""
        return [
            AferoValueEmission(
                self.function_class,
                self.function_instance,
                self.api_value,
            )
        ]


@dataclass(kw_only=True)
class ColorModeFeature(AferoFeature):
    """Represent the current mode (ie white, color) Feature object."""

    mode: str

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return self.mode


@dataclass(kw_only=True)
class ColorFeature(AferoFeature):
    """Represent `RGB` Feature object."""

    red: int
    green: int
    blue: int

    @property
    def api_value(self) -> dict[str, dict[str, int]]:
        """Value to send to Afero API."""
        return {
            "color-rgb": {
                "r": self.red,
                "g": self.green,
                "b": self.blue,
            }
        }


@dataclass(kw_only=True)
class ColorTemperatureFeature(AferoFeature):
    """Represent Current temperature Feature."""

    temperature: int
    supported: list[int]
    prefix: str = ""

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return f"{self.temperature}{self.prefix}"


class CurrentPositionEnum(Enum):
    """Enum with available current position modes."""

    LOCKED = "locked"
    LOCKING = "locking"
    UNKNOWN = "unknown"
    UNLOCKED = "unlocked"
    UNLOCKING = "unlocking"

    @classmethod
    def _missing_(cls, value):
        return cls.UNKNOWN


@dataclass(kw_only=True)
class CurrentPositionFeature(AferoFeature):
    """Represents the current position of the lock."""

    position: CurrentPositionEnum

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return self.position.value


@dataclass(kw_only=True)
class CurrentTemperatureFeature(AferoFeature):
    """Represents the current temperature."""

    temperature: float

    @property
    def api_value(self) -> float:
        """Value to send to Afero API."""
        return round(self.temperature, 1)


@dataclass(kw_only=True)
class DimmingFeature(AferoFeature):
    """Represent Current temperature Feature."""

    brightness: int
    supported: list[int]

    @property
    def api_value(self) -> int:
        """Value to send to Afero API."""
        return self.brightness


@dataclass(kw_only=True)
class DirectionFeature(AferoFeature):
    """Represent Current Fan direction Feature."""

    forward: bool

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return "forward" if self.forward else "reverse"


@dataclass(kw_only=True)
class EffectFeature(AferoFeature):
    """Represent the current effect."""

    effect: str
    effects: dict[str, set[str]]

    @property
    def api_value(self) -> str:
        """Canonical effect value; multi-state emission uses ``iter_afero_values``."""
        return self.effect

    def iter_afero_values(self) -> list[AferoValueEmission]:
        """Emit ordered color-sequence states for the selected effect."""
        seq_key = next(
            (
                effect_group
                for effect_group, effects in self.effects.items()
                if self.effect in effects
            ),
            None,
        )
        if seq_key is None:
            return []
        preset_val = self.effect if self.is_preset(self.effect) else seq_key
        states = [
            AferoValueEmission(self.function_class, "preset", preset_val),
        ]
        if seq_key != "preset":
            states.append(AferoValueEmission(self.function_class, seq_key, self.effect))
        return states

    def is_preset(self, effect: str) -> bool:
        """Determine if the current state is a preset effect."""
        return effect in self.effects.get("preset", ())


@dataclass(kw_only=True)
class HVACModeFeature(AferoFeature):
    """Represent HVAC Mode Feature."""

    mode: str | None
    previous_mode: str | None
    supported_modes: set[str]
    modes: set[str]

    @property
    def api_value(self) -> str | None:
        """Value to send to Afero API."""
        return self.mode


@dataclass(kw_only=True)
class ModeFeature(AferoFeature):
    """Represent Current Fan mode Feature."""

    mode: str | None
    modes: set[str]

    @property
    def api_value(self) -> str | None:
        """Value to send to Afero API."""
        return self.mode


@dataclass(kw_only=True)
class NumbersFeature(AferoFeature):
    """Represents a numeric value."""

    value: float
    min: float
    max: float
    step: float
    name: str | None
    unit: str | None

    @property
    def api_value(self) -> float:
        """Value to send to Afero API."""
        return self.value


@dataclass(kw_only=True)
class OnFeature(AferoFeature):
    """Represent `On` Feature object as used by various Afero resources."""

    on: bool

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return "on" if self.on else "off"


@dataclass(kw_only=True)
class OpenFeature(AferoFeature):
    """Represent `Open` Feature object."""

    open: bool

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return "on" if self.open else "off"


@dataclass(kw_only=True)
class PresetFeature(AferoFeature):
    """Represent the current preset."""

    enabled: bool

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return "enabled" if self.enabled else "disabled"


@dataclass(kw_only=True)
class SecuritySensorConfigFeature(AferoFeature):
    """Represent the current security sensor configuration."""

    sensor_id: int
    chirpMode: int  # noqa: N815
    triggerType: int  # noqa: N815
    bypassType: int  # noqa: N815
    key_name: str

    @property
    def api_value(self) -> dict[str, dict[str, int]]:
        """Value to send to Afero API."""
        return {
            self.key_name: {
                "chirpMode": self.chirpMode,
                "triggerType": self.triggerType,
                "bypassType": self.bypassType,
            }
        }


@dataclass(kw_only=True)
class SelectFeature(AferoFeature):
    """Represent available options and currently selected."""

    selected: str
    selects: set[str]
    name: str

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return self.selected


@dataclass(kw_only=True)
class SecuritySystemDisarmPin(AferoFeature):
    """Represent the disarm pin feature."""

    pin: int

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return str(self.pin)


@dataclass(kw_only=True)
class SecuritySensorSirenFeature(AferoFeature):
    """Represent the current state of the siren."""

    result_code: int | None
    command: int | None

    @property
    def api_value(self) -> dict[str, dict[str, int | None]] | None:
        """Value to send to Afero API."""
        if self.result_code is None and self.command is None:
            return None
        return {
            "security-siren-action": {
                "resultCode": self.result_code,
                "command": self.command,
            }
        }


@dataclass(kw_only=True)
class SpeedFeature(AferoFeature):
    """Represent Current Fan speed Feature."""

    speed: int
    speeds: list[str]

    @property
    def api_value(self) -> str:
        """Value to send to Afero API."""
        return percentage_to_ordered_list_item(self.speeds, self.speed)


@dataclass(kw_only=True)
class TargetTemperatureFeature(AferoFeature):
    """Represents the target temperature for auto."""

    value: float
    min: float
    max: float
    step: float

    @property
    def api_value(self) -> float:
        """Value to send to Afero API."""
        return self.value
