"""Feature Schemas used by various Afero resources."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from aioafero.util import percentage_to_ordered_list_item


@dataclass
class ColorModeFeature:
    """Represent the current mode (ie white, color) Feature object."""

    mode: str

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.mode


@dataclass
class ColorFeature:
    """Represent `RGB` Feature object."""

    red: int
    green: int
    blue: int

    @property
    def api_value(self):
        """Value to send to Afero API."""
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
    """Represent Current temperature Feature."""

    temperature: int
    supported: list[int]
    prefix: str | None = None

    @property
    def api_value(self):
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


@dataclass
class CurrentPositionFeature:
    """Represents the current position of the lock."""

    position: CurrentPositionEnum

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.position.value


@dataclass
class CurrentTemperatureFeature:
    """Represents the current temperature."""

    temperature: float
    function_class: str
    function_instance: str | None

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return {
            "functionClass": self.function_class,
            "functionInstance": self.function_instance,
            "value": round(self.temperature, 1),
        }


@dataclass
class DimmingFeature:
    """Represent Current temperature Feature."""

    brightness: int
    supported: list[int]

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.brightness


@dataclass
class DirectionFeature:
    """Represent Current Fan direction Feature."""

    forward: bool

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return "forward" if self.forward else "reverse"


@dataclass
class EffectFeature:
    """Represent the current effect."""

    effect: str
    effects: dict[str, set[str]]

    @property
    def api_value(self):
        """States to send to Afero API."""
        states = []
        seq_key = None
        for effect_group, effects in self.effects.items():
            if self.effect not in effects:
                continue
            seq_key = effect_group
            break
        if seq_key is None:
            return []
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
        """Determine if the current state is a preset effect."""
        try:
            return effect in self.effects["preset"]
        except KeyError:
            return False


@dataclass
class HVACModeFeature:
    """Represent HVAC Mode Feature."""

    mode: str | None
    previous_mode: str | None
    supported_modes: set[str]
    modes: set[str]

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.mode


@dataclass
class ModeFeature:
    """Represent Current Fan mode Feature."""

    mode: str | None
    modes: set[str]

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.mode


@dataclass
class NumbersFeature:
    """Represents a numeric value."""

    value: float
    min: float
    max: float
    step: float
    name: str | None
    unit: str | None

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.value


@dataclass
class OnFeature:
    """Represent `On` Feature object as used by various Afero resources."""

    on: bool
    func_class: str | None = field(default="power")
    func_instance: str | None = field(default=None)

    @property
    def api_value(self):
        """Value to send to Afero API."""
        state = {
            "value": "on" if self.on else "off",
            "functionClass": self.func_class,
        }
        if self.func_instance:
            state["functionInstance"] = self.func_instance
        return state


@dataclass
class OpenFeature:
    """Represent `Open` Feature object."""

    open: bool
    func_class: str | None = field(default="toggle")
    func_instance: str | None = field(default=None)

    @property
    def api_value(self):
        """Value to send to Afero API."""
        state = {
            "value": "on" if self.open else "off",
            "functionClass": self.func_class,
        }
        if self.func_instance:
            state["functionInstance"] = self.func_instance
        return state


@dataclass
class RainDelayFeature:
    """Represent the rain-delay / schedule-pause state of a water timer.

    Two wire states feed this single feature:
      * `schedule-pause` @ `active` (category `on`/`off`) -- whether a pause is
        currently in effect.
      * `schedule-pause` @ `rain-delay` (object) -- the configured pause windows,
        wrapped as ``{"schedule-pause-time-array": {"schedulePauseTimeArray": [...]}}``.

    ``active`` and ``pauses`` are read from the device (``active`` is a
    device-computed status: whether now falls inside a window). To WRITE a timed
    pause (rain delay), set ``pause_windows`` to a list of window entries built
    with :meth:`pause_window`; ``api_value`` then emits both the window array and
    the ``active`` mirror. ``pause_windows=[]`` clears the rain delay.
    """

    active: bool
    pauses: list[Any] = field(default_factory=list)
    # Windows to WRITE (None = emit only the active toggle; [] = clear).
    pause_windows: list[dict] | None = None

    @staticmethod
    def pause_window(start_epoch: int, end_epoch: int, *, flags: int = 0, version: int = 1) -> dict:
        """Build one pause-window entry (times in epoch SECONDS)."""
        return {
            "version": version,
            "flags": flags,
            "startTime": int(start_epoch),
            "endTime": int(end_epoch),
        }

    @property
    def api_value(self):
        """Value(s) to send to Afero API."""
        if self.pause_windows is None:
            # Plain active toggle (legacy behavior).
            return {
                "functionClass": "schedule-pause",
                "functionInstance": "active",
                "value": "on" if self.active else "off",
            }
        # Write the window array plus the active mirror (empty list = clear).
        return [
            {
                "functionClass": "schedule-pause",
                "functionInstance": "active",
                "value": "on" if self.pause_windows else "off",
            },
            {
                "functionClass": "schedule-pause",
                "functionInstance": "rain-delay",
                "value": {
                    "schedule-pause-time-array": {
                        "schedulePauseTimeArray": list(self.pause_windows)
                    }
                },
            },
        ]


@dataclass
class PresetFeature:
    """Represent the current preset."""

    enabled: bool
    func_instance: str
    func_class: str

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return {
            "functionClass": self.func_class,
            "functionInstance": self.func_instance,
            "value": "enabled" if self.enabled else "disabled",
        }


@dataclass
class SecuritySensorConfigFeature:
    """Represent the current security sensor configuration."""

    sensor_id: int
    chirpMode: int  # noqa: N815
    triggerType: int  # noqa: N815
    bypassType: int  # noqa: N815
    key_name: str

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return {
            "functionClass": "sensor-config",
            "value": {
                self.key_name: {
                    "chirpMode": self.chirpMode,
                    "triggerType": self.triggerType,
                    "bypassType": self.bypassType,
                }
            },
            "functionInstance": f"sensor-{self.sensor_id}",
        }


@dataclass
class SelectFeature:
    """Represent available options and currently selected."""

    selected: str
    selects: set[str]
    name: str

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return self.selected


@dataclass
class SecuritySystemDisarmPin:
    """Represent the disarm pin feature."""

    pin: int

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return {
            "functionClass": "disarm",
            "functionInstance": None,
            "value": str(self.pin),
        }


@dataclass
class SecuritySensorSirenFeature:
    """Represent the current state of the siren."""

    result_code: int | None
    command: int | None

    @property
    def api_value(self):
        """Value to send to Afero API."""
        if self.result_code is None and self.command is None:
            return {
                "functionClass": "siren-action",
                "value": None,
                "functionInstance": None,
            }
        return {
            "functionClass": "siren-action",
            "value": {
                "security-siren-action": {
                    "resultCode": self.result_code,
                    "command": self.command,
                }
            },
            "functionInstance": None,
        }


@dataclass
class SpeedFeature:
    """Represent Current Fan speed Feature."""

    speed: int
    speeds: list[str]

    @property
    def api_value(self):
        """Value to send to Afero API."""
        return percentage_to_ordered_list_item(self.speeds, self.speed)


@dataclass
class TargetTemperatureFeature:
    """Represents the target temperature for auto."""

    value: float
    min: float
    max: float
    step: float
    instance: str

    @property
    def api_value(self):
        """Value to send to Afero API."""
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
    RainDelayFeature,
    PresetFeature,
    SelectFeature,
    SpeedFeature,
    TargetTemperatureFeature,
]
