import pytest

from aioafero.v1.models import DeviceInformation, features
from aioafero.v1.models.light import Light, LightChannel


@pytest.fixture
def populated_light():
    return Light(
        _id="entity-1",
        available=True,
        on=features.OnFeature(on=True, function_class="power", function_instance=None),
        color=features.ColorFeature(
            red=10,
            green=20,
            blue=40,
            function_class="color",
            function_instance=None,
        ),
        color_mode=features.ColorModeFeature(
            mode="white", function_class="color-mode", function_instance=None
        ),
        color_modes=["white", "color", "night-light"],
        color_mode_hints={"night-light": ["no-brightness"]},
        color_temperature=features.ColorTemperatureFeature(
            temperature=3000,
            supported=list(range(2700, 5000, 100)),
            prefix="K",
            function_class="color-temperature",
            function_instance=None,
        ),
        dimming=features.DimmingFeature(
            brightness=100,
            supported=list(range(0, 101, 10)),
            function_class="dimming",
            function_instance=None,
        ),
        effect=features.EffectFeature(
            effect="rainbow",
            effects={"custom": {"rainbow"}},
            function_class="color-sequence",
            function_instance="custom",
        ),
        device_information=DeviceInformation(
            model="AL-TP-RGBICTW-1",
            functions=[
                {
                    "functionClass": "preset",
                    "functionInstance": "preset-1",
                    "value": "on",
                    "lastUpdateTime": 0,
                }
            ],
        ),
    )


@pytest.fixture
def empty_light():
    return Light(
        _id="entity-1",
        available=True,
        on=None,
        color=None,
        color_mode=None,
        color_modes=[],
        color_temperature=None,
        dimming=None,
        effect=None,
        device_information=DeviceInformation(
            model="a21-light",
            functions=[
                {
                    "functionClass": "preset",
                    "functionInstance": "preset-1",
                    "value": "on",
                    "lastUpdateTime": 0,
                }
            ],
        ),
    )


def test_init(populated_light):
    assert populated_light.id == "entity-1"
    assert populated_light.available is True
    assert populated_light.on.on is True
    assert populated_light.color.red == 10
    assert populated_light.color_mode.mode == "white"
    assert populated_light.color_temperature.temperature == 3000
    assert populated_light.dimming.brightness == 100
    assert populated_light.effect.effect == "rainbow"
    assert populated_light.supports_on
    assert populated_light.supports_color
    assert populated_light.supports_color_temperature
    assert populated_light.supports_color_white
    assert populated_light.color_mode_has_hint("night-light", "no-brightness")
    assert not populated_light.color_mode_has_hint("white", "no-brightness")
    assert populated_light.supports_dimming
    assert populated_light.supports_effects
    assert populated_light.is_on is True
    populated_light.on = None
    assert not populated_light.supports_on
    assert populated_light.brightness == 100
    assert populated_light.update_id == "entity-1"
    assert populated_light.instance is None
    populated_light._id = "entity-beans-1"
    populated_light.split_identifier = "beans"
    assert populated_light.update_id == "entity"
    assert populated_light.instance == "1"


def test_empty_light(empty_light):
    assert not empty_light.supports_on
    assert not empty_light.supports_color
    assert not empty_light.supports_color_temperature
    assert not empty_light.supports_color_white
    assert not empty_light.color_mode_has_hint("night-light", "no-brightness")
    assert not empty_light.supports_dimming
    assert not empty_light.supports_effects
    assert not empty_light.is_on
    assert not empty_light.brightness
    assert not empty_light.supports_white




def test_dual_channel_helpers():
    """Dual-channel fixtures expose per-driver state via channels."""
    dual = Light(
        _id="dual",
        available=True,
        channels={
            "color": LightChannel(brightness=10, on=True),
            "white": LightChannel(brightness=90, on=False),
        },
    )
    assert dual.is_dual_channel
    assert dual.channel_brightness("color") == 10
    assert dual.channel_brightness("white") == 90
    assert dual.channel_brightness("primary") is None
    assert dual.channel_on("color") is True
    assert dual.channel_on("white") is False
    assert dual.channel_on("missing") is None

    single = Light(_id="single", available=True)
    assert not single.is_dual_channel


def test_feature_for_update_comparison_channel_edges():
    """Channel comparison only remaps toggle/dimming; other fields fall through."""
    dual = Light(
        _id="dual",
        available=True,
        on=features.OnFeature(on=True, function_class="power", function_instance=None),
        dimming=features.DimmingFeature(
            brightness=50,
            supported=[1, 100],
            function_class="brightness",
            function_instance="primary",
        ),
        color_mode=features.ColorModeFeature(
            mode="color", function_class="color-mode", function_instance=None
        ),
        channels={
            "color": LightChannel(brightness=None, on=True),
            "white": LightChannel(brightness=10, on=False),
        },
        device_information=DeviceInformation(),
    )
    # Instance in channels but not a toggle → use primary on.
    powerish = features.OnFeature(on=True, function_class="power", function_instance="color")
    assert dual.feature_for_update_comparison("on", powerish) is dual.on
    # Unknown channel brightness does not suppress.
    dim = features.DimmingFeature(
        brightness=40,
        supported=[1, 100],
        function_class="brightness",
        function_instance="color",
    )
    assert dual.feature_for_update_comparison("dimming", dim) is None
    # Known channel brightness compares semantically.
    dual.channels["color"].brightness = 40
    cached_dim = dual.feature_for_update_comparison("dimming", dim)
    assert cached_dim.brightness == 40
    assert cached_dim.function_instance == "color"
    # Channel instance on a non on/dimming field falls through.
    assert (
        dual.feature_for_update_comparison(
            "color",
            features.OnFeature(on=True, function_class="toggle", function_instance="color"),
        )
        is None
    )
    # Missing dimming feature on the light also does not suppress.
    dual.dimming = None
    assert dual.feature_for_update_comparison("dimming", dim) is None

