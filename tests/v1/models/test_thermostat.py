import pytest

from aioafero.v1.models import features
from aioafero.v1.models.thermostat import Thermostat


@pytest.fixture
def populated_entity():
    return Thermostat(
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
        display_celsius=True,
        current_temperature=features.CurrentTemperatureFeature(
            temperature=12,
            function_class="temperature",
            function_instance="current-temp",
        ),
        fan_running=False,
        fan_mode=features.ModeFeature(mode="off", modes={"on", "off"}),
        hvac_action="off",
        hvac_mode=features.HVACModeFeature(
            mode="heat",
            previous_mode="heat",
            modes={"off", "heat", "auto", "fan", "cool"},
            supported_modes={"off", "heat", "auto", "fan", "cool"},
        ),
        safety_max_temp=features.TargetTemperatureFeature(
            value=36, step=0.5, min=29.5, max=37, instance="safety-mode-max-temp"
        ),
        safety_min_temp=features.TargetTemperatureFeature(
            value=4, step=0.5, min=4, max=13, instance="safety-mode-min-temp"
        ),
        target_temperature_auto_heating=features.TargetTemperatureFeature(
            value=18, step=0.5, min=4, max=32, instance="auto-heating-target"
        ),
        target_temperature_auto_cooling=features.TargetTemperatureFeature(
            value=26.5, step=0.5, min=4, max=32, instance="auto-cooling-target"
        ),
        target_temperature_heating=features.TargetTemperatureFeature(
            value=19, step=0.5, min=4, max=32, instance="heating-target"
        ),
        target_temperature_cooling=features.TargetTemperatureFeature(
            value=26, step=0.5, min=10, max=37, instance="cooling-target"
        ),
        instances="i dont execute",
    )


@pytest.fixture
def empty_entity():
    return Thermostat(
        [],
        id="entity-1",
        available=True,
        display_celsius=None,
        current_temperature=None,
        fan_mode=None,
        hvac_action=None,
        hvac_mode=None,
        safety_max_temp=None,
        safety_min_temp=None,
        target_temperature_auto_heating=None,
        target_temperature_auto_cooling=None,
        target_temperature_heating=None,
        target_temperature_cooling=None,
        instances="i dont execute",
    )


@pytest.mark.parametrize(
    "mode,prev_mode,expected",
    [
        ("cool", "cool", "cool"),
        ("heat", "heat", "heat"),
        ("off", "cool", "cool"),
        ("off", "heat", "heat"),
        ("auto", "cool", "cool"),
        ("auto", "heat", "heat"),
    ],
)
def test__get_mode_to_check(mode, prev_mode, expected, populated_entity):
    populated_entity.hvac_mode.mode = mode
    populated_entity.hvac_mode.previous_mode = prev_mode
    assert populated_entity.get_mode_to_check() == expected


def test__get_mode_to_not_populated(populated_entity):
    populated_entity.hvac_mode = None
    assert populated_entity.get_mode_to_check() is None


def test_target_temperature_step_not_populated(populated_entity):
    populated_entity.hvac_mode = None
    assert populated_entity.target_temperature_step == 0.5


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.current_temperature == features.CurrentTemperatureFeature(
        temperature=12,
        function_class="temperature",
        function_instance="current-temp",
    )
    assert populated_entity.fan_mode.mode == "off"
    assert populated_entity.hvac_action == "off"
    assert populated_entity.hvac_mode.mode == "heat"
    assert populated_entity.safety_max_temp.value == 36
    assert populated_entity.safety_max_temp.instance == "safety-mode-max-temp"
    assert populated_entity.safety_min_temp.value == 4
    assert populated_entity.safety_min_temp.instance == "safety-mode-min-temp"
    assert populated_entity.target_temperature_auto_heating.value == 18
    assert populated_entity.target_temperature_auto_heating.step == 0.5
    assert populated_entity.target_temperature_auto_heating.min == 4
    assert populated_entity.target_temperature_auto_heating.max == 32
    assert (
        populated_entity.target_temperature_auto_heating.instance
        == "auto-heating-target"
    )
    # Property checks
    assert populated_entity.target_temperature == 19
    assert populated_entity.target_temperature_max == 32
    assert populated_entity.target_temperature_min == 4
    assert populated_entity.target_temperature_step == 0.5
    assert populated_entity.temperature == 12
    populated_entity.hvac_mode.mode = "auto"
    assert populated_entity.target_temperature is None
    assert populated_entity.target_temperature_max == 32
    assert populated_entity.target_temperature_min == 4
    assert populated_entity.target_temperature_step == 0.5
    assert populated_entity.target_temperature_range == (
        18,
        26.5,
    )
    assert populated_entity.supports_fan_mode
    assert populated_entity.supports_temperature_range
    populated_entity.hvac_mode.mode = "cool"
    assert populated_entity.target_temperature == 26
    assert populated_entity.target_temperature_max == 37
    assert populated_entity.target_temperature_min == 10
    assert populated_entity.target_temperature_step == 0.5
    populated_entity.hvac_mode.mode = "off"
    populated_entity.hvac_mode.previous_mode = "cool"
    assert populated_entity.target_temperature == 26
    assert populated_entity.target_temperature_max == 37
    assert populated_entity.target_temperature_min == 10
    assert populated_entity.target_temperature_step == 0.5
    populated_entity.hvac_mode.previous_mode = "heat"
    assert populated_entity.target_temperature == 19
    populated_entity.hvac_mode.previous_mode = "i-dont-exist"
    assert populated_entity.target_temperature is None
    # Test F
    populated_entity.display_celsius = False
    populated_entity.hvac_mode.mode = "auto"
    assert populated_entity.target_temperature_range == (
        64,
        80,
    )
    assert populated_entity.target_temperature_step == 1
    assert populated_entity.target_temperature_max == 90
    assert populated_entity.target_temperature_min == 39
    assert populated_entity.temperature == 54
    populated_entity.hvac_mode.mode = "cool"
    assert populated_entity.target_temperature == 79
    # Test no target temperature
    populated_entity.hvac_mode.mode = "off"
    populated_entity.hvac_mode.previous_mode = "off"
    assert populated_entity.target_temperature is None
    # Test does not support range
    populated_entity.hvac_mode.supported_modes.remove("auto")
    assert not populated_entity.supports_temperature_range


def test_init_empty(empty_entity):
    assert not empty_entity.current_temperature
    assert not empty_entity.fan_mode
    assert not empty_entity.hvac_action
    assert not empty_entity.hvac_mode
    assert not empty_entity.safety_max_temp
    assert not empty_entity.safety_min_temp
    assert not empty_entity.target_temperature_auto_heating

    # Property Checks
    assert not empty_entity.supports_fan_mode
    assert not empty_entity.supports_temperature_range


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
