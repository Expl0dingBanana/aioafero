import pytest

from aioafero.v1.models import SecuritySystem, features


@pytest.fixture
def populated_entity():
    return SecuritySystem(
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
        alarm_state=features.ModeFeature(
            mode="arm-away", modes={"arm-away", "disarmed", "arm-stay", "alarming-sos"}
        ),
        numbers={
            ("arm-exit-delay", "away"): features.NumbersFeature(
                value=0,
                min=0,
                max=300,
                step=1,
                name="Exit Delay - Away",
                unit="seconds",
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
            ),
        },
        instances="i dont execute",
    )


@pytest.fixture
def empty_entity():
    return SecuritySystem(
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
        alarm_state=None,
        numbers={},
        selects={},
        instances="i dont execute",
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.supports_away is True
    assert populated_entity.supports_arm_bypass is False
    assert populated_entity.supports_home is True
    assert populated_entity.supports_night is False
    assert populated_entity.supports_vacation is False
    assert populated_entity.supports_trigger is True


def test_init_empty(empty_entity):
    assert empty_entity.alarm_state is None


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
