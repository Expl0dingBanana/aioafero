import pytest

from aioafero.v1.models import features


def test_base_feature_requires_api_value_implementation():
    feat = features.AferoFeature(
        function_class="test",
        function_instance=None,
    )

    with pytest.raises(NotImplementedError):
        _ = feat.api_value


def test_ColorModeFeature():
    feat = features.ColorModeFeature(
        mode="white", function_class="color-mode", function_instance=None
    )
    assert feat.api_value == "white"


def test_ColorFeature():
    feat = features.ColorFeature(
        red=10,
        green=20,
        blue=30,
        function_class="color",
        function_instance=None,
    )
    assert feat.api_value == {
        "color-rgb": {
            "r": 10,
            "g": 20,
            "b": 30,
        }
    }


def test_ColorTemperatureFeature():
    feat = features.ColorTemperatureFeature(
        temperature=3000,
        supported=[1000, 2000, 3000],
        prefix="K",
        function_class="color-temperature",
        function_instance=None,
    )
    assert feat.api_value == "3000K"
    feat = features.ColorTemperatureFeature(
        temperature=3000,
        supported=[1000, 2000, 3000],
        function_class="color-temperature",
        function_instance=None,
    )
    assert feat.api_value == "3000"


def test_CurrentPositionEnum():
    feat = features.CurrentPositionEnum("locking")
    assert feat.value == features.CurrentPositionEnum.LOCKING.value
    feat = features.CurrentPositionEnum("no")
    assert feat.value == features.CurrentPositionEnum.UNKNOWN.value


def test_CurrentPositionFeature():
    feat = features.CurrentPositionFeature(
        position=features.CurrentPositionEnum.LOCKED,
        function_class="lock",
        function_instance=None,
    )
    assert feat.api_value == "locked"


def test_CurrentTemperatureFeature():
    feat = features.CurrentTemperatureFeature(
        temperature=1, function_class="temperature", function_instance="current-temp"
    )
    assert feat.api_value == 1


def test_DimmingFeature():
    feat = features.DimmingFeature(
        brightness=30,
        supported=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        function_class="dimming",
        function_instance=None,
    )
    assert feat.api_value == 30


def test_DirectionFeature():
    feat = features.DirectionFeature(
        forward=True, function_class="direction", function_instance=None
    )
    assert feat.api_value == "forward"
    feat = features.DirectionFeature(
        forward=False, function_class="direction", function_instance=None
    )
    assert feat.api_value == "reverse"


def test_EffectFeature():
    feat = features.EffectFeature(
        effect="fade-3",
        effects={"preset": {"fade-3"}, "custom": {"rainbow"}},
        function_class="color-sequence",
        function_instance="preset",
    )
    assert feat.api_value == "fade-3"
    assert feat.iter_afero_values() == [
        features.AferoValueEmission("color-sequence", "preset", "fade-3")
    ]
    feat.effect = "rainbow"
    assert feat.api_value == "rainbow"
    assert feat.iter_afero_values() == [
        features.AferoValueEmission("color-sequence", "preset", "custom"),
        features.AferoValueEmission("color-sequence", "custom", "rainbow"),
    ]
    assert feat.is_preset("fade-3")
    assert not feat.is_preset("rainbow")
    # effect does not exist
    feat.effect = "nope"
    assert feat.api_value == "nope"
    assert feat.iter_afero_values() == []
    feat = features.EffectFeature(
        effect="rainbow",
        effects={"custom": {"rainbow"}},
        function_class="color-sequence",
        function_instance="custom",
    )
    assert feat.iter_afero_values() == [
        features.AferoValueEmission("color-sequence", "preset", "custom"),
        features.AferoValueEmission("color-sequence", "custom", "rainbow"),
    ]
    assert not feat.is_preset("rainbow")


def test_effect_emission_uses_owned_function_class():
    feat = features.EffectFeature(
        effect="rainbow",
        effects={"custom": {"rainbow"}},
        function_class="owned-color-sequence",
        function_instance="custom",
    )

    assert feat.iter_afero_values() == [
        features.AferoValueEmission("owned-color-sequence", "preset", "custom"),
        features.AferoValueEmission("owned-color-sequence", "custom", "rainbow"),
    ]


def test_HVACModeFeature():
    feat = features.HVACModeFeature(
        mode="beans",
        previous_mode="not_beans",
        modes={"beans", "not_beans"},
        supported_modes={"beans", "not_beans"},
        function_class="hvac-mode",
        function_instance=None,
    )
    assert feat.api_value == "beans"


def test_ModeFeature():
    feat = features.ModeFeature(
        mode="color",
        modes={"color", "white"},
        function_class="mode",
        function_instance=None,
    )
    assert feat.api_value == "color"


def test_NumbersFeature():
    feat = features.NumbersFeature(
        value=12,
        min=0,
        max=20,
        step=1,
        name="Cool Beans",
        unit="bean count",
        function_class="number",
        function_instance="beans",
    )
    assert feat.api_value == 12


def test_OnFeature():
    feat = features.OnFeature(on=True, function_class="power", function_instance=None)
    assert feat.api_value == "on"
    feat = features.OnFeature(
        on=False, function_class="cool", function_instance="beans"
    )
    assert feat.api_value == "off"


def test_OpenFeature():
    feat = features.OpenFeature(
        open=True, function_class="toggle", function_instance=None
    )
    assert feat.api_value == "on"
    feat = features.OpenFeature(
        open=False, function_class="cool", function_instance="beans"
    )
    assert feat.api_value == "off"


def test_PresetFeature():
    feat = features.PresetFeature(
        enabled=True, function_class="cool", function_instance="beans"
    )
    assert feat.api_value == "enabled"
    feat.enabled = False
    assert feat.api_value == "disabled"


def test_SelectFeature():
    feat = features.SelectFeature(
        selected="beans",
        selects={"cool", "beans"},
        name="Those beans",
        function_class="select",
        function_instance="beans",
    )
    assert feat.api_value == "beans"


def test_SpeedFeature():
    feat = features.SpeedFeature(
        speed=25,
        speeds=[
            "speed-4-0",
            "speed-4-25",
            "speed-4-50",
            "speed-4-75",
            "speed-4-100",
        ],
        function_class="fan-speed",
        function_instance=None,
    )
    assert feat.api_value == "speed-4-25"
    feat.speed = 50
    assert feat.api_value == "speed-4-50"


def test_TargetTemperatureAutoFeature():
    feat = features.TargetTemperatureFeature(
        value=12,
        min=10,
        max=14,
        step=0.5,
        function_class="temperature",
        function_instance="whatever",
    )
    assert feat.api_value == 12


def test_SecuritySensorSirenFeature():
    feat = features.SecuritySensorSirenFeature(
        result_code=0,
        command=4,
        function_class="siren-action",
        function_instance=None,
    )
    assert feat.api_value == {"security-siren-action": {"resultCode": 0, "command": 4}}
    feat = features.SecuritySensorSirenFeature(
        result_code=None,
        command=None,
        function_class="siren-action",
        function_instance=None,
    )
    assert feat.api_value is None
