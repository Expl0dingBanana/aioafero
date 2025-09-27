import pytest

from aioafero.v1.models import features, DeviceInformation
from aioafero.v1.models.hvac_mixin import HVACMixin


class DummyHVAC(HVACMixin):
    def get_mode_to_check(self) -> str | None:
        return self.hvac_mode.mode

@pytest.fixture
def populatedEntity():
    return DummyHVAC(
        current_temperature=features.CurrentTemperatureFeature(
            temperature=35,
            function_class="temperature",
            function_instance="current-temp",
        ),
        hvac_mode=features.HVACModeFeature(
            mode="cool",
            previous_mode="fan",
            modes={"fan", "auto-cool", "dehumidify", "cool"},
            supported_modes={"fan", "auto-cool", "dehumidify", "cool"},
        ),
        target_temperature_heating=features.TargetTemperatureFeature(
            value=19, step=0.5, min=4, max=32, instance="heating-target"
        ),
        target_temperature_cooling=features.TargetTemperatureFeature(
            value=26, step=0.5, min=10, max=37, instance="cooling-target"
        ),
        target_temperature_auto_heating=features.TargetTemperatureFeature(
            value=18, step=0.5, min=4, max=32, instance="auto-heating-target"
        ),
        target_temperature_auto_cooling=features.TargetTemperatureFeature(
            value=26.5, step=0.5, min=4, max=32, instance="auto-cooling-target"
        ),
        fan_running=False,
        fan_mode=features.ModeFeature(mode="off", modes={"on", "off"}),
        display_celsius=True,
    )


@pytest.mark.parametrize(
    ("mode", "celsius", "expected"), [
        ("cool", True, 26),
        ("heat", True, 19),
        ("dry", True, None),
        ("heat", False, 66),
    ]
)
def test_target_temperature(mode, celsius, expected, populatedEntity, mocker):
    populatedEntity.hvac_mode.mode = mode
    populatedEntity.display_celsius = celsius
    assert populatedEntity.target_temperature == expected


def test_target_temperature_no_feature(populatedEntity):
    populatedEntity.hvac_mode.mode = "cool"
    populatedEntity.target_temperature_cooling = None
    assert populatedEntity.target_temperature is None


@pytest.mark.parametrize(("mode", "expected"), [
    ("cool", features.TargetTemperatureFeature(
            value=26, step=0.5, min=10, max=37, instance="cooling-target"
        )),
    ("heat", features.TargetTemperatureFeature(
            value=19, step=0.5, min=4, max=32, instance="heating-target"
        )),
    ("dry", None),
])
def test__get_target_feature(mode, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    assert populatedEntity._get_target_feature(mode) == expected

@pytest.mark.parametrize(("mode", "expected", "celsius"), [
    ("cool", 0.5, True),
    ("heat", 0.5, True),
    (None, 0.5, True),
    ("cool", 1, False),
])
def test_target_temperature_step(mode, expected, celsius, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    populatedEntity.display_celsius = celsius
    assert populatedEntity.target_temperature_step == expected


@pytest.mark.parametrize(("mode", "celsius", "is_set", "expected"), [
    ("cool", True, True, 37),
    ("cool", False, True, 99),
    ("auto", True, True, 32),
    ("cool", True, None, None),
    ("heat", True, True, 32),
])
def test_target_temperature_max(mode, celsius, is_set, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    populatedEntity.display_celsius = celsius
    if not is_set:
        populatedEntity.target_temperature_cooling = None
        populatedEntity.target_temperature_auto_cooling = None
    assert populatedEntity.target_temperature_max == expected


@pytest.mark.parametrize(("mode", "celsius", "is_set", "expected"), [
    ("heat", True, True, 4),
    ("heat", False, True, 39),
    ("auto", True, True, 4),
    ("heat", True, None, None),
])
def test_target_temperature_min(mode, celsius, is_set, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    populatedEntity.display_celsius = celsius
    if not is_set:
        populatedEntity.target_temperature_heating = None
        populatedEntity.target_temperature_auto_heating = None
    assert populatedEntity.target_temperature_min == expected


@pytest.mark.parametrize(("current_temperature", "celsius", "expected"), [
    (None, None, None),
    (
        features.CurrentTemperatureFeature(
            temperature=35,
            function_class="temperature",
            function_instance="current-temp",
        ),
        True,
        35,
    ),
    (
        features.CurrentTemperatureFeature(
            temperature=35,
            function_class="temperature",
            function_instance="current-temp",
        ),
        False,
        95,
    ),
])
def test_temperature(populatedEntity, current_temperature, celsius, expected):
    populatedEntity.current_temperature = current_temperature
    populatedEntity.display_celsius = celsius
    assert populatedEntity.temperature == expected
