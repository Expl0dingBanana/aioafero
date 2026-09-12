import pytest

from aioafero.device import SplitDeviceId
from aioafero.v1.models import DeviceInformation, features
from aioafero.v1.models.switch import Switch


@pytest.fixture
def populated_entity():
    return Switch(
        _id="entity-1",
        available=True,
        on={
            None: features.OnFeature(
                on=True, function_class="power", function_instance=None
            )
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
    return Switch(
        _id="entity-1",
        available=True,
        on=None,
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
    assert populated_entity.on[None].on is True
    assert populated_entity.update_id == "entity-1"
    assert populated_entity.instance is None
    assert populated_entity.split_identifier is None
    populated_entity.split = SplitDeviceId("entity", "beans", "1")
    populated_entity._id = str(populated_entity.split)
    assert populated_entity.update_id == "entity"
    assert populated_entity.instance == "1"
    populated_entity.split = SplitDeviceId(
        "c12e2c2c-c009-41bb-963f-d4f3a77d6928", "light", "light-sensor-enabled"
    )
    populated_entity._id = str(populated_entity.split)
    assert populated_entity.update_id == "c12e2c2c-c009-41bb-963f-d4f3a77d6928"
    assert populated_entity.instance == "light-sensor-enabled"


def test_init_empty(empty_entity):
    assert not empty_entity.on
