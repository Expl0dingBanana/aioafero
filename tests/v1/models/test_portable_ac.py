import pytest

from aioafero.v1.models import PortableAC, features, DeviceInformation


@pytest.fixture
def populated_entity():
    numbers = {
        ("timer", None): features.NumbersFeature(
            value=0, min=0, max=1440, step=30, name="timer", unit="minutes"
        )
    }
    selects = {
        ("fan-speed", "ac-fan-speed"): features.SelectFeature(
            selected="fan-speed-auto",
            selects={"fan-speed-auto", "fan-speed-2-100", "fan-speed-2-050"},
            name="Fan Speed",
        ),
        ("sleep", None): features.SelectFeature(
            selected="off",
            selects={"on", "off"},
            name="Sleep Timer",
        ),
    }
    return PortableAC(
        _id="entity-1",
        available=True,
        current_temperature=features.CurrentTemperatureFeature(
            temperature=35,
            function_class="temperature",
            function_instance="current-temp",
        ),
        hvac_mode=features.HVACModeFeature(
            mode="auto-cool",
            previous_mode="fan",
            modes={"fan", "auto-cool", "dehumidify", "cool"},
            supported_modes={"fan", "auto-cool", "dehumidify", "cool"},
        ),
        target_temperature_cooling=features.TargetTemperatureFeature(
            value=26, step=0.5, min=10, max=37, instance="cooling-target"
        ),
        numbers=numbers,
        selects=selects,
        device_information=DeviceInformation(
            functions=[
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ]
        )
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.temperature == 35
    assert populated_entity.current_temperature.function_class == "temperature"
    assert populated_entity.current_temperature.function_instance == "current-temp"
    assert populated_entity.hvac_mode.mode == "auto-cool"
    assert populated_entity.target_temperature_cooling.value == 26
    assert populated_entity.target_temperature_cooling.step == 0.5
    assert populated_entity.target_temperature_cooling.min == 10
    assert populated_entity.target_temperature_cooling.max == 37
    # Property checks
    assert populated_entity.target_temperature == 26
    assert populated_entity.target_temperature_max == 37
    assert populated_entity.target_temperature_min == 10
    assert populated_entity.target_temperature_step == 0.5
    assert populated_entity.supports_fan_mode is False
    assert populated_entity.supports_temperature_range is False


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"


def test_empty():
    entity = PortableAC(
        _id="entity-1",
        available=True,
        device_information=DeviceInformation(functions=[]),
        numbers={},
        selects={},
    )
    assert entity.get_mode_to_check() is None
    assert entity.temperature is None
    assert entity.target_temperature is None
    assert entity.target_temperature_max is None
    assert entity.target_temperature_min is None
    assert entity.supports_fan_mode is False
    assert entity.supports_temperature_range is False
    assert entity.target_temperature_step == 1


@pytest.mark.parametrize(
    ("mode", "previous_mode", "expected"),
    [
        (None, None, None),
        ("cool", None, "cool"),
        ("dehumidify", "cool", "cool"),
        ("auto-cool", None, "cool"),
        ("heat", "heat", "heat"),
        ("heat", None, "heat"),
        ("fan", None, None),
    ]
)
def test_get_mode_to_check(mode, previous_mode, expected, populated_entity):
    populated_entity.hvac_mode.mode = mode
    populated_entity.hvac_mode.previous_mode = previous_mode
    assert populated_entity.get_mode_to_check() == expected
