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
    )


@pytest.mark.parametrize(
    ("mode", "expected"), [
        ("cool", 26),
        ("heat", 19),
        ("dry", None),
    ]
)
def test_target_temperature(mode, expected, populatedEntity, mocker):
    populatedEntity.hvac_mode.mode = mode
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

@pytest.mark.parametrize(("mode", "expected"), [
    ("cool", 0.5),
    ("heat", 0.5),
    (None, 0.5),
])
def test_target_temperature_step(mode, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    assert populatedEntity.target_temperature_step == expected


@pytest.mark.parametrize(("mode", "is_set", "expected"), [
    ("cool", True, 37),
    ("auto", True, 32),
    ("cool", None, None),
    ("heat", True, 32),
])
def test_target_temperature_max(mode, is_set, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    if not is_set:
        populatedEntity.target_temperature_cooling = None
        populatedEntity.target_temperature_auto_cooling = None
    assert populatedEntity.target_temperature_max == expected


@pytest.mark.parametrize(("mode", "is_set", "expected"), [
    ("heat", True, 4),
    ("auto", True, 4),
    ("heat", None, None),
])
def test_target_temperature_min(mode, is_set, expected, populatedEntity):
    populatedEntity.hvac_mode.mode = mode
    if not is_set:
        populatedEntity.target_temperature_heating = None
        populatedEntity.target_temperature_auto_heating = None
    assert populatedEntity.target_temperature_min == expected


@pytest.mark.parametrize(("current_temperature", "expected"), [
    (None, None),
    (
        features.CurrentTemperatureFeature(
            temperature=35,
            function_class="temperature",
            function_instance="current-temp",
        ),
        35,
    ),
])
def test_temperature(populatedEntity, current_temperature, expected):
    populatedEntity.current_temperature = current_temperature
    assert populatedEntity.temperature == expected
