import pytest

from aioafero.v1.models import SecuritySystemSensor, features
from aioafero.v1.models.sensor import AferoBinarySensor, AferoSensor


@pytest.fixture
def populated_entity():
    return SecuritySystemSensor(
        [
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ],
        _id="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
        available=True,
        selects={
            ("sensor-2 ", "chirpMode"): features.SelectFeature(
                selected="On",
                selects={"On", "Off"},
                name="Chirp Mode",
            ),
        },
        binary_sensors={
            "tampered": AferoBinarySensor(
                id="tampered",
                owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
                instance="tampered",
                _value=1,
                _error=1,
            )
        },
        sensor={
            "batteryLevel": AferoSensor(
                id="sensor-state",
                owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
                _value=100,
                unit="%",
                instance=None,
            ),
        },
        instances="i dont execute",
    )


@pytest.fixture
def empty_entity():
    return SecuritySystemSensor(
        [
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ],
        _id="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
        available=True,
        selects={},
        binary_sensors={},
        sensor={},
        instances="i dont execute",
    )


def test_init(populated_entity):
    assert populated_entity.id == "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.update_id == "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    assert populated_entity.sensor_id == 2
