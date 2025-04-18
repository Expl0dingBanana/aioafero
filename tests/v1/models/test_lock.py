import pytest

from aioafero.v1.models import features
from aioafero.v1.models.lock import Lock


@pytest.fixture
def populated_entity():
    return Lock(
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
        instances="i dont execute",
        position=features.CurrentPositionFeature(
            position=features.CurrentPositionEnum.LOCKED
        ),
    )


def test_init(populated_entity):
    assert populated_entity.id == "entity-1"


def test_get_instance(populated_entity):
    assert populated_entity.get_instance("preset") == "preset-1"
