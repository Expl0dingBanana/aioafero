import pytest

from aioafero.v1.models import DeviceInformation, SecuritySystemKeypad, features


@pytest.fixture
def populated_entity():
    return SecuritySystemKeypad(
        _id="entity-1",
        available=True,
        selects={
            ("volume", "buzzer-volume"): features.SelectFeature(
                selected="volume-04",
                selects={
                    "volume-00",
                    "volume-01",
                    "volume-02",
                    "volume-03",
                    "volume-04",
                },
                name="Buzzer Volume",
                function_class="volume",
                function_instance="buzzer-volume",
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


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
