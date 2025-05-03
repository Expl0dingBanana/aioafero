import pytest

from aioafero.v1.models import features
from aioafero.v1.models.light import Light


@pytest.fixture
def populated_light():
    return Light(
        [
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ],
        id="entity-1",
        available=True,
        on=features.OnFeature(on=True),
        color=features.ColorFeature(red=10, green=20, blue=40),
        color_mode=features.ColorModeFeature(mode="white"),
        color_modes=["white", "color"],
        color_temperature=features.ColorTemperatureFeature(
            temperature=3000, supported=list(range(2700, 5000, 100)), prefix="K"
        ),
        dimming=features.DimmingFeature(
            brightness=100, supported=list(range(0, 101, 10))
        ),
        effect=features.EffectFeature(
            effect="rainbow", effects={"custom": {"rainbow"}}
        ),
        instances="i dont execute",
    )


@pytest.fixture
def empty_light():
    return Light(
        [
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ],
        id="entity-1",
        available=True,
        on=None,
        color=None,
        color_mode=None,
        color_modes=[],
        color_temperature=None,
        dimming=None,
        effect=None,
        instances="i dont execute",
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
    assert populated_light.instances == {"preset": "preset-1"}
    assert populated_light.supports_on
    assert populated_light.supports_color
    assert populated_light.supports_color_temperature
    assert populated_light.supports_color_white
    assert populated_light.supports_dimming
    assert populated_light.supports_effects
    assert populated_light.is_on is True
    populated_light.on = None
    assert not populated_light.supports_on
    assert populated_light.brightness == 100


def test_empty_light(empty_light):
    assert not empty_light.supports_on
    assert not empty_light.supports_color
    assert not empty_light.supports_color_temperature
    assert not empty_light.supports_color_white
    assert not empty_light.supports_dimming
    assert not empty_light.supports_effects
    assert not empty_light.is_on
    assert not empty_light.brightness


def test_get_instance(populated_light):
    assert populated_light.get_instance("preset") == "preset-1"
