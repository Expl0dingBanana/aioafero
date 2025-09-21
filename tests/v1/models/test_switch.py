import pytest

from aioafero.v1.models import features, DeviceInformation
from aioafero.v1.models.switch import Switch


@pytest.fixture
def populated_entity():
    return Switch(
        _id="entity-1",
        available=True,
        on={None: features.OnFeature(on=True)},
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
        )
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.on[None].on is True
    assert populated_entity.update_id == "entity-1"
    assert populated_entity.instance is None
    populated_entity._id = "entity-beans-1"
    populated_entity.split_identifier = "beans"
    assert populated_entity.update_id == "entity"
    assert populated_entity.instance == "1"


def test_init_empty(empty_entity):
    assert not empty_entity.on


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
