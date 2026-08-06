import pytest

from aioafero.v1.models import DeviceInformation, SecuritySystem, features


@pytest.fixture
def populated_entity():
    return SecuritySystem(
        _id="entity-1",
        available=True,
        alarm_state=features.ModeFeature(
            mode="arm-away",
            modes={"arm-away", "disarmed", "arm-stay", "alarming-sos"},
            function_class="security-system-mode",
            function_instance=None,
        ),
        numbers={
            ("arm-exit-delay", "away"): features.NumbersFeature(
                value=0,
                min=0,
                max=300,
                step=1,
                name="Exit Delay - Away",
                unit="seconds",
                function_class="arm-exit-delay",
                function_instance="away",
            ),
        },
        selects={
            ("volume ", "siren "): features.SelectFeature(
                selected="volume-04",
                selects={
                    "volume-00",
                    "volume-01",
                    "volume-02",
                    "volume-03",
                    "volume-04",
                },
                name="Siren Volume",
                function_class="volume",
                function_instance="siren",
            ),
        },
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
def empty_entity():
    return SecuritySystem(
        _id="entity-1",
        available=True,
        alarm_state=None,
        numbers={},
        selects={},
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.supports_away is True
    assert populated_entity.supports_arm_bypass is False
    assert populated_entity.supports_home is True
    assert populated_entity.supports_night is False
    assert populated_entity.supports_vacation is False
    assert populated_entity.supports_trigger is True


def test_init_empty(empty_entity):
    assert empty_entity.alarm_state is None
