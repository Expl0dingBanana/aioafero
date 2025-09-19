import pytest

from aioafero.v1.models import SecuritySystemSensor, features, DeviceInformation
from aioafero.v1.models.sensor import AferoBinarySensor, AferoSensor


@pytest.fixture
def populated_entity():
    return SecuritySystemSensor(
        _id="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
        split_identifier="sensor",
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
                current_value=1,
                _error=1,
            )
        },
        sensors={
            "batteryLevel": AferoSensor(
                id="sensor-state",
                owner="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
                value=100,
                unit="%",
                instance=None,
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
        )
    )


@pytest.fixture
def empty_entity():
    return SecuritySystemSensor(
        _id="7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2",
        split_identifier="sensor",
        available=True,
        selects={},
        binary_sensors={},
        sensors={},
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
    assert populated_entity.id == "7f4e4c01-e799-45c5-9b1a-385433a78edc-sensor-2"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.update_id == "7f4e4c01-e799-45c5-9b1a-385433a78edc"
    assert populated_entity.instance == 2
