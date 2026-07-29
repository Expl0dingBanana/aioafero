import pytest

from aioafero.v1.models import DeviceInformation, features
from aioafero.v1.models.fan import Fan


@pytest.fixture
def populated_fan():
    return Fan(
        _id="fan-1",
        available=True,
        on=features.OnFeature(on=True, function_class="power", function_instance=None),
        speed=features.SpeedFeature(
            speed=50,
            speeds=[25, 50, 75, 100],
            function_class="fan-speed",
            function_instance=None,
        ),
        direction=features.DirectionFeature(
            forward=True, function_class="direction", function_instance=None
        ),
        preset=features.PresetFeature(
            enabled=True,
            function_class="preset",
            function_instance="preset-1",
        ),
        device_information=DeviceInformation(
            functions=[
                {
                    "functionClass": "preset",
                    "functionInstance": "preset-1",
                    "value": "on",
                    "lastUpdateTime": 0,
                }
            ]
        ),
    )


@pytest.fixture
def empty_fan():
    return Fan(
        _id="fan-1",
        available=True,
        on=None,
        speed=None,
        direction=None,
        preset=None,
    )


def test_init(populated_fan):
    assert populated_fan.id == "fan-1"
    assert populated_fan.available is True
    assert populated_fan.on.on is True
    assert populated_fan.speed.speed == 50
    assert populated_fan.direction.forward is True
    assert populated_fan.preset.enabled is True
    assert populated_fan.is_on is True
    populated_fan.on.on = False
    assert populated_fan.is_on is False
    assert populated_fan.current_direction is True
    assert populated_fan.current_speed == 50
    assert populated_fan.current_preset == "preset-1"
    populated_fan.preset.enabled = False
    assert populated_fan.current_preset is None


def test_empty_fan(empty_fan):
    assert not empty_fan.supports_presets
    assert not empty_fan.current_preset
    assert not empty_fan.supports_speed
    assert not empty_fan.current_speed
    assert not empty_fan.supports_direction
    assert not empty_fan.current_direction
    assert not empty_fan.supports_on
    assert not empty_fan.is_on


@pytest.mark.parametrize(
    "has_feature",
    [True, False],
)
def test_supports_direction(has_feature, populated_fan):
    if not has_feature:
        populated_fan.direction = None
    assert populated_fan.supports_direction == has_feature


@pytest.mark.parametrize(
    "has_feature",
    [True, False],
)
def test_supports_on(has_feature, populated_fan):
    if not has_feature:
        populated_fan.on = None
    assert populated_fan.supports_on == has_feature


@pytest.mark.parametrize(
    "has_feature",
    [True, False],
)
def test_supports_presets(has_feature, populated_fan):
    if not has_feature:
        populated_fan.preset = None
    assert populated_fan.supports_presets == has_feature


@pytest.mark.parametrize(
    "has_feature",
    [True, False],
)
def test_supports_speed(has_feature, populated_fan):
    if not has_feature:
        populated_fan.speed = None
    assert populated_fan.supports_speed == has_feature
