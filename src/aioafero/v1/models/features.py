"""Feature Schemas used by various Afero resources."""

from dataclasses import dataclass, field
from enum import Enum

from ...util import percentage_to_ordered_list_item


@dataclass
class ColorModeFeature:
    """Represent the current mode (ie white, color) Feature object"""

    mode: str

    @property
    def api_value(self):
        return self.mode


@dataclass
class ColorFeature:
    """Represent `RGB` Feature object"""

    red: int
    green: int
    blue: int

    @property
    def api_value(self):
        return {
            "value": {
                "color-rgb": {
                    "r": self.red,
                    "g": self.green,
                    "b": self.blue,
                }
            }
        }


@dataclass
class ColorTemperatureFeature:
    """Represent Current temperature Feature"""

    temperature: int
    supported: list[int]
    prefix: str | None = None

    @property
    def api_value(self):
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


@dataclass
class CurrentPositionFeature:
    """Represents the current position of the lock"""

    position: CurrentPositionEnum

    @property
    def api_value(self):
        return self.position.value


@dataclass
class CurrentTemperatureFeature:
    """Represents the current temperature"""

    temperature: float
    function_class: str
    function_instance: str | None

    @property
    def api_value(self):
        return {
            "functionClass": self.function_class,
            "functionInstance": self.function_instance,
            "value": round(self.temperature, 1),
        }


@dataclass
class DimmingFeature:
    """Represent Current temperature Feature"""

    brightness: int
    supported: list[int]

    @property
    def api_value(self):
        return self.brightness


@dataclass
class DirectionFeature:
    """Represent Current Fan direction Feature"""

    forward: bool

    @property
    def api_value(self):
        return "forward" if self.forward else "reverse"


@dataclass
class EffectFeature:
    """Represent the current effect"""

    effect: str
    effects: dict[str, set[str]]

    @property
    def api_value(self):
        states = []
        seq_key = None
        for effect_group, effects in self.effects.items():
            if self.effect not in effects:
                continue
            else:
                seq_key = effect_group
                break
        preset_val = self.effect if self.effect in self.effects["preset"] else seq_key
        states.append(
            {
                "functionClass": "color-sequence",
                "functionInstance": "preset",
                "value": preset_val,
            }
        )
        if seq_key != "preset":
            states.append(
                {
                    "functionClass": "color-sequence",
                    "functionInstance": seq_key,
                    "value": self.effect,
                }
            )
        return states

    def is_preset(self, effect):
        try:
            return effect in self.effects["preset"]
        except KeyError:
            return False


@dataclass
class HVACModeFeature:
    """Represent HVAC Mode Feature"""

    mode: str | None
    previous_mode: str | None
    supported_modes: set[str]
    modes: set[str]

    @property
    def api_value(self):
        return self.mode


@dataclass
class ModeFeature:
    """Represent Current Fan mode Feature"""

    mode: str | None
    modes: set[str]

    @property
    def api_value(self):
        return self.mode


@dataclass
class NumbersFeature:
    """Represents a numeric value"""

    value: float
    min: float
    max: float
    step: float
    name: str | None
    unit: str | None

    @property
    def api_value(self):
        return self.value


@dataclass
class OnFeature:
    """Represent `On` Feature object as used by various Afero resources."""

    on: bool
    func_class: str | None = field(default="power")
    func_instance: str | None = field(default=None)

    @property
    def api_value(self):
        state = {
            "value": "on" if self.on else "off",
            "functionClass": self.func_class,
        }
        if self.func_instance:
            state["functionInstance"] = self.func_instance
        return state


@dataclass
class OpenFeature:
    """Represent `Open` Feature object"""

    open: bool
    func_class: str | None = field(default="toggle")
    func_instance: str | None = field(default=None)

    @property
    def api_value(self):
        state = {
            "value": "on" if self.open else "off",
            "functionClass": self.func_class,
        }
        if self.func_instance:
            state["functionInstance"] = self.func_instance
        return state


@dataclass
class PresetFeature:
    """Represent the current preset"""

    enabled: bool
    func_instance: str
    func_class: str

    @property
    def api_value(self):
        return {
            "functionClass": self.func_class,
            "functionInstance": self.func_instance,
            "value": "enabled" if self.enabled else "disabled",
        }


@dataclass
class SelectFeature:
    """Represent available options and currently selected"""

    selected: str
    selects: set[str]
    name: str

    @property
    def api_value(self):
        return self.selected


@dataclass
class SpeedFeature:
    """Represent Current Fan speed Feature"""

    speed: int
    speeds: list[str]

    @property
    def api_value(self):
        return percentage_to_ordered_list_item(self.speeds, self.speed)


@dataclass
class TargetTemperatureFeature:
    """Represents the target temperature for auto"""

    value: float
    min: float
    max: float
    step: float
    instance: str

    @property
    def api_value(self):
        return {
            "functionClass": "temperature",
            "functionInstance": self.instance,
            "value": self.value,
        }


AferoFeatures: list = [
    ColorModeFeature,
    ColorFeature,
    ColorTemperatureFeature,
    CurrentPositionEnum,
    CurrentPositionFeature,
    DimmingFeature,
    DirectionFeature,
    EffectFeature,
    HVACModeFeature,
    ModeFeature,
    NumbersFeature,
    OnFeature,
    OpenFeature,
    PresetFeature,
    SelectFeature,
    SpeedFeature,
    TargetTemperatureFeature,
]
