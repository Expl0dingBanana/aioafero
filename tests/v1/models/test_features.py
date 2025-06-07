from aioafero.v1.models import features


def test_ColorModeFeature():
    feat = features.ColorModeFeature("white")
    assert feat.api_value == "white"


def test_ColorFeature():
    feat = features.ColorFeature(red=10, green=20, blue=30)
    assert feat.api_value == {
        "value": {
            "color-rgb": {
                "r": 10,
                "g": 20,
                "b": 30,
            }
        }
    }


def test_ColorTemperatureFeature():
    feat = features.ColorTemperatureFeature(
        temperature=3000, supported=[1000, 2000, 3000], prefix="K"
    )
    assert feat.api_value == "3000K"


def test_CurrentPositionEnum():
    feat = features.CurrentPositionEnum("locking")
    assert feat.value == features.CurrentPositionEnum.LOCKING.value
    feat = features.CurrentPositionEnum("no")
    assert feat.value == features.CurrentPositionEnum.UNKNOWN.value


def test_CurrentPositionFeature():
    feat = features.CurrentPositionFeature(features.CurrentPositionEnum.LOCKED)
    assert feat.api_value == "locked"


def test_CurrentTemperatureFeature():
    feat = features.CurrentTemperatureFeature(
        temperature=1, function_class="temperature", function_instance="current-temp"
    )
    assert feat.api_value == {
        "functionClass": "temperature",
        "functionInstance": "current-temp",
        "value": 1,
    }


def test_DimmingFeature():
    feat = features.DimmingFeature(
        brightness=30, supported=[10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
    )
    assert feat.api_value == 30


def test_DirectionFeature():
    feat = features.DirectionFeature(forward=True)
    assert feat.api_value == "forward"
    feat = features.DirectionFeature(forward=False)
    assert feat.api_value == "reverse"


def test_EffectFeature():
    feat = features.EffectFeature(
        effect="fade-3", effects={"preset": {"fade-3"}, "custom": {"rainbow"}}
    )
    assert feat.api_value == [
        {
            "functionClass": "color-sequence",
            "functionInstance": "preset",
            "value": "fade-3",
        }
    ]
    feat.effect = "rainbow"
    assert feat.api_value == [
        {
            "functionClass": "color-sequence",
            "functionInstance": "preset",
            "value": "custom",
        },
        {
            "functionClass": "color-sequence",
            "functionInstance": "custom",
            "value": "rainbow",
        },
    ]
    assert feat.is_preset("fade-3")
    assert not feat.is_preset("rainbow")
    feat = features.EffectFeature(effect="fade-3", effects={"custom": {"rainbow"}})
    assert not feat.is_preset("rainbow")


def test_HVACModeFeature():
    feat = features.HVACModeFeature(
        mode="beans",
        previous_mode="not_beans",
        modes={"beans", "not_beans"},
        supported_modes={"beans", "not_beans"},
    )
    assert feat.api_value == "beans"


def test_ModeFeature():
    feat = features.ModeFeature(mode="color", modes={"color", "white"})
    assert feat.api_value == "color"


def test_NumbersFeature():
    feat = features.NumbersFeature(
        value=12,
        min=0,
        max=20,
        step=1,
        name="Cool Beans",
        unit="bean count",
    )
    assert feat.api_value == 12


def test_OnFeature():
    feat = features.OnFeature(on=True)
    assert feat.api_value == {"value": "on", "functionClass": "power"}
    feat = features.OnFeature(on=False, func_class="cool", func_instance="beans")
    assert feat.api_value == {
        "value": "off",
        "functionClass": "cool",
        "functionInstance": "beans",
    }


def test_OpenFeature():
    feat = features.OpenFeature(open=True)
    assert feat.api_value == {"value": "on", "functionClass": "toggle"}
    feat = features.OpenFeature(open=False, func_class="cool", func_instance="beans")
    assert feat.api_value == {
        "value": "off",
        "functionClass": "cool",
        "functionInstance": "beans",
    }


def test_PresetFeature():
    feat = features.PresetFeature(
        enabled=True, func_class="cool", func_instance="beans"
    )
    assert feat.api_value == {
        "value": "enabled",
        "functionClass": "cool",
        "functionInstance": "beans",
    }
    feat.enabled = False
    assert feat.api_value == {
        "value": "disabled",
        "functionClass": "cool",
        "functionInstance": "beans",
    }


def test_SelectFeature():
    feat = features.SelectFeature(
        selected="beans", selects={"cool", "beans"}, name="Those beans"
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
        instance="whatever",
    )
    assert feat.api_value == {
        "functionClass": "temperature",
        "functionInstance": "whatever",
        "value": 12,
    }
