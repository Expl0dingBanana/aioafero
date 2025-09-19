import pytest

from aioafero.v1.models import features, DeviceInformation
from aioafero.v1.models.valve import Valve


@pytest.fixture
def populated_entity():
    return Valve(
        _id="entity-1",
        available=True,
        open={None: features.OpenFeature(open=True)},
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
    return Valve(
        _id="entity-1",
        available=True,
        open=None,
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"
    assert populated_entity.available is True
    assert populated_entity.instances == {"preset": "preset-1"}
    assert populated_entity.open[None].open is True


def test_init_empty(empty_entity):
    assert not empty_entity.open


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
