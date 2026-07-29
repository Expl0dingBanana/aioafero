import pytest

from aioafero.v1.models import DeviceInformation, features
from aioafero.v1.models.lock import Lock


@pytest.fixture
def populated_entity():
    return Lock(
        _id="entity-1",
        available=True,
        position=features.CurrentPositionFeature(
            position=features.CurrentPositionEnum.LOCKED,
            function_class="lock",
            function_instance=None,
        ),
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
