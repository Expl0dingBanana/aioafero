import pytest

from aioafero.v1.models import features
from aioafero.v1.models.lock import Lock


@pytest.fixture
def populated_entity():
    return Lock(
        functions=[
            {
                "functionClass": "preset",
                "functionInstance": "preset-1",
                "value": "on",
                "lastUpdateTime": 0,
            }
        ],
        _id="entity-1",
        available=True,
        position=features.CurrentPositionFeature(
            position=features.CurrentPositionEnum.LOCKED
        ),
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
