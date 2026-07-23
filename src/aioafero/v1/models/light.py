"""Representation of an Afero Light and its corresponding updates."""

from dataclasses import dataclass, field
import re

from aioafero.v1.models import features

from .resource import ResourceTypes
from .standard_mixin import StandardMixin

rgbw_name_search = re.compile(r"RGB\w*W")


@dataclass
class LightChannel:
    """Per-channel brightness/on for a dual-channel light."""

    brightness: int | None = None
    on: bool | None = None


@dataclass(kw_only=True)
class Light(StandardMixin):
    """Representation of an Afero Light."""

    type: ResourceTypes = ResourceTypes.LIGHT

    on: features.OnFeature | None = None
    color: features.ColorFeature | None = None
    color_mode: features.ColorModeFeature | None = None
    color_modes: list[str] | None = None
    color_mode_hints: dict[str, list[str]] | None = None
    color_temperature: features.ColorTemperatureFeature | None = None
    dimming: features.DimmingFeature | None = None
    effect: features.EffectFeature | None = None
    supports_white: bool = False
    channels: dict[str, LightChannel] = field(default_factory=dict)

    def __post_init__(self):
        """Determine if white only is supported."""
        super().__post_init__()
        model = getattr(getattr(self, "device_information", None), "model", None)
        if model is not None and rgbw_name_search.search(model):
            self.supports_white = True

    @property
    def supports_color(self) -> bool:
        """Return if this light supports color control."""
        return self.color is not None

    @property
    def supports_color_temperature(self) -> bool:
        """Return if this light supports color_temperature control."""
        return self.color_temperature is not None

    @property
    def supports_color_white(self) -> bool:
        """Return if this light supports setting white."""
        return self.color_modes is not None and "white" in self.color_modes

    def color_mode_has_hint(self, mode: str, hint: str) -> bool:
        """Return True when ``mode`` carries the given API category hint."""
        if not self.color_mode_hints:
            return False
        return hint in self.color_mode_hints.get(mode, [])

    @property
    def supports_dimming(self) -> bool:
        """Return if this light supports brightness control."""
        return self.dimming is not None

    @property
    def supports_effects(self) -> bool:
        """Return if this light supports brightness control."""
        return self.effect is not None

    @property
    def supports_on(self):
        """If the light can be toggled on or off."""
        return self.on is not None

    @property
    def is_on(self) -> bool:
        """Return bool if light is currently powered on."""
        if self.on is not None:
            return self.on.on
        return False

    @property
    def brightness(self) -> float:
        """Return current brightness of light."""
        if self.dimming is not None:
            return self.dimming.brightness
        return 100.0 if self.is_on else 0.0

    @property
    def is_dual_channel(self) -> bool:
        """Return True when color and white channels are both present."""
        return {"color", "white"}.issubset(self.channels)

    def channel_brightness(self, channel: str) -> float | None:
        """Return brightness for a channel, if known."""
        entry = self.channels.get(channel)
        if entry is None or entry.brightness is None:
            return None
        return float(entry.brightness)

    def channel_on(self, channel: str) -> bool | None:
        """Return on/off for a channel toggle, if known."""
        entry = self.channels.get(channel)
        if entry is None:
            return None
        return entry.on

    def feature_for_update_comparison(
        self, field_name: str, put_feature: object | None
    ) -> object | None:
        """Compare channel toggles/dimming against ``channels``, not primary."""
        instance = getattr(put_feature, "func_instance", None) if put_feature else None
        # Primary power/dimming often use func_instance=None; never treat that as a channel.
        if not instance or instance not in self.channels:
            return super().feature_for_update_comparison(field_name, put_feature)
        channel = self.channels[instance]
        if field_name == "on":
            # Dual-channel power uses toggle/<color|white>, not primary power.
            if getattr(put_feature, "func_class", None) != "toggle":
                return super().feature_for_update_comparison(field_name, put_feature)
            if channel.on is None:
                # Unknown channel state: do not suppress (caller may still PUT).
                return None
            return features.OnFeature(
                on=channel.on,
                func_class="toggle",
                func_instance=instance,
            )
        if field_name == "dimming":
            if channel.brightness is None or self.dimming is None:
                # Unknown channel brightness: do not suppress.
                return None
            return features.DimmingFeature(
                brightness=channel.brightness,
                # Required by the dataclass; features_equivalent_for_update ignores it.
                supported=self.dimming.supported,
                func_instance=instance,
            )
        return super().feature_for_update_comparison(field_name, put_feature)


@dataclass
class LightPut[AferoResource]:
    """States that can be updated for a light."""

    on: features.OnFeature | None = None
    color: features.ColorFeature | None = None
    color_mode: features.ColorModeFeature | None = None
    color_temperature: features.ColorTemperatureFeature | None = None
    dimming: features.DimmingFeature | None = None
    effect: features.EffectFeature | None = None
    numbers: dict[tuple[str, str | None], features.NumbersFeature] | None = field(
        default_factory=dict, repr=False, init=False
    )
